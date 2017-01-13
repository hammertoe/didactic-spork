import json
import unittest
import os
import random
import time
import utils

#if not os.environ.has_key('SQLALCHEMY_DATABASE_URI'):
#    os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
from gameserver.game import Game
from gameserver.models import Node, Player, Goal, Policy, Wallet, Edge
from sqlalchemy import event

from gameserver.database import db
from gameserver.app import app, create_app
from flask_testing import TestCase

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
        utils.random.seed(0)
        self.game = Game()

    def tearDown(self):
        db_session.rollback()

class CoreGameTests(DBTestCase):
        
    def testRefactorLinks(self):
        p1 = Player('Player 1')
        n1 = Policy('Policy A', leak=1.0)
        g1 = Goal('Goal B', leak=1.0)
        w1 = Wallet(p1)
        w2 = Wallet(p1)
        
        l1 = Edge(p1, n1, 1)
        l2 = Edge(n1, g1, 1)

        n1.wallets_here.append(w1)
        p1.wallets_here.append(w2)

        db_session.add_all([p1, n1, g1, l1, l2, w1, w2])

        self.assertEquals(len(p1.wallets_owned), 3)
        self.assertIn(w1, p1.wallets_owned)
        self.assertIn(w2, p1.wallets_owned)
        self.assertEquals(w1.location, n1)

        self.assertEquals(w2.location, p1)
        self.assertEquals(w2.owner, p1)

        self.assertIn(p1.wallets_here[0], p1.wallets_owned)

    def testAddPlayer(self):

        p = self.game.create_player('Matt')

        self.assertEqual(self.game.get_player(p.id), p)
        self.assertEqual(self.game.num_players, 1)


    def testPlayerHasWallet(self):

        p = self.game.create_player('Matt')

        self.assertEqual(self.game.get_player(p.id), p)
        self.assertAlmostEqual(p.balance, 0.0)

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
        w1 = Wallet(p1)
        po1.wallets_here.append(w1)

        self.assertEqual(w1.location, po1)
        self.assertEqual(po1.wallets_here, [w1,])


    def testAddGoal(self):

        g = self.game.add_goal('World Peace', 0.5)

        self.assertEqual(self.game.get_goal(g.id), g)
        self.assertEqual(self.game.get_goal(g.id).leak, 0.5)

    def testAddWalletToGoal(self):

        g = self.game.add_goal('World Peace', 0.5)
        p1 = self.game.create_player('Matt')
        w1 = Wallet(p1)
        g.wallets_here.append(w1)

        self.assertEqual(w1.location, g)
        self.assertEqual(g.wallets_here, [w1,])

    def testModifyPolicies(self):

        p1 = self.game.add_policy('Policy 1', 0.1)
        p2 = self.game.add_policy('Policy 2', 0.2)

        self.assertEqual(self.game.get_policy(p1.id).leak, 0.1)

        p1.leak = 0.3
        self.assertEqual(self.game.get_policy(p1.id).leak, 0.3)
        self.assertEqual(self.game.get_policy(p2.id).leak, 0.2)

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

        w1 = self.game.add_wallet(p1, 5.0)
        self.assertEqual(n1.balance, 0)
        n1.wallets_here.append(w1)
        self.assertEqual(n1.balance, 5.0)

        w2 = self.game.add_wallet(p1, 10.0)
        self.assertEqual(n1.balance, 5.0)
        n1.wallets_here.append(w2)
        self.assertEqual(n1.balance, 15.0)

    def testNodeLeak100(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        p1 = self.game.create_player('Matt')
        w1 = self.game.add_wallet(p1, 5.0)
        n1.wallets_here.append(w1)
        w2 = self.game.add_wallet(p1, 10.0)
        n1.wallets_here.append(w2)

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 0.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 0.0)

    def testNodeLeak0(self):
        n1 = self.game.add_policy('Policy 1', 0.0)
        p1 = self.game.create_player('Matt')
        w1 = self.game.add_wallet(p1, 5.0)
        n1.wallets_here.append(w1)
        w2 = self.game.add_wallet(p1, 10.0)
        n1.wallets_here.append(w2)

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 15.0)

    def testNodeLeak20(self):
        n1 = self.game.add_policy('Policy 1', 0.2)
        p1 = self.game.create_player('Matt')
        w1 = self.game.add_wallet(p1, 5.0)
        n1.wallets_here.append(w1)
        w2 = self.game.add_wallet(p1, 10.0)
        n1.wallets_here.append(w2)

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertAlmostEqual(n1.balance, 12.0)
        n1.do_leak()
        self.assertAlmostEqual(n1.balance, 9.6)

        # Check the individual wallets
        self.assertAlmostEqual(w1.balance, 3.2)
        self.assertAlmostEqual(w2.balance, 6.4)

    def testTransferWalletToWallet(self):
        p1 = self.game.create_player('Matt')
        w1 = Wallet(p1, 100.0)
        w2 = Wallet(p1, 20.0)

        self.assertAlmostEqual(w1.balance, 100.0)
        self.assertAlmostEqual(w2.balance, 20.0)

        w1.transfer_to_wallet(w2, 30.0)

        self.assertAlmostEqual(w1.balance, 70.0)
        self.assertAlmostEqual(w2.balance, 50.0)


    def testTransferWalletToNode(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        p1 = self.game.create_player('Matt')
        w1 = self.game.add_wallet(p1, 100)
        n1.wallets_here.append(w1)

        n2 = self.game.add_policy('Policy 2', 1.0)

        self.assertAlmostEqual(n1.balance, 100.0)
        self.assertAlmostEqual(n2.balance, 0.0)

        self.assertEqual(db_session.query(Wallet).count(), 2)

        w1.transfer_to_node(n2, 70.0)

        self.assertAlmostEqual(n1.balance, 30.0)
        self.assertAlmostEqual(n2.balance, 70.0)

        self.assertEqual(db_session.query(Wallet).count(), 3)

        w1.transfer_to_node(n2, 10.0)

        self.assertAlmostEqual(n1.balance, 20.0)
        self.assertAlmostEqual(n2.balance, 80.0)

        self.assertEqual(db_session.query(Wallet).count(), 3)

        w1.transfer_to_node(n2, 20.0)

        self.assertAlmostEqual(n1.balance, 0.0)
        self.assertAlmostEqual(n2.balance, 100.0)

        self.assertEqual(db_session.query(Wallet).count(), 2)

    def testTransferToWalletInsufficientFunds(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        p1 = self.game.create_player('Matt')
        w1 = self.game.add_wallet(p1, 100)
        n1.wallets_here.append(w1)
        n2 = self.game.add_policy('Policy 2', 1.0)

        self.assertAlmostEqual(n1.balance, 100.0)
        self.assertAlmostEqual(n2.balance, 0.0)

        with self.assertRaises(ValueError):
            w1.transfer_to_node(n2, 110.0)

        self.assertAlmostEqual(n1.balance, 100.0)
        self.assertAlmostEqual(n2.balance, 0.0)


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

        self.assertEqual(len(p1.children()), 0)

    def testPlayerCurrentOutflow(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        self.game.add_fund(p1, po1, 10)
        po2 = self.game.add_policy('Policy 2', 1.0)
        self.game.add_fund(p1, po2, 20)
        po3 = self.game.add_policy('Policy 3', 1.0)
        self.game.add_fund(p1, po3, 30)

        self.assertEqual(p1.current_outflow, 60)

        self.game.add_fund(p1, po3, 10)
        self.assertEqual(p1.current_outflow, 40)

        self.game.add_fund(p1, po2, 0)
        self.assertEqual(p1.current_outflow, 20)

    def testPlayerMaxOutflow(self):
        p1 = self.game.create_player('Matt')
        self.assertEqual(p1.max_outflow, self.game.standard_max_player_outflow)
        
    def testPlayerExceedMaxOutflow(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        self.game.add_fund(p1, po1, 10)
        po2 = self.game.add_policy('Policy 2', 1.0)
        self.game.add_fund(p1, po2, 20)
        po3 = self.game.add_policy('Policy 3', 1.0)

        with self.assertRaises(ValueError):
            self.game.add_fund(p1, po3, 80)

        self.assertEqual(p1.current_outflow, 30)

        self.game.add_fund(p1, po3, 70)
        self.assertEqual(p1.current_outflow, 100)

    def testNodeActivationFromPlayer(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        po1.activation = 2.0

        self.assertFalse(po1.active)
        self.game.add_fund(p1, po1, 10.0)
        
        self.assertTrue(po1.active)

    def testNodeActivationFromNode(self):
        p1 = self.game.create_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        po1.activation = 2.0

        self.assertFalse(po1.active)

        po2 = self.game.add_policy('Policy 2', 1.0)
        po2.activation = 10.0
        l1 = self.game.add_link(po1, po2, 5.0)

        self.assertFalse(po1.active)

        self.game.add_fund(p1, po1, 10.0)
        for x in range(5):
            self.game.do_propogate_funds()
        
        self.assertTrue(po1.active)
        self.assertFalse(po2.active)

        self.game.add_fund(p1, po1, 20.0)
        self.assertTrue(po1.active)
        self.assertFalse(po2.active)

        l1.weight = 30.0
        self.assertTrue(po1.active)
        self.assertTrue(po2.active)


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
        w1 = self.game.add_wallet(p1, 100.0)
        w1.location = n1
        w2 = self.game.add_wallet(p1, 100.0)
        w2.location = n2

        self.assertEqual(n1.balance, 100.0)
        self.assertEqual(n2.balance, 100.0)

        self.game.do_leak()
        self.assertEqual(n1.balance, 0.0)
        self.assertEqual(n2.balance, 0.0)

    def testGameLeak0_100(self):
        n1 = self.game.add_policy('Policy 1', 0.0)
        n2 = self.game.add_policy('Policy 2', 1.0)
        p1 = self.game.create_player('Matt')
        w1 = self.game.add_wallet(p1, 100.0)
        w1.location = n1
        w2 = self.game.add_wallet(p1, 100.0)
        w2.location = n2

        self.assertEqual(n1.balance, 100.0)
        self.assertEqual(n2.balance, 100.0)

        self.game.do_leak()
        self.assertEqual(n1.balance, 100.0)
        self.assertEqual(n2.balance, 0.0)

    def testGameLeak50(self):
        n1 = self.game.add_policy('Policy 1', 0.5)
        n2 = self.game.add_policy('Policy 2', 0.2)
        p1 = self.game.create_player('Matt')
        w1 = self.game.add_wallet(p1, 100.0)
        w1.location = n1
        w2 = self.game.add_wallet(p1, 100.0)
        w2.location = n2

        self.assertEqual(n1.balance, 100.0)
        self.assertEqual(n2.balance, 100.0)

        self.game.do_leak()
        self.assertAlmostEqual(n1.balance, 50.0)
        self.assertAlmostEqual(n2.balance, 80.0)

        self.game.do_leak()
        self.assertAlmostEqual(n1.balance, 25.0)
        self.assertAlmostEqual(n2.balance, 64.0)


    def testFundPlayers(self):
        p1 = self.game.create_player('Matt')
        p2 = self.game.create_player('Simon')
        p3 = self.game.create_player('Rich')

        self.game.do_replenish_budget()

        self.assertAlmostEqual(p1.balance, self.game.coins_per_budget_cycle)
        self.assertAlmostEqual(p2.balance, self.game.coins_per_budget_cycle)
        self.assertAlmostEqual(p3.balance, self.game.coins_per_budget_cycle)

        n1 = self.game.add_policy('Policy 1', 1.0)

        p1.transfer_funds_to_node(n1, 100)
        p2.transfer_funds_to_node(n1, 200)
        p3.transfer_funds_to_node(n1, 400)

        self.assertAlmostEqual(p1.balance, self.game.coins_per_budget_cycle-100)
        self.assertAlmostEqual(p2.balance, self.game.coins_per_budget_cycle-200)
        self.assertAlmostEqual(p3.balance, self.game.coins_per_budget_cycle-400)

        self.assertAlmostEqual(n1.balance, 100+200+400)

        self.game.do_replenish_budget()

        self.assertAlmostEqual(p1.balance, self.game.coins_per_budget_cycle)
        self.assertAlmostEqual(p2.balance, self.game.coins_per_budget_cycle)
        self.assertAlmostEqual(p3.balance, self.game.coins_per_budget_cycle)

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
        self.assertAlmostEqual(po1.balance, 49.998, 2)
        self.assertAlmostEqual(po2.balance, 59.998, 2)

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
        po1.activation = 6.0
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
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        po1.activation = 0.2
        g1 = self.game.add_goal('World Peace', 0.5)
        self.game.add_fund(p1, po1, 5.0)
        l2 = self.game.add_link(po1, g1, 1.0)

        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 500)
        self.assertEqual(po1.balance, 400)
        self.assertEqual(g1.balance, 100)

class DataLoadTests(DBTestCase):

    def testLoadJsonFile(self):
        json_file = open('example-graph.json', 'r')
        self.game.load_json(json_file)
        self.assertEqual(61, db_session.query(Edge).count())
        self.assertEqual(36, db_session.query(Node).count())
        self.assertEqual(30, db_session.query(Policy).count())
        self.assertEqual(6, db_session.query(Goal).count())

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

    def testCreateNetwork(self):
        data = json.load(open('network.json', 'r'))

        self.game.create_network(data)

        self.assertEqual(61, db_session.query(Edge).count())
        self.assertEqual(36, db_session.query(Node).count())
        self.assertEqual(30, db_session.query(Policy).count())
        self.assertEqual(6, db_session.query(Goal).count())


    def testCreateThenGetNetwork(self):
        data = json.load(open('network.json', 'r'))

        self.game.create_network(data)
        network = self.game.get_network()

        self.assertEqual(data, network)


class GameTests(DBTestCase):
    
    def testGetNonexistantPlayer(self):
        player = self.game.get_player('nonexistant')
        self.assertIsNone(player)

class RestAPITests(DBTestCase):

    @unittest.skip("not implemented")
    def testGetEmptyPlayersList(self):
        response = self.client.get("/v1/players/")
        import pdb; pdb.set_trace()
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json, [])

    @unittest.skip("not implemented")
    def testGetNonEmptyPlayersList(self):
        names = ['Matt', 'Simon', 'Richard']
        cp = self.game.create_player
        players = [ cp(name) for name in names ]
        data = [ dict(name=p.name, id=p.id) for p in players ]

        response = self.client.get("/v1/players/")
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json, data)

    def testGetSpecificPlayer(self):
        name = 'Matt'
        player = self.game.create_player(name)
        id = player.id
        response = self.client.get("/v1/players/{}".format(id))
        self.assertEquals(response.status_code, 200)
        self.assertDictContainsSubset(dict(name=name, id=id), response.json)
        self.assertFalse(response.json.has_key('token'))

    def testGetNonExistentPlayer(self):
        response = self.client.get("/v1/players/nobody")
        self.assertEquals(response.status_code, 404)

    def testCreateNewPlayer(self):
        data = dict(name='Matt')

        response = self.client.post("/v1/players/", data=json.dumps(data),
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)
        id = response.json['id']
        token = response.json['token']

        player = self.game.get_player(id)
        self.assertEquals(id, player.id)
        self.assertEquals(token, player.token)

    def testCreateThenGetNewPlayer(self):
        name = 'Matt {}'.format(time.time())
        data = dict(name=name)
        response = self.client.post("/v1/players/", data=json.dumps(data),
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)
        id = response.json['id']

        response = self.client.get("/v1/players/{}".format(id))
        self.assertEquals(response.status_code, 200)
        self.assertDictContainsSubset(dict(name=name, id=id), response.json)
        self.assertFalse(response.json.has_key('token'))

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

        response = self.client.get("/v1/network/")
        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.json['policies']), 2)
        self.assertEquals(len(response.json['goals']), 3)


class Utils(DBTestCase):

    def GenNetFile(self):
        json_file = open('example-graph.json', 'r')
        self.game.load_json(json_file)

        response = self.client.get("/v1/network/")

        outfile = open('network.json', 'w')
        outfile.write(response.data)
        outfile.close()

if __name__ == '__main__':
    unittest.main()
