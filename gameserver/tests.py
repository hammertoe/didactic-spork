import json
import unittest
import os
from gameserver.utils import random, pack_amount, unpack_amount, checksum
import time
from datetime import datetime, timedelta

#if not os.environ.has_key('SQLALCHEMY_DATABASE_URI'):
#    os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
from gameserver.game import Game
from gameserver.models import Base, Node, Player, Goal, Policy, Edge, Table
from sqlalchemy import event

from gameserver.database import db, default_uuid
from gameserver.wallet_sqlalchemy import Wallet
from gameserver.app import app, create_app
from flask_testing import TestCase

from gameserver.utils import fake_memcache as memcache, checksum
from gameserver.settings import GAME_ID

db.app = app

db_session = db.session
engine = db.engine

@event.listens_for(engine, "connect")
def do_connect(dbapi_connection, connection_record):
    # disable pysqlite's emitting of the BEGIN statement entirely.
    # also stops it from emitting COMMIT before any DDL.
    dbapi_connection.isolation_level = None

@event.listens_for(engine, "begin")
def do_begin(conn):
    # emit our own BEGIN
    conn.execute("BEGIN")

class UnitTests(unittest.TestCase):

    def testPackAmount(self):
        v = 1.4567
        self.assertAlmostEqual(unpack_amount(pack_amount(v)), v, 3)

    def testChecksum(self):
        c1 = checksum('1', '2', 3.14, 'salt')
        self.assertEqual(len(c1), 40)

        c2 = checksum('1', '2', 3.14, 'salt')
        self.assertEqual(c1, c2)

        c3 = checksum('1', '2', 3.15, 'salt')
        self.assertNotEqual(c1, c3)

    def testFakeMemcache(self):
        memcache.add('foo', 'bar', 100)
        res = memcache.get('foo')
        self.assertEqual(res, 'bar')

        memcache.set('foo', 'baz', 100)
        res = memcache.get('foo')
        self.assertEqual(res, 'baz')

        memcache.set_multi({'foo': 1, 'bar': 2}, 100)
        res = memcache.get('foo')
        self.assertEqual(res, 1)
        res = memcache.get('bar')
        self.assertEqual(res, 2)

        memcache.clear()
        res = memcache.get('bar')
        self.assertEqual(res, None)

class DBTestCase(TestCase):

    SQLALCHEMY_DATABASE_URI = "sqlite://"
    TESTING = True

    def create_app(self):
        # pass in test configuration
        return app

    @classmethod
    def setUpClass(cls):
        db_session.begin(subtransactions=True)
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db_session.rollback()
        db_session.close()

    def setUp(self):
        db_session.begin_nested()
        self.game = Game()
        test_client = self.game.add_client('tests')
        self.api_key = test_client.id
        memcache.clear()

    def tearDown(self):
        db_session.rollback()
        os.system('echo "select * from node;" | sqlite3 gameserver/database.db')

    def add_20_goals_and_policies(self):
        for x in range(20):
            g = self.game.add_goal("G{}".format(x), 0.5)
            g.id = "G{}".format(x)
            p = self.game.add_policy("P{}".format(x), 0.5)
            p.id = "P{}".format(x)

class CoreGameTests(DBTestCase):
        
    def testAddPlayer(self):

        p = self.game.create_player('Matt')

        self.assertEqual(self.game.get_player(p.id), p)
        self.assertEqual(self.game.num_players, 1)

    def testGameCreatePlayer(self):
        
        self.add_20_goals_and_policies()
        random.seed(1)
        p = self.game.create_player('Matt')
        self.assertEqual(self.game.get_player(p.id), p)
        self.assertEqual(p.goal.name, 'G10')
        self.assertEqual([x.name for x in p.children()], ['P13', 'P5', 'P10', 'P9', 'P2'])

    def testGameClearPlayers(self):
        self.add_20_goals_and_policies()
        random.seed(1)
        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')
        self.assertEqual(db_session.query(Player).count(), 2)
        self.assertEqual(db_session.query(Edge).count(), 10)

        self.game.clear_players()
        db_session.flush()
        
        self.assertEqual(db_session.query(Player).count(), 0)
        self.assertEqual(db_session.query(Edge).count(), 0)        

    def testPlayerHasWallet(self):

        p = self.game.create_player('Matt')

        self.assertEqual(self.game.get_player(p.id), p)
        self.assertAlmostEqual(p.balance, self.game.money_per_budget_cycle)

    def testPlayerSetBalance(self):

        p = self.game.create_player('Matt')
        p.balance = 5000

        self.assertAlmostEqual(p.balance, 5000.0)

    def testAddPolicy(self):

        p = self.game.add_policy('Arms Embargo', 0.1)

        self.assertEqual(self.game.get_policy(p.id), p)
        self.assertEqual(self.game.get_policy(p.id).leak, 0.1)

    def testAddWalletToPolicy(self):

        po1 = self.game.add_policy('Arms Embargo', 0.1)
        p1 = self.game.create_player('Matt')
        w1 = Wallet([(p1.id, 100)])
        po1.wallet = w1

        self.assertIn(p1.id, w1.todict())
        self.assertEqual(po1.wallet, w1)


    def testAddGoal(self):

        g = self.game.add_goal('World Peace', 0.5)

        self.assertEqual(self.game.get_goal(g.id), g)
        self.assertEqual(self.game.get_goal(g.id).leak, 0.5)

    def testGetRandomGoal(self):
        
        self.add_20_goals_and_policies()

        random.seed(1)
        self.assertEqual(self.game.get_random_goal().name, 'G10')
        self.assertEqual(self.game.get_random_goal().name, 'G6')
        

    def testAddPlayerAndGoal(self):
        
        p1 = self.game.create_player('Matt')
        g1 = self.game.add_goal('World Peace', 0.5)
        p1.goal = g1

        self.assertEqual(p1.goal, g1)
        self.assertIn(p1, g1.players)

    def testAddWalletToGoal(self):

        g = self.game.add_goal('World Peace', 0.5)
        p1 = self.game.create_player('Matt')
        w1 = Wallet([(p1.id, 100.0)])
        g.wallet = w1

        self.assertEqual(g.wallet, w1)

    def testGetNPolicies(self):
        g1 = self.game.add_goal('A', 0.5)
        self.add_20_goals_and_policies()

        random.seed(1)
        policies = ['P8', 'P19', 'P13', 'P5', 'P7']
        self.assertEqual([x.name for x in self.game.get_n_policies(g1)], policies)
        
    def testModifyPolicies(self):

        p1 = self.game.add_policy('Policy 1', 0.1)
        p2 = self.game.add_policy('Policy 2', 0.2)

        self.assertEqual(self.game.get_policy(p1.id).leak, 0.1)

        p1.leak = 0.3
        self.assertEqual(self.game.get_policy(p1.id).leak, 0.3)
        self.assertEqual(self.game.get_policy(p2.id).leak, 0.2)

    def testChildParentRelationship(self):
        a = Node('A', 0.1)
        b = Node('B', 0.1)

        l = self.game.add_link(a, b, 1.0)
        self.assertIn(a, b.parents())
        self.assertIn(b, a.children())

    def testPlayerFundedPolicies(self):
        p1 = self.game.add_policy('Policy 1', 0.1)
        p2 = self.game.add_policy('Policy 2', 0.2)
        p3 = self.game.add_policy('Policy 3', 0.2)
        p = self.game.create_player('Matt')

        p.fund(p1, 20)
        p.fund(p2, 30)
        p.fund(p3, 0)

        self.assertEqual(sorted(p.policies), sorted([p1,p2,p3]))
        self.assertEqual(sorted(p.funded_policies), sorted([p1,p2]))

    def testSimpleNetwork(self):
        n1 = self.game.add_policy('Policy 1', 0.1)
        n2 = self.game.add_goal('Goal 1', 0.2)
        l1 = self.game.add_link(n1, n2, 0.5)

        self.assertEqual(self.game.get_link(l1.id), l1)
        self.assertIn(n2, n1.children())
        
    def testMultiLevelNetwork(self):
        n1 = self.game.add_policy('Policy 1', 0.1)
        n2 = self.game.add_policy('Policy 2', 0.1)
        n3 = self.game.add_goal('Goal 1', 0.2)
        
        l1 = self.game.add_link(n1, n2, 0.5)
        l2 = self.game.add_link(n2, n3, 0.5)

        self.assertEqual(n3, n1.children()[0].children()[0])

    def testAddWallets(self):
        n1 = self.game.add_policy('Policy 1', 0.1)
        p1 = self.game.create_player('Matt')

        self.assertEqual(n1.balance, 0)

        w1 = Wallet([(p1.id, 5.0)])
        self.assertEqual(n1.balance, 0)
        n1.wallet = w1
        self.assertEqual(n1.balance, 5.0)

        w2 = Wallet([(p1.id, 10.0)])
        n1.wallet &= w2

        self.assertEqual(n1.balance, 15.0)

    def testNodeLeak100(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')
        n1.wallet = Wallet([(p1.id, 5.0),
                            (p2.id, 10.0),])

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 0.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 0.0)

    def testNodeLeak0(self):
        n1 = self.game.add_policy('Policy 1', 0.0)
        p1 = self.game.create_player('Matt')
        n1.wallet = Wallet([(p1.id, 15.0)])

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 15.0)

    def testNodeLeak20(self):
        n1 = self.game.add_policy('Policy 1', 0.2)
        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')
        n1.wallet = Wallet([(p1.id, 5.0),
                            (p2.id, 10.0),])

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertAlmostEqual(n1.balance, 12.0)
        n1.do_leak()
        self.assertAlmostEqual(n1.balance, 9.6)

        # Check the individual wallets
        d = n1.wallet.todict()
        self.assertAlmostEqual(d[p1.id], 3.2, 5)
        self.assertAlmostEqual(d[p2.id], 6.4, 5)

    def testNodeLeakNegative20(self):
        n1 = self.game.add_policy('Policy 1', 0.2)
        g1 = self.game.add_goal('Goal 1', 0.2)
        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')
        g1.wallet = Wallet([(p1.id, 5.0),
                            (p2.id, 10.0),])

        # add a negative impact edge
        l1 = self.game.add_link(n1, g1, -0.5)

        self.assertEqual(g1.balance, 15.0)
        g1.do_leak()
        self.assertAlmostEqual(g1.balance, 4.5)
        g1.do_leak()
        self.assertAlmostEqual(g1.balance, 1.35)

        # Check the individual wallets
        d = g1.wallet.todict()
        self.assertAlmostEqual(d[p1.id], 0.45, 5)
        self.assertAlmostEqual(d[p2.id], 0.9, 5)

    def testTransferWalletToWallet(self):
        p1 = self.game.create_player('Matt')
        w1 = Wallet([(p1.id, 100.0)])
        w2 = Wallet([(p1.id, 20.0)])

        self.assertAlmostEqual(w1.total, 100.0)
        self.assertAlmostEqual(w2.total, 20.0)

        w1.transfer(w2, 30.0)

        self.assertAlmostEqual(w1.total, 70.0)
        self.assertAlmostEqual(w2.total, 50.0)

    def testTransferToWalletInsufficientFunds(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        p1 = self.game.create_player('Matt')
        n1.wallet = Wallet([(p1.id, 100.0)])
        n2 = self.game.add_policy('Policy 2', 1.0)

        self.assertAlmostEqual(n1.balance, 100.0)
        self.assertAlmostEqual(n2.balance, 0.0)

        with self.assertRaises(ValueError):
            n1.wallet.transfer(n2.wallet, 110.0)

        self.assertAlmostEqual(n1.wallet.total, 100.0)
        self.assertAlmostEqual(n2.wallet.total, 0.0)


    def testAllocateFunds(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        n1 = self.game.add_policy('Policy 1', 1.0)

        self.assertEqual(p1.balance, 1000.0)
        self.assertEqual(n1.balance, 0.0)

        p1.transfer_funds()

        self.assertEqual(p1.balance, 1000.0)
        self.assertEqual(n1.balance, 0.0)

        self.game.add_fund(p1, n1, 100)

        p1.transfer_funds()

        self.assertEqual(p1.balance, 900.0)
        self.assertEqual(n1.balance, 100.0)

    def testAllocateDifferentFunds(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        n1 = self.game.add_policy('Policy 1', 1.0)

        self.game.add_fund(p1, n1, 60)
        p1.transfer_funds()

        self.assertEqual(p1.balance, 940.0)
        self.assertEqual(n1.balance, 60.0)

        self.game.add_fund(p1, n1, 80)
        p1.transfer_funds()

        self.assertEqual(p1.balance, 860.0)
        self.assertEqual(n1.balance, 140.0)

    def testDeleteFunds(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        n1 = self.game.add_policy('Policy 1', 1.0)

        self.game.add_fund(p1, n1, 100)
        p1.transfer_funds()

        self.assertEqual(p1.balance, 900.0)
        self.assertEqual(n1.balance, 100.0)

        self.game.add_fund(p1, n1, 0)
        p1.transfer_funds()

        self.assertEqual(p1.balance, 900.0)
        self.assertEqual(n1.balance, 100.0)

        # test that we keep the link even when funding stopped
        self.assertEqual(len(p1.children()), 1)

    def testGameTotalInflow(self):
        p1 = self.game.create_player('Matt')
        self.assertEqual(self.game.total_players_inflow, 1000)
        p2 = self.game.create_player('Simon')
        self.assertEqual(self.game.total_players_inflow, 2000)
        p2.max_outflow = 50
        self.assertEqual(self.game.total_players_inflow, 1050)

    def testGameTotalActiveInflow(self):
        p1 = self.game.create_player('Matt')
        self.assertEqual(self.game.total_active_players_inflow, 1000)
        p2 = self.game.create_player('Simon')
        self.assertEqual(self.game.total_active_players_inflow, 2000)
        p2.max_outflow = 50
        self.assertEqual(self.game.total_active_players_inflow, 1050)

        p1.last_budget_claim = datetime.now()-timedelta(hours=6)
        self.assertEqual(self.game.total_active_players_inflow, 50)

        p1.claim_budget()
        self.assertEqual(self.game.total_active_players_inflow, 1050)


    def testPlayerTotalFunding(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        self.game.add_fund(p1, po1, 10)
        po2 = self.game.add_policy('Policy 2', 1.0)
        self.game.add_fund(p1, po2, 20)
        po3 = self.game.add_policy('Policy 3', 1.0)
        self.game.add_fund(p1, po3, 30)

        self.assertEqual(p1.total_funding, 60)

        self.game.add_fund(p1, po3, 10)
        self.assertEqual(p1.total_funding, 40)

        self.game.add_fund(p1, po2, 0)
        self.assertEqual(p1.total_funding, 20)

    def testPlayerMaxOutflow(self):
        p1 = self.game.create_player('Matt')
        self.assertEqual(p1.max_outflow, self.game.standard_max_player_outflow)
        
    def testPlayerExceedMaxOutflow(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        self.game.add_fund(p1, po1, 100)
        po2 = self.game.add_policy('Policy 2', 1.0)
        self.game.add_fund(p1, po2, 200)
        po3 = self.game.add_policy('Policy 3', 1.0)

        with self.assertRaises(ValueError):
            self.game.add_fund(p1, po3, 800)

        self.assertEqual(p1.total_funding, 300)

        self.game.add_fund(p1, po3, 700)
        self.assertEqual(p1.total_funding, 1000)

    def testGoalActive(self):
        p1 = self.game.create_player('Player 1')
        p1.balance = 1000
        po1 = self.game.add_policy('Policy 1', 0.0)
        g1 = self.game.add_goal('Goal 1', 0.0)
        g1.activation = 400
        l1 = self.game.add_link(po1, g1, 200.0)
        self.game.add_fund(p1, po1, 200.0)
        self.game.do_propogate_funds()

        self.assertAlmostEqual(p1.balance, 800)

        self.assertAlmostEqual(g1.balance, 200)
        self.assertFalse(g1.active)

        self.game.do_propogate_funds()
        self.assertTrue(g1.active)


    def testNodeActivationFromPlayer(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        po1.activation = 0.2

        self.assertFalse(po1.active)
        self.assertAlmostEqual(po1.active_level, 0)
        self.game.add_fund(p1, po1, 200.0)
        self.game.do_propogate_funds()
        
        self.assertTrue(po1.active)

    def testNodeActivationFromNode(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 10000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        po1.activation = 0.1

        self.assertAlmostEqual(po1.active_level, 0)
        self.assertFalse(po1.active)

        po2 = self.game.add_policy('Policy 2', 1.0)
        po2.activation = 0.2
        l1 = self.game.add_link(po1, po2, 50.0)

        self.assertAlmostEqual(po1.active, 0.0)
        self.assertFalse(po1.active)

        self.game.add_fund(p1, po1, 200.0)
        for x in range(5):
            self.game.do_propogate_funds()
        
        self.assertTrue(po1.active)
        self.assertAlmostEqual(po1.active_level, 0.2)
        self.assertAlmostEqual(po1.active_percent, 2.0)
        self.assertFalse(po2.active)

        self.game.add_fund(p1, po1, 400.0)
        self.assertTrue(po1.active)
        self.assertAlmostEqual(po1.active_percent, 2.0)
        self.assertFalse(po2.active)
        self.assertAlmostEqual(po2.active_percent, 0.25)

        l1.weight = 400.0
        self.game.do_propogate_funds()
        self.assertTrue(po1.active)
        self.assertTrue(po2.active)
        self.assertAlmostEqual(po2.active_percent, 2.0)


    def testTwoPlayersFundPolicy(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        p2 = self.game.create_player('Simon')
        p2.balance = 1000.0
        n1 = self.game.add_policy('Policy 1', 1.0)

        self.game.add_fund(p1, n1, 100)
        self.game.add_fund(p2, n1, 90)
        p1.transfer_funds()
        p2.transfer_funds()

        self.assertEqual(p1.balance, 900.0)
        self.assertEqual(p2.balance, 910.0)
        self.assertEqual(n1.balance, 190.0)

        self.assertEqual(len(n1.parents()), 2)

    def testGameTransferFunds(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        p2 = self.game.create_player('Simon')
        p2.balance = 1000.0
        p3 = self.game.create_player('Rich')
        p3.balance = 1000.0
    
        n1 = self.game.add_policy('Policy 1', 1.0)

        self.game.add_fund(p1, n1, 10)
        self.game.add_fund(p2, n1, 20)
        self.game.add_fund(p3, n1, 50)

        

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 990.0)
        self.assertEqual(p2.balance, 980.0)
        self.assertEqual(p3.balance, 950.0)
        self.assertEqual(n1.balance, 80.0)

        self.assertEqual(len(n1.parents()), 3)

    def testGameTransferFundsNoMaxLevel(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
    
        n1 = self.game.add_policy('Policy 1', 1.0)
        n1.max_level = 0
        self.game.add_fund(p1, n1, 10)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 990.0)
        self.assertEqual(n1.balance, 10.0)

    def testGameTransferFundsMaxLevel(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
    
        n1 = self.game.add_policy('Policy 1', 1.0)
        n1.max_level = 5.0
        self.game.add_fund(p1, n1, 10)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 990.0)
        self.assertEqual(n1.balance, 5.0)

    def testGameTransferFundsMaxLevelMultiplePlayers(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
    
        p2 = self.game.create_player('Simon')
        p2.balance = 1000.0

        n1 = self.game.add_policy('Policy 1', 1.0)
        n1.max_level = 5.0
        self.game.add_fund(p1, n1, 10)
        self.game.add_fund(p2, n1, 5)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 990.0)
        self.assertEqual(p2.balance, 995.0)
        self.assertEqual(n1.balance, 5.0)

    def testGameTransferFundsComplex(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        p2 = self.game.create_player('Simon')
        p2.balance = 1000.0
        p3 = self.game.create_player('Rich')
        p3.balance = 1000.0
    
        n1 = self.game.add_policy('Policy 1', 1.0)
        n2 = self.game.add_policy('Policy 2', 1.0)

        self.game.add_fund(p1, n1, 10)
        self.game.add_fund(p2, n1, 20)
        self.game.add_fund(p3, n1, 50)

        self.game.add_fund(p2, n2, 50)
        self.game.add_fund(p3, n2, 40)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 990.0)
        self.assertEqual(p2.balance, 930.0)
        self.assertEqual(p3.balance, 910.0)
        self.assertEqual(n1.balance, 80.0)
        self.assertEqual(n2.balance, 90.0)

        self.assertEqual(len(n1.parents()), 3)
        self.assertEqual(len(n2.parents()), 2)


    def testAllocateFundsMultiplePolicies(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        n1 = self.game.add_policy('Policy 1', 1.0)
        n2 = self.game.add_policy('Policy 2', 1.0) 

        self.assertEqual(p1.balance, 1000.0)
        self.assertEqual(n1.balance, 0.0)
        self.assertEqual(n2.balance, 0.0)

        p1.transfer_funds()

        self.assertEqual(p1.balance, 1000.0)
        self.assertEqual(n1.balance, 0.0)
        self.assertEqual(n2.balance, 0.0)

        self.game.add_fund(p1, n1, 10)
        self.game.add_fund(p1, n2, 30)

        p1.transfer_funds()

        self.assertEqual(p1.balance, 960.0)
        self.assertEqual(n1.balance, 10.0)
        self.assertEqual(n2.balance, 30.0)

    def testGameLeak100(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        n2 = self.game.add_policy('Policy 2', 1.0)
        p1 = self.game.create_player('Matt')
        n1.wallet = Wallet([(p1.id, 100.0)])
        n2.wallet = Wallet([(p1.id, 100.0)])

        self.assertEqual(n1.balance, 100.0)
        self.assertEqual(n2.balance, 100.0)

        self.game.do_leak()
        self.assertEqual(n1.balance, 0.0)
        self.assertEqual(n2.balance, 0.0)

    def testGameLeak0_100(self):
        n1 = self.game.add_policy('Policy 1', 0.0)
        n2 = self.game.add_policy('Policy 2', 1.0)
        p1 = self.game.create_player('Matt')
        n1.wallet = Wallet([(p1.id, 100.0)])
        n2.wallet = Wallet([(p1.id, 100.0)])

        self.assertEqual(n1.balance, 100.0)
        self.assertEqual(n2.balance, 100.0)

        self.game.do_leak()
        self.assertEqual(n1.balance, 100.0)
        self.assertEqual(n2.balance, 0.0)

    def testGameLeak50(self):
        n1 = self.game.add_policy('Policy 1', 0.5)
        n2 = self.game.add_policy('Policy 2', 0.2)
        p1 = self.game.create_player('Matt')
        n1.wallet = Wallet([(p1.id, 100.0)])
        n2.wallet = Wallet([(p1.id, 100.0)])

        self.assertEqual(n1.balance, 100.0)
        self.assertEqual(n2.balance, 100.0)

        self.game.do_leak()
        self.assertAlmostEqual(n1.balance, 50.0)
        self.assertAlmostEqual(n2.balance, 80.0)

        self.game.do_leak()
        self.assertAlmostEqual(n1.balance, 25.0)
        self.assertAlmostEqual(n2.balance, 64.0)

    def testGameGetWallets(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        p2 = self.game.create_player('Simon')
        p2.balance = 1000.0
        n1 = self.game.add_policy('Policy 1', 1.0)

        self.game.add_fund(p1, n1, 100)
        self.game.add_fund(p2, n1, 90)
        p1.transfer_funds()
        p2.transfer_funds()

        self.assertEqual(p1.balance, 900.0)
        self.assertEqual(p2.balance, 910.0)
        self.assertEqual(n1.balance, 190.0)

        self.assertEqual(len(n1.parents()), 2)

        expected = {p1.id: 100.0,
                    p2.id: 90.0,}

        wallets = self.game.get_wallets_by_location(n1.id)

        self.assertEqual(wallets, expected)

    def testFundPlayers(self):
        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')
        p3 = self.game.create_player('Rich')

        self.game.do_replenish_budget()

        self.assertAlmostEqual(p1.balance, self.game.money_per_budget_cycle)
        self.assertAlmostEqual(p2.balance, self.game.money_per_budget_cycle)
        self.assertAlmostEqual(p3.balance, self.game.money_per_budget_cycle)

        n1 = self.game.add_policy('Policy 1', 1.0)

        p1.transfer_funds_to_node(n1, 100)
        p2.transfer_funds_to_node(n1, 200)
        p3.transfer_funds_to_node(n1, 400)

        self.assertAlmostEqual(p1.balance, self.game.money_per_budget_cycle-100)
        self.assertAlmostEqual(p2.balance, self.game.money_per_budget_cycle-200)
        self.assertAlmostEqual(p3.balance, self.game.money_per_budget_cycle-400)

        self.assertAlmostEqual(n1.balance, 100+200+400)

        self.game.do_replenish_budget()

        self.assertAlmostEqual(p1.balance, self.game.money_per_budget_cycle-100)
        self.assertAlmostEqual(p2.balance, self.game.money_per_budget_cycle-200)
        self.assertAlmostEqual(p3.balance, self.game.money_per_budget_cycle-400)

        self.assertAlmostEqual(p1.unclaimed_budget, self.game.money_per_budget_cycle)
        self.assertAlmostEqual(p2.unclaimed_budget, self.game.money_per_budget_cycle)
        self.assertAlmostEqual(p3.unclaimed_budget, self.game.money_per_budget_cycle)


        self.assertAlmostEqual(n1.balance, 100+200+400)
        

    def testGameTransfer15_30(self):
        n1 = self.game.add_policy('Policy 1', 0.5)
        n2 = self.game.add_policy('Policy 2', 0.5)
        n3 = self.game.add_policy('Policy 3', 0.5)
        p1 = self.game.create_player('Matt')
        l1 = self.game.add_link(n1, n2, 15.0)
        l2 = self.game.add_link(n1, n3, 30.0)

        self.game.do_replenish_budget()

        p1.transfer_funds_to_node(n1, 100)

        self.assertEqual(n1.balance, 100)
        self.assertEqual(n2.balance, 0)
        self.assertEqual(n3.balance, 0)
        
        self.game.do_propogate_funds()

        self.assertAlmostEqual(n1.balance, 55.0)
        self.assertAlmostEqual(n2.balance, 15.0)
        self.assertAlmostEqual(n3.balance, 30.0)

        self.game.do_propogate_funds()

        self.assertAlmostEqual(n1.balance, 10.0)
        self.assertAlmostEqual(n2.balance, 30.0)
        self.assertAlmostEqual(n3.balance, 60.0)


    def testGameTransfer50_goal(self):
        n1 = self.game.add_policy('Policy 1', 0.5)
        n2 = self.game.add_policy('Policy 2', 0.5)
        n3 = self.game.add_policy('Policy 3', 0.5)
        g1 = self.game.add_goal('Goal 1', 0.5)
        g2 = self.game.add_goal('Goal 2', 0.5)
        g3 = self.game.add_goal('Goal 3', 0.5)
        p1 = self.game.create_player('Matt')

        l1 = self.game.add_link(n1, n2, 4.0)
        l2 = self.game.add_link(n1, n3, 3.0)

        l3 = self.game.add_link(n2, g1, 1.0)
        l4 = self.game.add_link(n3, g2, 3.0)
        l5 = self.game.add_link(n3, g3, 5.0)

        self.game.do_replenish_budget()

        self.assertEqual(n1.balance, 0)
        self.assertEqual(n2.balance, 0)
        self.assertEqual(n3.balance, 0)

        self.assertEqual(g1.balance, 0)
        self.assertEqual(g2.balance, 0)
        self.assertEqual(g3.balance, 0)

        for i in range(200):
            p1.transfer_funds_to_node(n1, 10)
            p1.transfer_funds_to_node(n2, 10)
            p1.transfer_funds_to_node(n3, 10)
            self.game.do_propogate_funds()

        self.assertAlmostEqual(n1.balance, 600.0)
        self.assertAlmostEqual(n2.balance, 2600.0)
        self.assertAlmostEqual(n3.balance, 1000.0)

        self.assertAlmostEqual(g1.balance, 200.0)
        self.assertAlmostEqual(g2.balance, 600.0)
        self.assertAlmostEqual(g3.balance, 1000.0)


    def testSimpleNetwork(self):
        p1 = self.game.create_player('Player 1')
        p1.balance = 1000
        po1 = self.game.add_policy('Policy 1', 0.0)
        g1 = self.game.add_goal('Goal 1', 0.0)
        g2 = self.game.add_goal('Goal 2', 0.0)

        l1 = self.game.add_link(po1, g1, 3.0)
        l2 = self.game.add_link(po1, g2, 4.0)

        

        p1.transfer_funds_to_node(po1, 10)

        self.game.do_propogate_funds()

        self.assertAlmostEqual(p1.balance, 990)

        self.assertAlmostEqual(g1.balance, 3.0)
        self.assertAlmostEqual(g2.balance, 4.0)

    def testSimpleNetworkLessThanBalance(self):
        p1 = self.game.create_player('Player 1')
        p1.balance = 1000
        po1 = self.game.add_policy('Policy 1', 0.0)
        g1 = self.game.add_goal('Goal 1', 0.0)
        g2 = self.game.add_goal('Goal 2', 0.0)

        l1 = self.game.add_link(po1, g1, 10.0)
        l2 = self.game.add_link(po1, g2, 40.0)

        p1.transfer_funds_to_node(po1, 10)

        self.game.do_propogate_funds()

        self.assertAlmostEqual(p1.balance, 990)

        self.assertAlmostEqual(g1.balance, 2.0)
        self.assertAlmostEqual(g2.balance, 8.0)

    def testSimpleNetworkTwoWallets(self):
        p1 = self.game.create_player('Player 1')
        p1.balance = 1000
        p2 = self.game.create_player('Player 2')
        p2.balance = 1000
        po1 = self.game.add_policy('Policy 1', 0.0)
        g1 = self.game.add_goal('Goal 1', 0.0)
        g2 = self.game.add_goal('Goal 2', 0.0)

        l1 = self.game.add_link(po1, g1, 3.0)
        l2 = self.game.add_link(po1, g2, 5.0)

        p1.transfer_funds_to_node(po1, 10)
        p2.transfer_funds_to_node(po1, 30)

        self.game.do_propogate_funds()

        self.assertAlmostEqual(p1.balance, 990)
        self.assertAlmostEqual(p2.balance, 970)

        self.assertAlmostEqual(g1.balance, 3.0)
        self.assertEqual(g1.wallet_owner_map, {p1.id: 0.75,
                                               p2.id: 2.25})
        
        self.assertAlmostEqual(g2.balance, 5.0)
        self.assertEqual(g2.wallet_owner_map, {p1.id: 1.25,
                                               p2.id: 3.75})

    def testSimpleNetworkTwoWalletsLessThanBalance(self):
        p1 = self.game.create_player('Player 1')
        p1.balance = 1000
        p2 = self.game.create_player('Player 2')
        p2.balance = 1000
        po1 = self.game.add_policy('Policy 1', 0.0)
        g1 = self.game.add_goal('Goal 1', 0.0)
        g2 = self.game.add_goal('Goal 2', 0.0)

        l1 = self.game.add_link(po1, g1, 3.0)
        l2 = self.game.add_link(po1, g2, 5.0)

        p1.transfer_funds_to_node(po1, 1)
        p2.transfer_funds_to_node(po1, 3)

        self.assertAlmostEqual(p1.balance, 999)
        self.assertAlmostEqual(p2.balance, 997)
        self.assertAlmostEqual(po1.balance, 4)

        self.game.do_propogate_funds()

        self.assertAlmostEqual(g1.balance, 1.5)
        self.assertEqual(g1.wallet_owner_map, {p1.id: 0.375,
                                               p2.id: 1.125})
        
        self.assertAlmostEqual(g2.balance, 2.5)
        self.assertEqual(g2.wallet_owner_map, {p1.id: 0.625,
                                               p2.id: 1.875})
        

    def testSimplePlayerCoinsNetwork(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_fund(p1, po1, 50)

        self.assertEqual(p1.balance, 1000)
        self.assertEqual(po1.balance, 0)

        p1.transfer_funds_to_node(po1, 60)
        self.assertEqual(po1.balance, 60)

        self.assertEqual(p1.balance, 940)
        self.assertEqual(po1.balance, 60)

    def testTransferPartialFunds(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_fund(p1, po1, 100.0)

        g1 = self.game.add_goal('World Peace', 1.0)
        l1 = self.game.add_link(po1, g1, 1.0)

        

        self.game.do_propogate_funds()
        
        self.assertEqual(p1.balance, 900)
        self.assertEqual(po1.balance, 99.0)
        self.assertEqual(g1.balance, 1.0)

    def testTransferFullFunds(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_fund(p1, po1, 100.0)

        g1 = self.game.add_goal('World Peace', 1.0)
        l1 = self.game.add_link(po1, g1, 2.0)

        

        self.game.do_propogate_funds()
        
        self.assertEqual(p1.balance, 900)
        self.assertEqual(po1.balance, 98.0)
        self.assertEqual(g1.balance, 2.0)
        

    def testTransferGreaterThan100_300(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_fund(p1, po1, 3.0)

        self.assertEqual(p1.balance, 1000)
        self.assertEqual(po1.balance, 0)

        for x in range(50):
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 850)
        self.assertEqual(po1.balance, 150)


    def testTransferSlowFunds(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_fund(p1, po1, 1.0)

        g1 = self.game.add_goal('World Peace', 1.0)
        l1 = self.game.add_link(po1, g1, 2.0)

        

        self.game.do_propogate_funds()
        
        self.assertEqual(p1.balance, 999)
        self.assertEqual(po1.balance, 0.0)
        self.assertEqual(g1.balance, 1.0)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 998)
        self.assertEqual(po1.balance, 0.0)
        self.assertEqual(g1.balance, 2.0)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 997)
        self.assertEqual(po1.balance, 0.0)
        self.assertEqual(g1.balance, 3.0)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 996)
        self.assertEqual(po1.balance, 0.0)
        self.assertEqual(g1.balance, 4.0)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 995)
        self.assertEqual(po1.balance, 0.0)
        self.assertEqual(g1.balance, 5.0)
        
    def testTransferFastFunds(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_link(p1, po1, 3.0)

        g1 = self.game.add_goal('World Peace', 1.0)
        l1 = self.game.add_link(po1, g1, 1.0)

        

        self.game.do_propogate_funds()
        
        self.assertEqual(p1.balance, 997)
        self.assertEqual(po1.balance, 2.0)
        self.assertEqual(g1.balance, 1.0)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 994)
        self.assertEqual(po1.balance, 4.0)
        self.assertEqual(g1.balance, 2.0)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 991)
        self.assertEqual(po1.balance, 6.0)
        self.assertEqual(g1.balance, 3.0)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 988)
        self.assertEqual(po1.balance, 8.0)
        self.assertEqual(g1.balance, 4.0)

        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 985)
        self.assertEqual(po1.balance, 10.0)
        self.assertEqual(g1.balance, 5.0)
        

    def testMoreComplexPlayerCoinsNetwork(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_fund(p1, po1, 0.5)
        po2 = self.game.add_policy('Pollution control', 0.1)
        self.game.add_fund(p1, po2, 1.0)

        g1 = self.game.add_goal('World Peace', 0.5)
        g2 = self.game.add_goal('Clean Water', 0.5)
        l3 = self.game.add_link(po1, g1, 1.0)
        l4 = self.game.add_link(po2, g2, 2.0)

        

        self.assertEqual(p1.balance, 1000)
        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 850)
        self.assertEqual(po1.balance, 0)
        self.assertEqual(po2.balance, 0)

        self.assertEqual(g1.balance, 50)
        self.assertEqual(g2.balance, 100)

    def testMoreComplexPlayerCoinsNetworkWithFullTick(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 5000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_fund(p1, po1, 10.0)
        po2 = self.game.add_policy('Pollution control', 0.1)
        self.game.add_fund(p1, po2, 15.0)

        g1 = self.game.add_goal('World Peace', 0.5)
        g2 = self.game.add_goal('Clean Water', 0.5)
        l3 = self.game.add_link(po1, g1, 5.0)
        l4 = self.game.add_link(po2, g2, 9.0)

        self.assertEqual(p1.balance, 5000)
        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.tick()

        self.assertEqual(p1.balance, 2500)
        self.assertAlmostEqual(po1.balance, 50, 2)
        self.assertAlmostEqual(po2.balance, 60, 2)

        self.assertEqual(g1.balance, 10.0)
        self.assertEqual(g2.balance, 18.0)

    def testTwoPlayersFundAPolicyEqually(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000
        p2 = self.game.create_player('Simon')
        p2.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_fund(p1, po1, 1.0)
        self.game.add_fund(p2, po1, 1.0)

        

        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 900)
        self.assertEqual(p2.balance, 900)

        self.assertEqual(po1.balance, 200)


    def testActivationLevelLow(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        po1.activation = 0.2
        g1 = self.game.add_goal('World Peace', 0.5)
        self.game.add_fund(p1, po1, 5.0)
        l2 = self.game.add_link(po1, g1, 1.0)

        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 500.0)
        self.assertEqual(po1.balance, 500.0)
        self.assertEqual(g1.balance, 0.0)

    def testActivationLevelHigh(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 10000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        po1.activation = 0.2
        g1 = self.game.add_goal('World Peace', 0.5)
        self.game.add_fund(p1, po1, 250.0)
        l2 = self.game.add_link(po1, g1, 1.0)

        self.assertEqual(po1.balance, 0)

        for x in range(10):
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 7500)
        self.assertEqual(po1.balance, 2490)
        self.assertEqual(g1.balance, 10)

    def testGetFunding(self):
        self.add_20_goals_and_policies()
        random.seed(0)
        name = 'Matt'
        player = self.game.create_player(name)
        id = player.id

        funding = []
        
        for amount,edge in enumerate(player.lower_edges):
            edge.weight = amount
            dest_id = edge.higher_node.id
            funding.append({'from_id':id, 'to_id': dest_id, 'amount': amount})

        data = self.game.get_funding(id)
        self.assertEqual(funding, data)

    def testSetFunding(self):

        for x in range(5):
            p = self.game.add_policy("P{}".format(x), 0.5)
            p.id = "P{}".format(x)

        random.seed(0)

        name = 'Matt'
        player = self.game.create_player(name)
        id = player.id

        funding = []
        data = self.game.get_funding(id)

        self.assertEqual([ x['amount'] for x in data ], [0,0,0,0,0])

        for x in range(5):
            data[x]['amount'] = x
            
        self.game.set_funding(id, data)

        data2 = self.game.get_funding(id)

        self.assertEqual(data, data2)

    def testCreateTable(self):
        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')
        table = self.game.create_table('table a')

        self.assertEqual(table.players, [])

        table.players.append(p1)
        
        self.assertEqual(table.players, [p1,])
        self.assertEqual(p1.table.id, table.id)

        p2.table = table

        self.assertEqual(table.players, [p1,p2])
        self.assertEqual(p2.table.id, table.id)

        p1.table = None

        self.assertEqual(table.players, [p2,])
        

    @unittest.skip("needs fixing after network re-jig")
    def testGetNetworkForTable(self):

        data = json.load(open('examples/network.json', 'r'))
        self.game.create_network(data)
        random.seed(0)
        
        t1 = self.game.create_table('T1')

        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')
        p3 = self.game.create_player('Richard')

        table_uuid = default_uuid()

        self.assertEqual(self.game.get_network_for_table('nonexistant'), None)

        table = self.game.get_network_for_table(t1.id)
        self.assertEqual(len(table['goals']), 6)
        self.assertEqual(len(table['policies']), 30)

        t1.players.append(p1)

        table = self.game.get_network_for_table(t1.id)
        self.assertEqual(len(table['goals']), 1)
        self.assertEqual(len(table['policies']), 5)

        t1.players.append(p2)

        table = self.game.get_network_for_table(t1.id)
        self.assertEqual(len(table['goals']), 2)
        self.assertEqual(len(table['policies']), 7)

        p2.table = None

        table = self.game.get_network_for_table(t1.id)
        self.assertEqual(len(table['goals']), 1)
        self.assertEqual(len(table['policies']), 5)

    def testTopPlayers(self):
        random.seed(0)
        g1 = self.game.add_goal('G1', 0.0)
        g2 = self.game.add_goal('G2', 0.0)

        p1 = self.game.create_player('Matt')
        p1.goal = g1
        p2 = self.game.create_player('Simon')
        p2.goal = g1
        p3 = self.game.create_player('Richard')
        p3.goal = g2

        self.game.add_fund(p1, g1, 10)
        self.game.add_fund(p2, g1, 20)
        self.game.add_fund(p2, g2, 40)
        self.game.add_fund(p3, g2, 15)

        self.game.tick()

        self.assertEqual(p1.balance, 1499990)
        self.assertEqual(p2.balance, 1499940)
        self.assertEqual(p3.balance, 1499985)

        p1.calc_goal_funded()
        p2.calc_goal_funded()
        p3.calc_goal_funded()

        top = self.game.top_players()
        self.assertEqual(top, [p2,p3,p1])

        self.game.add_fund(p1, g1, 100)

        self.game.tick()

        p1.calc_goal_funded()
        p2.calc_goal_funded()
        p3.calc_goal_funded()

        top = self.game.top_players()
        self.assertEqual(top, [p1,p2,p3])

    def testGoalFunded(self):
        g1 = self.game.add_goal('G1', 0.0)
        g2 = self.game.add_goal('G2', 0.0)

        p1 = self.game.create_player('Matt')
        p1.goal = g1
        
        self.assertEqual(p1.goal_funded, 0)

        self.game.add_fund(p1, g1, 10)
        self.game.add_fund(p1, g2, 30)

        self.game.tick()
        p1.calc_goal_funded()

        self.assertEqual(p1.balance, 1499960)
        self.assertEqual(p1.goal_funded, 10)

        self.game.tick()
        p1.calc_goal_funded()

        self.assertEqual(p1.goal_funded, 20)

    def testOfferPolicy(self):
        p1 = self.game.create_player('Matt')
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        p1.fund(po1, 0)

        data = self.game.offer_policy(p1.id, po1.id, 5000)

        self.assertEqual(data['seller_id'], p1.id)
        self.assertEqual(data['policy_id'], po1.id)
        self.assertEqual(data['price'], 5000)
        self.assertEqual(len(data['checksum']), 40)

    def testBuyPolicy(self):
        
        seller = self.game.create_player('Matt')
        buyer = self.game.create_player('Simon')

        self.assertEqual(seller.balance, 1500000)
        self.assertEqual(buyer.balance, 1500000)

        p1 = self.game.add_policy('Policy 1', 0)
        
        seller.fund(p1, 0)
        self.assertIn(p1, seller.children())
        self.assertNotIn(p1, buyer.children())

        offer = self.game.offer_policy(seller.id, p1.id, 20000)
        self.game.buy_policy(buyer.id, offer)

        self.assertIn(p1, buyer.children())
        self.assertIn(p1, seller.children())
        self.assertEqual(seller.balance, 1500000+20000)
        self.assertEqual(buyer.balance, 1500000-20000)
        
    def testBuyPolicyFailDupe(self):
        
        seller = self.game.create_player('Matt')
        buyer = self.game.create_player('Simon')

        self.assertEqual(seller.balance, 1500000)
        self.assertEqual(buyer.balance, 1500000)

        p1 = self.game.add_policy('Policy 1', 0)
        
        seller.fund(p1, 0)
        buyer.fund(p1, 0)
        self.assertIn(p1, seller.children())
        self.assertIn(p1, buyer.children())

        offer = self.game.offer_policy(seller.id, p1.id, 20000)
        with self.assertRaises(ValueError):
            self.game.buy_policy(buyer.id, offer)

        self.assertIn(p1, buyer.children())
        self.assertIn(p1, seller.children())
        self.assertEqual(seller.balance, 1500000)
        self.assertEqual(buyer.balance, 1500000)
        
    def testBuyPolicyFailNoFunds(self):
        
        seller = self.game.create_player('Matt')
        buyer = self.game.create_player('Simon')

        self.assertEqual(seller.balance, 1500000)
        self.assertEqual(buyer.balance, 1500000)

        p1 = self.game.add_policy('Policy 1', 0)
        
        seller.fund(p1, 0)
        self.assertIn(p1, seller.children())
        self.assertNotIn(p1, buyer.children())

        offer = self.game.offer_policy(seller.id, p1.id, 2000000)
        with self.assertRaises(ValueError):
            self.game.buy_policy(buyer.id, offer)

        self.assertNotIn(p1, buyer.children())
        self.assertIn(p1, seller.children())
        self.assertEqual(seller.balance, 1500000)
        self.assertEqual(buyer.balance, 1500000)
        
    def testBuyPolicyFailNoPolicy(self):
        
        seller = self.game.create_player('Matt')
        buyer = self.game.create_player('Simon')

        self.assertEqual(seller.balance, 1500000)
        self.assertEqual(buyer.balance, 1500000)

        p1 = self.game.add_policy('Policy 1', 0)
        
        self.assertNotIn(p1, seller.children())
        self.assertNotIn(p1, buyer.children())

        with self.assertRaises(ValueError):
            offer = self.game.offer_policy(seller.id, p1.id, 20000)
            self.game.buy_policy(buyer.id, offer)

        self.assertNotIn(p1, buyer.children())
        self.assertNotIn(p1, seller.children())
        self.assertEqual(seller.balance, 1500000)
        self.assertEqual(buyer.balance, 1500000)

    def testGameStartStop(self):
        self.assertFalse(self.game.is_running())

        year = self.game.start(2017)
        self.assertEqual(year, 2017)

        self.assertTrue(self.game.is_running())

        year = self.game.stop()
        self.assertEqual(year, 2017)

        self.assertFalse(self.game.is_running())

    def testMessages(self):
        messages = self.game.get_messages()
        self.assertEqual(len(messages), 0)
        
        t1 = datetime.now()
        m1 = self.game.add_message(t1, "policy", "message 1")

        messages = self.game.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].timestamp, t1)
        self.assertEqual(messages[0].message, "message 1")
        self.assertEqual(messages[0].type, "policy")

        t2 = datetime.now()
        m2 = self.game.add_message(t2, "event", "message 2")
        messages = self.game.get_messages()

        self.assertEqual(len(messages), 2)
        
        self.game.clear_messages()
        messages = self.game.get_messages()
        self.assertEqual(len(messages), 0)
        
    def testClaimBudget(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000
        p1.unclaimed_budget = 1500000

        p1.claim_budget()

        self.assertEqual(p1.balance, 1500000)
        self.assertEqual(p1.unclaimed_budget, 0)

        # 2nd claim with no unclaimed budget should do no-op
        p1.balance = 1400000
        p1.claim_budget()

        self.assertEqual(p1.balance, 1400000)
        self.assertEqual(p1.unclaimed_budget, 0)
        

class DataLoadTests(DBTestCase):

    def testCreateNetwork(self):
        json_file = open('examples/example-network.json', 'r')
        self.game.create_network(json.load(json_file))
        self.assertEqual(80, db_session.query(Edge).count())
        self.assertEqual(44, db_session.query(Node).count())
        self.assertEqual(37, db_session.query(Policy).count())
        self.assertEqual(7, db_session.query(Goal).count())

    def testGetNetwork(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 5000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_fund(p1, po1, 10.0)
        po2 = self.game.add_policy('Pollution control', 0.1)
        self.game.add_fund(p1, po2, 15.0)

        g1 = self.game.add_goal('World Peace', 0.5)
        g2 = self.game.add_goal('Clean Water', 0.5)
        g3 = self.game.add_goal('Equal Rights', 0.2)
        l3 = self.game.add_link(po1, g1, 5.0)
        l4 = self.game.add_link(po2, g2, 9.0)

        self.assertEqual(p1.balance, 5000)
        self.assertEqual(po1.balance, 0)

        for x in range(20):
            self.game.tick()
        
        network = self.game.get_network()

        policies = network['policies']
        goals = network['goals']

        self.assertEqual(len(policies), 2)
        self.assertEqual(len(goals), 3)

        # todo: add more tests here

    def testClearNetwork(self):
        json_file = open('examples/example-network.json', 'r')
        self.game.create_network(json.load(json_file))
        self.assertEqual(80, db_session.query(Edge).count())
        self.assertEqual(44, db_session.query(Node).count())
        self.assertEqual(37, db_session.query(Policy).count())
        self.assertEqual(7, db_session.query(Goal).count())

        self.game.clear_network()
        self.assertEqual(0, db_session.query(Edge).count())
        self.assertEqual(0, db_session.query(Node).count())
        self.assertEqual(0, db_session.query(Policy).count())
        self.assertEqual(0, db_session.query(Goal).count())


    def testGetWallets(self):
        self.add_20_goals_and_policies()

        random.seed(0)

        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')

        data = self.game.get_funding(p1.id)
        for x in range(5):
            data[x]['amount'] = x
        self.game.set_funding(p1.id, data)

        data = self.game.get_funding(p2.id)
        for x in range(5):
            data[x]['amount'] = x
        self.game.set_funding(p2.id, data)

        self.game.do_propogate_funds()

        nodes = set(p1.children() + p2.children())

        wallets = []
        for n in nodes:
            for player_id,amount in n.wallet.todict().items():
                wallets.append(dict(location=n.id,
                                    owner=self.game.get_player(player_id).name,
                                    balance=float("{:.2f}".format(amount))))
                
        expected = [{'balance': 3.0, 'location': u'P11', 'owner': 'Matt'},
                    {'balance': 1.0, 'location': u'P18', 'owner': 'Matt'},
                    {'balance': 1.0, 'location': u'P12', 'owner': 'Simon'},
                    {'balance': 4.0, 'location': u'P15', 'owner': 'Simon'},
                    {'balance': 3.0, 'location': u'P5', 'owner': 'Simon'},
                    {'balance': 2.0, 'location': u'P6', 'owner': 'Matt'},
                    {'balance': 4.0, 'location': u'P4', 'owner': 'Matt'},
                    {'balance': 2.0, 'location': u'P17', 'owner': 'Simon'}]

        self.assertEqual(sorted(expected), sorted(wallets))


class GameTests(DBTestCase):
    
    def testGetNonexistantPlayer(self):
        player = self.game.get_player('nonexistant')
        self.assertIsNone(player)

class RestAPITests(DBTestCase):

    def testTick(self):
        headers = {'X-API-KEY': self.api_key}
        response = self.client.put("/v1/game/tick",
                                   headers=headers,
                                   content_type='application/json')
        self.assertEquals(response.status_code, 200)

    def testPlayerFunding(self):
        headers = {'X-API-KEY': self.api_key}

        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        p2 = self.game.create_player('Simon')
        p2.balance = 0
        n1 = self.game.add_policy('Policy 1', 1.0)
        n2 = self.game.add_policy('Policy 2', 1.0)
        self.game.add_fund(p1, n1, 100)
        self.game.add_fund(p1, n2, 100)
        self.game.add_fund(p2, n2, 200)

        # temp unavailable as not computed yet
        response = self.client.get("/v1/game/player_fundings",
                                   headers=headers,
                                   content_type='application/json')
        self.assertEquals(response.status_code, 503)

        response = self.client.put("/v1/game/tick",
                                   headers=headers,
                                   content_type='application/json')
        self.assertEquals(response.status_code, 200)

        response = self.client.get("/v1/game/player_fundings",
                                   headers=headers,
                                   content_type='application/json')
        self.assertEquals(response.status_code, 200)

        expected = [{'id': p1.id,
                     'name': p1.name,
                     'funding': [{'id': n1.id,
                                  'amount_set': 100,
                                  'amount_actual': 100},
                                 {'id': n2.id,
                                  'amount_set': 100,
                                  'amount_actual': 100,},
                                 ]},
                    {'id': p2.id,
                     'name': p2.name,
                     'funding': [{'id': n2.id,
                                  'amount_set': 200,
                                  'amount_actual': 0},
                                 ]}
                    ]

        self.assertEqual(sorted(expected), sorted(response.json))


    @unittest.skip("not implemented")
    def testGetEmptyPlayersList(self):
        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/players/", headers=headers)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json, [])

    @unittest.skip("not implemented")
    def testGetNonEmptyPlayersList(self):
        names = ['Matt', 'Simon', 'Richard']
        cp = self.game.create_player
        players = [ cp(name) for name in names ]
        data = [ dict(name=p.name, id=p.id) for p in players ]

        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/players/", headers=headers)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json, data)

    def testGetSpecificPlayer(self):
        name = 'Matt'
        player = self.game.create_player(name)
        id = player.id
        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/players/{}".format(id), headers=headers)
        self.assertEquals(response.status_code, 200)
        self.assertDictContainsSubset(dict(name=name, id=id), response.json)
        self.assertFalse(response.json.has_key('token'))

    def testGetNonExistentPlayer(self):
        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/players/nobody", headers=headers)
        self.assertEquals(response.status_code, 404)

    def testCreateNewPlayerBadGameId(self):
        data = dict(name='Matt', game_id='dummy')

        num1 = db_session.query(Player).count()

        headers = {'X-API-KEY': self.api_key}
        response = self.client.post("/v1/players/", data=json.dumps(data),
                                    headers=headers,
                                    content_type='application/json')
        self.assertEquals(response.status_code, 404)

        num2 = db_session.query(Player).count()
        self.assertEqual(num1, num2)

    def testCreateNewPlayer(self):
        data = dict(name='Matt', game_id='Global Festival of Ideas for Sustainable Development')

        headers = {'X-API-KEY': self.api_key}
        response = self.client.post("/v1/players/", data=json.dumps(data),
                                    headers=headers,
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)
        id = response.json['id']
        token = response.json['token']

        player = self.game.get_player(id)
        self.assertEquals(id, player.id)
        self.assertEquals(token, player.token)

    def testCreateThenGetNewPlayer(self):
        name = 'Matt {}'.format(time.time())
        data = dict(name=name, game_id=GAME_ID)
        headers = {'X-API-KEY': self.api_key}
        response = self.client.post("/v1/players/", data=json.dumps(data),
                                    headers=headers,
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)
        id = response.json['id']

        response = self.client.get("/v1/players/{}".format(id), headers=headers)
        self.assertEquals(response.status_code, 200)
        self.assertDictContainsSubset(dict(name=name, id=id), response.json)
        self.assertFalse(response.json.has_key('token'))

    def testCreateThenGetNewPlayerWithNodes(self):
        # create some nodes first
        self.add_20_goals_and_policies()

        random.seed(0)
        name = 'Matt {}'.format(time.time())
        data = dict(name=name, game_id=GAME_ID)
        db_session.begin(subtransactions=True)
        headers = {'X-API-KEY': self.api_key}
        response = self.client.post("/v1/players/", data=json.dumps(data),
                                    headers=headers,
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)
        id = response.json['id']

        response = self.client.get("/v1/players/{}".format(id), headers=headers)
        self.assertEquals(response.status_code, 200)
        self.assertDictContainsSubset(dict(name=name, id=id), response.json)
        self.assertEquals(response.json['goal']['id'], 'G6')
        policies = response.json['policies']
        policies = [ x['id'] for x in policies ] 
        policies.sort()
        self.assertEquals(policies, ['P0', 'P11', 'P18', 'P4', 'P6'])
        self.assertFalse(response.json.has_key('token'))

        name = 'Simon {}'.format(time.time())
        data = dict(name=name, game_id=GAME_ID)
        response = self.client.post("/v1/players/", data=json.dumps(data),
                                    headers=headers,
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)
        id = response.json['id']

        response = self.client.get("/v1/players/{}".format(id), headers=headers)
        self.assertEquals(response.status_code, 200)
        self.assertDictContainsSubset(dict(name=name, id=id), response.json)
        self.assertEquals(response.json['goal']['id'], 'G14')
        policies = response.json['policies']
        policies = [ x['id'] for x in policies ] 
        policies.sort()
        self.assertEquals(policies, ['P12', 'P15', 'P17', 'P18','P5'])
        self.assertFalse(response.json.has_key('token'))

    @unittest.skip("needs fixing after network re-jig")
    def testGetNetwork(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 5000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        self.game.add_fund(p1, po1, 10.0)
        po2 = self.game.add_policy('Pollution control', 0.1)
        self.game.add_fund(p1, po2, 15.0)

        g1 = self.game.add_goal('World Peace', 0.5)
        g2 = self.game.add_goal('Clean Water', 0.5)
        g3 = self.game.add_goal('Equal Rights', 0.2)
        l3 = self.game.add_link(po1, g1, 5.0)
        l4 = self.game.add_link(po2, g2, 9.0)

        self.assertEqual(p1.balance, 5000)
        self.assertEqual(po1.balance, 0)

        for x in range(20):
            self.game.tick()

        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/network/", headers=headers)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.json['policies']), 2)
        self.assertEquals(len(response.json['goals']), 3)

    def testCreateNetwork(self):
        data = json.load(open('examples/example-network.json', 'r'))

        headers = {'X-API-KEY': self.api_key}
        response = self.client.post("/v1/network/", data=json.dumps(data),
                                    headers=headers,
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)

        self.assertEqual(80, db_session.query(Edge).count())
        self.assertEqual(44, db_session.query(Node).count())
        self.assertEqual(37, db_session.query(Policy).count())
        self.assertEqual(7, db_session.query(Goal).count())

    @unittest.skip("needs fixing after network re-jig")
    def testCreateThenGetNetwork(self):
        data = json.load(open('examples/example-network.json', 'r'))

        headers = {'X-API-KEY': self.api_key}
        response = self.client.post("/v1/network/", data=json.dumps(data),
                                    headers=headers,
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)

        response = self.client.get("/v1/network/", headers=headers)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.json['policies']), 37)
        self.assertEquals(len(response.json['goals']), 7)

        self.assertEqual(data, response.json)

    def testUpdateNetwork(self):
        data = json.load(open('examples/example-network.json', 'r'))

        self.game.create_network(data)

        self.assertEqual(80, db_session.query(Edge).count())
        self.assertEqual(44, db_session.query(Node).count())
        self.assertEqual(37, db_session.query(Policy).count())
        self.assertEqual(7, db_session.query(Goal).count())

        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/network/", headers=headers)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.json['policies']), 37)
        self.assertEquals(len(response.json['goals']), 7)

        expected = response.json
        e = expected['goals'][0]

        e['short_name'] = 'new short name'
        e['group'] = 1
        e['name'] = 'long name'
        e['max_amount'] = 100.0
        e['activation_amount'] = 10.0
        e['leakage'] = 0.2

        id_ = e['id']

        response2 = self.client.put("/v1/network/", data=json.dumps(expected),
                                    headers=headers,
                                    content_type='application/json')
        self.assertEquals(response2.status_code, 200)
        d = { x['id']: x for x in response2.json['goals'] }
        self.assertEqual(d[id_]['short_name'], 'new short name')
        # remove generation time
        del expected['generated']
        self.assertEqual(sorted(expected), sorted(response2.json))

    def testCreateTable(self):
        data = {'name': 'Table A'}
        headers = {'X-API-KEY': self.api_key}
        response = self.client.post("/v1/tables/", data=json.dumps(data),
                                    headers=headers,
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)
        self.assertEquals(response.json['name'], 'Table A')
        self.assertEquals(response.json['players'], [])

        id = response.json['id']
        self.assertEquals(self.game.get_table(id).id, id)

    def testDeleteTable(self):
        table = self.game.create_table('Table A')
        id = table.id

        headers = {'X-API-KEY': self.api_key}
        response = self.client.delete("/v1/tables/{}".format(id),
                                    headers=headers,
                                    content_type='application/json')
        self.assertEquals(response.status_code, 200)
        self.assertEquals(self.game.get_table(id), None)

    def testGetTableEmpty(self):
        data = json.load(open('examples/example-network.json', 'r'))
        self.game.create_network(data)

        table = self.game.create_table('Table A')

        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/tables/{}".format(table.id), headers=headers)
        self.assertEquals(response.status_code, 200)
        result = response.json
        self.assertEquals(result['id'], table.id)
        self.assertEquals(result['name'], 'Table A')
        self.assertEquals(result['players'], [])
        self.assertEquals(len(result['network']['nodes']), 44)
        self.assertEquals(len(result['network']['links']), 80)

    def testGetTableWithOnePlayer(self):
        data = json.load(open('examples/example-network.json', 'r'))
        self.game.create_network(data)

        random.seed(0)
        p1 = self.game.create_player('Matt')
        p1.fund(p1.policies[0], 10)

        table = self.game.create_table('Table A')
        table.players.append(p1)

        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/tables/{}".format(table.id), headers=headers)
        self.assertEquals(response.status_code, 200)
        result = response.json
        self.assertEquals(result['id'], table.id)
        self.assertEquals(result['name'], 'Table A')
        self.assertEquals(result['players'][0]['name'], 'Matt')
        self.assertEquals(len(result['network']['nodes']), 4)
        self.assertEquals(len(result['network']['links']), 2)

    def testGetTableWithTwoPlayers(self):
        data = json.load(open('examples/example-network.json', 'r'))
        self.game.create_network(data)

        random.seed(0)
        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')
        p1.fund(p1.policies[0], 10)
        p2.fund(p2.policies[0], 10)

        table = self.game.create_table('Table A')
        table.players.append(p1)
        table.players.append(p2)

        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/tables/{}".format(table.id), headers=headers)
        self.assertEquals(response.status_code, 200)
        result = response.json
        self.assertEquals(result['id'], table.id)
        self.assertEquals(result['name'], 'Table A')
        self.assertEquals(result['players'][0]['name'], 'Matt')
        self.assertEquals(len(result['network']['nodes']), 8)
        self.assertEquals(len(result['network']['links']), 7)

    def testGetTableChecksum(self):
        data = json.load(open('examples/example-network.json', 'r'))
        self.game.create_network(data)

        random.seed(0)
        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')
        p1.fund(p1.policies[0], 10)
        p2.fund(p2.policies[0], 10)

        table = self.game.create_table('Table A')
        table.players.append(p1)

        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/tables/{}".format(table.id), headers=headers)
        self.assertEquals(response.status_code, 200)
        result = response.json
        chksum1 = result['layout_checksum']

        response = self.client.get("/v1/tables/{}".format(table.id), headers=headers)
        self.assertEquals(response.status_code, 200)
        result = response.json
        self.assertEqual(chksum1, result['layout_checksum'])

        p1.policies[0].lower_edges[0].weight = 0.5

        response = self.client.get("/v1/tables/{}".format(table.id), headers=headers)
        self.assertEquals(response.status_code, 200)
        result = response.json
        self.assertEqual(chksum1, result['layout_checksum'])

        p1.fund(p1.policies[1], 10)

        response = self.client.get("/v1/tables/{}".format(table.id), headers=headers)
        self.assertEquals(response.status_code, 200)
        result = response.json
        self.assertNotEqual(chksum1, result['layout_checksum'])



    def testGetFunding(self):
        self.add_20_goals_and_policies()
        random.seed(0)
        name = 'Matt'
        player = self.game.create_player(name)
        id = player.id

        funding = []
        for amount,edge in enumerate(player.lower_edges):
            edge.weight = amount
            dest_id = edge.higher_node.id
            funding.append({'from_id':id, 'to_id': dest_id, 'amount': amount})

        headers = {'X-USER-KEY': player.token,
                   'X-API-KEY': self.api_key}
        response = self.client.get("/v1/players/{}/funding".format(id),
                                   headers=headers)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(funding, response.json)
        
    def testGetFundingFailAuth(self):
        self.add_20_goals_and_policies()
        random.seed(0)
        name = 'Matt'
        player = self.game.create_player(name)
        id = player.id

        funding = []
        for amount,edge in enumerate(player.lower_edges):
            edge.weight = amount
            dest_id = edge.higher_node.id
            funding.append({'from_id':id, 'to_id': dest_id, 'amount': amount})

        headers = {'X-USER-KEY': 'bogus',
                   'X-API-KEY': self.api_key}
        response = self.client.get("/v1/players/{}/funding".format(id),
                                   headers=headers)
        self.assertEquals(response.status_code, 401)

    def testSetFunding(self):

        for x in range(5):
            p = self.game.add_policy("P{}".format(x), 0.5)
            p.id = "P{}".format(x)

        random.seed(0)

        name = 'Matt'
        player = self.game.create_player(name)
        id = player.id

        funding = []
        data = self.game.get_funding(id)

        self.assertEqual([ x['amount'] for x in data ], [0,0,0,0,0])

        for x in range(5):
            data[x]['amount'] = x

        headers = {'X-USER-KEY': player.token,
                   'X-API-KEY': self.api_key}
        response = self.client.put("/v1/players/{}/funding".format(id),
                                   data=json.dumps(data),
                                   headers=headers,
                                   content_type='application/json')
        self.assertEquals(response.status_code, 200)

        data2 = self.game.get_funding(id)

        self.assertEqual(data, data2)

    def testSetFundingMaxOverflow(self):

        for x in range(5):
            p = self.game.add_policy("P{}".format(x), 0.5)
            p.id = "P{}".format(x)

        random.seed(0)

        name = 'Matt'
        player = self.game.create_player(name)
        id = player.id

        funding = []
        data = self.game.get_funding(id)

        self.assertEqual([ x['amount'] for x in data ], [0,0,0,0,0])

        for x in range(5):
            data[x]['amount'] = x*200

        headers = {'X-API-KEY': self.api_key,
                   'X-USER-KEY': player.token}
        response = self.client.put("/v1/players/{}/funding".format(id),
                                   data=json.dumps(data),
                                   headers=headers,
                                   content_type='application/json')
        self.assertEquals(response.status_code, 400)

    def testGetWallets(self):
        self.add_20_goals_and_policies()

        random.seed(0)

        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')

        data = self.game.get_funding(p1.id)
        for x in range(5):
            data[x]['amount'] = x
        self.game.set_funding(p1.id, data)

        data = self.game.get_funding(p2.id)
        for x in range(5):
            data[x]['amount'] = x
        self.game.set_funding(p2.id, data)

        self.game.do_propogate_funds()        

        nodes = set(p1.children() + p2.children())

        wallets = []
        for n in nodes:
            headers = {'X-API-KEY': self.api_key}
            response = self.client.get("/v1/network/{}/wallets".format(n.id), headers=headers)
            if response.status_code == 200:
                wallets.extend(response.json)

        expected = [{u'balance': 1.0,
                     u'location': u'P12',
                     u'owner': p2.id},
                    {u'balance': 2.0,
                     u'location': u'P6',
                     u'owner': p1.id},
                    {u'balance': 3.0,
                     u'location': u'P5',
                     u'owner': p2.id},
                    {u'balance': 2.0,
                     u'location': u'P17',
                     u'owner': p2.id},
                    {u'balance': 1.0,
                     u'location': u'P18',
                     u'owner': p1.id},
                    {u'balance': 4.0,
                     u'location': u'P15',
                     u'owner': p2.id},
                    {u'balance': 4.0,
                     u'location': u'P4',
                     u'owner': p1.id},
                    {u'balance': 3.0,
                     u'location': u'P11',
                     u'owner': p1.id}]

        self.assertEqual(sorted(expected), sorted(wallets))

    def testGetNode(self):
        n1 = self.game.add_policy('A', 0.5)

        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/network/{}".format(n1.id), headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['id'], n1.id)
        self.assertEqual(response.json['name'], 'A')

    def testGetOfferDefaultPrice(self):
        seller = self.game.create_player('Matt')
        self.assertEqual(seller.balance, 1500000)
        p1 = self.game.add_policy('Policy 1', 0)
        
        seller.fund(p1, 0)
        self.assertIn(p1, seller.children())

        headers = {'X-USER-KEY': seller.token,
                   'X-API-KEY': self.api_key}
        response = self.client.get("/v1/players/{}/policies/{}/offer".format(seller.id, p1.id), 
                                   headers=headers)
        self.assertEqual(response.status_code, 200)
        offer = response.json
        self.assertEqual(offer['price'], self.game.default_offer_price)

    def testGetOfferCustomPrice(self):
        seller = self.game.create_player('Matt')
        self.assertEqual(seller.balance, 1500000)
        p1 = self.game.add_policy('Policy 1', 0)
        
        seller.fund(p1, 0)
        self.assertIn(p1, seller.children())

        headers = {'X-USER-KEY': seller.token,
                   'X-API-KEY': self.api_key}
        response = self.client.get("/v1/players/{}/policies/{}/offer?price={}".format(seller.id, p1.id, 0), 
                                   headers=headers)
        self.assertEqual(response.status_code, 200)
        offer = response.json
        self.assertEqual(offer['price'], 0)

    def testBuyPolicy(self):
        
        seller = self.game.create_player('Matt')
        buyer = self.game.create_player('Simon')

        self.assertEqual(seller.balance, 1500000)
        self.assertEqual(buyer.balance, 1500000)

        p1 = self.game.add_policy('Policy 1', 0)
        
        seller.fund(p1, 0)
        self.assertIn(p1, seller.children())
        self.assertNotIn(p1, buyer.children())

        headers = {'X-USER-KEY': seller.token,
                   'X-API-KEY': self.api_key}
        response = self.client.get("/v1/players/{}/policies/{}/offer".format(seller.id, p1.id), 
                                   headers=headers)
        self.assertEqual(response.status_code, 200)
        offer = response.json

        headers = {'X-USER-KEY': buyer.token,
                   'X-API-KEY': self.api_key}
        response = self.client.post("/v1/players/{}/policies/".format(buyer.id),
                                    data=json.dumps(offer),
                                    headers=headers,
                                    content_type='application/json')

        self.assertEqual(response.status_code, 200)

        self.assertIn(p1, buyer.children())
        self.assertIn(p1, seller.children())
        self.assertEqual(seller.balance, 1500000+20000)
        self.assertEqual(buyer.balance, 1500000-20000)
        
    def testBuyPolicyFail(self):
        
        seller = self.game.create_player('Matt')
        buyer = self.game.create_player('Simon')
        buyer.balance = 1000

        self.assertEqual(seller.balance, 1500000)
        self.assertEqual(buyer.balance, 1000)

        p1 = self.game.add_policy('Policy 1', 0)
        
        seller.fund(p1, 0)
        self.assertIn(p1, seller.children())
        self.assertNotIn(p1, buyer.children())

        headers = {'X-USER-KEY': seller.token,
                   'X-API-KEY': self.api_key}
        response = self.client.get("/v1/players/{}/policies/{}/offer".format(seller.id, p1.id), 
                                   headers=headers)
        self.assertEqual(response.status_code, 200)
        offer = response.json

        headers = {'X-USER-KEY': buyer.token,
                   'X-API-KEY': self.api_key}
        response = self.client.post("/v1/players/{}/policies/".format(buyer.id),
                                    data=json.dumps(offer),
                                    headers=headers,
                                    content_type='application/json')

        self.assertEqual(response.status_code, 400)

        self.assertNotIn(p1, buyer.children())
        self.assertIn(p1, seller.children())
        self.assertEqual(seller.balance, 1500000)
        self.assertEqual(buyer.balance, 1000)

    def testLeagueTable(self):
        random.seed(0)
        g1 = self.game.add_goal('G1', 0.0)
        g2 = self.game.add_goal('G2', 0.0)

        p1 = self.game.create_player('Matt')
        p1.goal = g1
        p2 = self.game.create_player('Simon')
        p2.goal = g1
        p3 = self.game.create_player('Richard')
        p3.goal = g2

        self.game.add_fund(p1, g1, 10)
        self.game.add_fund(p2, g1, 20)
        self.game.add_fund(p3, g2, 15)

        self.game.tick()

        self.assertEqual(p1.balance, 1499990)
        self.assertEqual(p2.balance, 1499980)
        self.assertEqual(p3.balance, 1499985)

        p1.calc_goal_funded()
        p2.calc_goal_funded()
        p3.calc_goal_funded()

        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/game/league_table", headers=headers)
        self.assertEqual(response.status_code, 200)
        expected = {'rows': [{'id': p2.id,
                              'name': p2.name,
                              'goal': p2.goal.name,
                              'goal_total': '30.00',
                              'goal_contribution': '20.00',},
                             {'id': p3.id,
                              'name': p3.name,
                              'goal': p3.goal.name,
                              'goal_total': '15.00',
                              'goal_contribution': '15.00',},
                             {'id': p1.id,
                              'name': p1.name,
                              'goal': p1.goal.name,
                              'goal_total': '30.00',
                              'goal_contribution': '10.00',}
                             ]}

        self.assertEqual(response.json, expected)

    def testAddPlayerToTable(self):
        random.seed(0)
        p1 = self.game.create_player('Matt')

        table = self.game.create_table('Table A')
        self.assertNotIn(p1, table.players)

        headers = {'X-USER-KEY': p1.token,
                   'X-API-KEY': self.api_key}
        response = self.client.put("/v1/players/{}/table/{}".format(p1.id, table.id),
                                     headers=headers,
                                     content_type='application/json')

        self.assertEquals(response.status_code, 200)
        self.assertIn(p1, table.players)

    def testAddPlayerToNonexistantTable(self):
        random.seed(0)
        p1 = self.game.create_player('Matt')

        table = self.game.create_table('Table A')
        self.assertNotIn(p1, table.players)

        headers = {'X-USER-KEY': p1.token,
                   'X-API-KEY': self.api_key}
        response = self.client.put("/v1/players/{}/table/{}".format(p1.id, 'bogus'),
                                     headers=headers,
                                     content_type='application/json')

        self.assertEquals(response.status_code, 404)
        self.assertNotIn(p1, table.players)

    def testAddNonexistantPlayerToTable(self):
        random.seed(0)
        p1 = self.game.create_player('Matt')

        table = self.game.create_table('Table A')
        self.assertNotIn(p1, table.players)

        headers = {'X-USER-KEY': p1.token,
                   'X-API-KEY': self.api_key}
        response = self.client.put("/v1/players/{}/table/{}".format('bogus', table.id),
                                     headers=headers,
                                     content_type='application/json')

        self.assertEquals(response.status_code, 404)
        self.assertNotIn(p1, table.players)

    def testRemovePlayerFromTable(self):
        random.seed(0)
        p1 = self.game.create_player('Matt')

        table = self.game.create_table('Table A')
        p1.table = table
        self.assertIn(p1, table.players)

        headers = {'X-USER-KEY': p1.token,
                   'X-API-KEY': self.api_key}
        response = self.client.delete("/v1/players/{}/table/{}".format(p1.id, table.id),
                                      headers=headers,
                                      content_type='application/json')

        self.assertEquals(response.status_code, 200)
        self.assertNotIn(p1, table.players)

    def testRemoveAllPlayersFromTable(self):
        random.seed(0)
        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')

        table = self.game.create_table('Table A')
        p1.table = table
        p2.table = table
        self.assertIn(p1, table.players)
        self.assertIn(p2, table.players)

        headers = {'X-USER-KEY': p1.token,
                   'X-API-KEY': self.api_key}
        response = self.client.put("/v1/tables/{}/clear".format(table.id),
                                   headers=headers,
                                   content_type='application/json')

        self.assertEquals(response.status_code, 200)
        self.assertEquals(table.players, [])
        self.assertEquals(p1.table, None)
        self.assertEquals(p2.table, None)

    def testSetMessages(self):
        headers = {'X-API-KEY': self.api_key}
        data = {'budgets': [{'time': '2017-02-22T12:50:00',
                             'message': 'message 1',
                             },
                            {'time': '2017-02-22T12:51:00',
                             'message': 'message 2',
                             }],
                'events': [{'time': '2017-02-22T13:50:00',
                             'message': 'message 3',
                             },
                            {'time': '2017-02-22T13:51:00',
                             'message': 'message 4',
                             }],
                }
        response = self.client.put("/v1/game/messages",
                                   headers=headers,
                                   data=json.dumps(data),
                                   content_type='application/json')

        self.assertEquals(response.status_code, 200)
        messages = self.game.get_messages()
        self.assertEqual(len(messages), 4)

    def testGetMessages(self):
        t1 = datetime(2017,02,22,12,50)
        m1 = self.game.add_message(t1, "budget", "message 1")
        t2 = datetime(2017,02,22,13,50)
        m2 = self.game.add_message(t2, "event", "message 2")

        headers = {'X-API-KEY': self.api_key}
        response = self.client.get("/v1/game/messages", headers=headers)
        self.assertEqual(response.status_code, 200)
        expected = {'budgets': [{'time': '2017-02-22T12:50:00',
                                 'message': 'message 1'}
                                ],
                    'events': [{'time': '2017-02-22T13:50:00',
                                'message': 'message 2'},
                               ],
                    }

        self.assertEqual(sorted(response.json), sorted(expected))



class Utils(DBTestCase): # pragma: no cover

    def createDB(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def createSuperUser(self):
        p = Player('Super User')
        p.id = '89663963-fada-11e6-9949-0c4de9cfe672'
        p.token = '89663b3a-fada-11e6-be7e-0c4de9cfe672'
        db_session.add(p)
        for policy in self.game.get_policies():
            self.game.add_fund(p, policy, 0)

        db_session.commit()
        db_session.commit()
        db_session.commit()

    def genFreebiePolicyCodes(self):
        # [checksum] [policy_id] [price] [seller_id]
        id = '89663963-fada-11e6-9949-0c4de9cfe672'
        token = '89663b3a-fada-11e6-be7e-0c4de9cfe672'
        for policy in self.game.get_policies():
            chk = checksum(id, policy.id, 0, token)

            img = """"<img src='https://chart.googleapis.com/chart?cht=qr&chl={}%20{}%200%20{}&chs=280x280&choe=UTF-8&chld=L|2' alt=''>""".format(chk.upper(), policy.id.upper(), id.upper(), policy.name)
            print "<h1>{}</h1>".format(policy.name)
            print img
            print "<hr />"
#            print "{} {} {} {} {}".format(chk.upper(), policy.id.upper(), 0, id.upper(), policy.name)

    def GenNetFile(self):
        json_file = open('examples/example-graph.json', 'r')
        self.game.load_json(json_file)

        response = self.client.get("/v1/network/")

        outfile = open('examples/network.json', 'w')
        outfile.write(response.data)
        outfile.close()
    
    def loadNet2(self):
        self.createDB()
        f = open('example-network.json')
        network = json.load(f)
        game = self.game
        nodes = {}
        for g in network['goals']:
            goal = game.add_goal(g['name'], 0.0)
            goal.id = g['id']
            nodes[goal.id] = goal

        for p in network['policies']:
            policy = game.add_policy(p['name'], 0.0)
            policy.id = p['id']
            nodes[policy.id] = policy


        for e in network['edges']:
            game.add_link(nodes[e['source']],
                          nodes[e['target']],
                          e['weight'],
                          )

        db_session.commit()
        db_session.commit()
        db_session.commit()


if __name__ == '__main__':
    unittest.main()
