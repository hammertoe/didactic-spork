import unittest
import os
import random
import utils

if not os.environ.has_key('SQLALCHEMY_DATABASE_URI'):
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
from game import Game
from database import clear_db, init_db, db_session
from models import Edge, Node, Player, Goal, Policy, Wallet, Fund

class GameNetworkTests(unittest.TestCase):

    def setUp(self):
        utils.random.seed(0)
        init_db()
        self.game = Game()
 
    def tearDown(self):
        clear_db()

    def testAddPlayer(self):

        p = self.game.add_player('Matt')

        self.assertEqual(self.game.get_player(p.id), p)
        self.assertEqual(self.game.num_players, 1)


    def testPlayerHasWallet(self):

        p = self.game.add_player('Matt')

        self.assertEqual(self.game.get_player(p.id), p)
        self.assertAlmostEqual(p.balance, 0.0)

    def testPlayerSetBalance(self):

        p = self.game.add_player('Matt')
        p.balance = 5000

        self.assertAlmostEqual(p.balance, 5000.0)

    def testAddPolicy(self):

        p = self.game.add_policy('Arms Embargo', 0.1)

        self.assertEqual(self.game.get_policy(p.id), p)
        self.assertEqual(self.game.get_policy(p.id).leak, 0.1)

    def testAddWalletToPolicy(self):

        po1 = self.game.add_policy('Arms Embargo', 0.1)
        p1 = self.game.add_player('Matt')
        w1 = Wallet(p1)
        po1.wallets = [w1,]

        self.assertEqual(w1.location, po1)
        self.assertEqual(po1.wallets, [w1,])


    def testAddGoal(self):

        g = self.game.add_goal('World Peace', 0.5)

        self.assertEqual(self.game.get_goal(g.id), g)
        self.assertEqual(self.game.get_goal(g.id).leak, 0.5)

    def testAddWalletToGoal(self):

        g = self.game.add_goal('World Peace', 0.5)
        p1 = self.game.add_player('Matt')
        w1 = Wallet(p1)
        g.wallets.append(w1)

        self.assertEqual(w1.location, g)
        self.assertEqual(g.wallets, [w1,])


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
        p1 = self.game.add_player('Matt')

        self.assertEqual(n1.balance, 0)

        w1 = self.game.add_wallet(p1, 5.0)
        self.assertEqual(n1.balance, 0)
        n1.wallets.append(w1)
        self.assertEqual(n1.balance, 5.0)

        w2 = self.game.add_wallet(p1, 10.0)
        self.assertEqual(n1.balance, 5.0)
        n1.wallets.append(w2)
        self.assertEqual(n1.balance, 15.0)


    def testNodeLeak100(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        p1 = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p1, 5.0)
        n1.wallets.append(w1)
        w2 = self.game.add_wallet(p1, 10.0)
        n1.wallets.append(w2)

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 0.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 0.0)

    def testNodeLeak0(self):
        n1 = self.game.add_policy('Policy 1', 0.0)
        p1 = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p1, 5.0)
        n1.wallets.append(w1)
        w2 = self.game.add_wallet(p1, 10.0)
        n1.wallets.append(w2)

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 15.0)

    def testNodeLeak20(self):
        n1 = self.game.add_policy('Policy 1', 0.2)
        p1 = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p1, 5.0)
        n1.wallets.append(w1)
        w2 = self.game.add_wallet(p1, 10.0)
        n1.wallets.append(w2)

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertAlmostEqual(n1.balance, 12.0)
        n1.do_leak()
        self.assertAlmostEqual(n1.balance, 9.6)

        # Check the individual wallets
        self.assertAlmostEqual(w1.balance, 3.2)
        self.assertAlmostEqual(w2.balance, 6.4)

    def testTransferWalletToWallet(self):
        p1 = self.game.add_player('Matt')
        w1 = Wallet(p1, 100.0)
        w2 = Wallet(p1, 20.0)

        self.assertAlmostEqual(w1.balance, 100.0)
        self.assertAlmostEqual(w2.balance, 20.0)

        w1.transfer_to_wallet(w2, 30.0)

        self.assertAlmostEqual(w1.balance, 70.0)
        self.assertAlmostEqual(w2.balance, 50.0)


    def testTransferWalletToNode(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        p1 = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p1, 100)
        n1.wallets.append(w1)

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
        p1 = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p1, 100)
        n1.wallets.append(w1)
        n2 = self.game.add_policy('Policy 2', 1.0)

        self.assertAlmostEqual(n1.balance, 100.0)
        self.assertAlmostEqual(n2.balance, 0.0)

        with self.assertRaises(ValueError):
            w1.transfer_to_node(n2, 110.0)

        self.assertAlmostEqual(n1.balance, 100.0)
        self.assertAlmostEqual(n2.balance, 0.0)


    def testAllocateFunds(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000.0
        n1 = self.game.add_policy('Policy 1', 1.0)

        self.assertEqual(p1.balance, 1000.0)
        self.assertEqual(n1.balance, 0.0)

        p1.transfer_funds()

        self.assertEqual(p1.balance, 1000.0)
        self.assertEqual(n1.balance, 0.0)

        p1.fund(n1, 100)

        p1.transfer_funds()

        self.assertEqual(p1.balance, 900.0)
        self.assertEqual(n1.balance, 100.0)

    def testAllocateDifferentFunds(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000.0
        n1 = self.game.add_policy('Policy 1', 1.0)

        p1.fund(n1, 60)
        p1.transfer_funds()

        self.assertEqual(p1.balance, 940.0)
        self.assertEqual(n1.balance, 60.0)

        p1.fund(n1, 80)
        p1.transfer_funds()

        self.assertEqual(p1.balance, 860.0)
        self.assertEqual(n1.balance, 140.0)

    def testDeleteFunds(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000.0
        n1 = self.game.add_policy('Policy 1', 1.0)

        p1.fund(n1, 100)
        p1.transfer_funds()

        self.assertEqual(p1.balance, 900.0)
        self.assertEqual(n1.balance, 100.0)

        p1.fund(n1, 0)
        # needed to get delete to show
        db_session.commit()
        p1.transfer_funds()

        self.assertEqual(p1.balance, 900.0)
        self.assertEqual(n1.balance, 100.0)

        self.assertEqual(len(p1.funds), 0)

    def testPlayerCurrentOutflow(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        p1.fund(po1, 10)
        po2 = self.game.add_policy('Policy 2', 1.0)
        p1.fund(po2, 20)
        po3 = self.game.add_policy('Policy 3', 1.0)
        p1.fund(po3, 30)

        self.assertEqual(p1.current_outflow, 60)

        p1.fund(po3, 10)
        self.assertEqual(p1.current_outflow, 40)

        p1.fund(po2, 0)
        self.assertEqual(p1.current_outflow, 20)

    def testPlayerMaxOutflow(self):
        p1 = self.game.add_player('Matt')
        self.assertEqual(p1.max_outflow, self.game.standard_max_player_outflow)
        
    def testPlayerExceedMaxOutflow(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        p1.fund(po1, 10)
        po2 = self.game.add_policy('Policy 2', 1.0)
        p1.fund(po2, 20)
        po3 = self.game.add_policy('Policy 3', 1.0)

        with self.assertRaises(ValueError):
            p1.fund(po3, 80)

        self.assertEqual(p1.current_outflow, 30)

        p1.fund(po3, 70)
        self.assertEqual(p1.current_outflow, 100)

    def testNodeActivationFromPlayer(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        po1.activation = 2.0

        self.assertFalse(po1.active)
        p1.fund(po1, 10.0)
        
        self.assertTrue(po1.active)

    def testNodeActivationFromNode(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000.0
        po1 = self.game.add_policy('Policy 1', 1.0)
        po1.activation = 2.0

        self.assertFalse(po1.active)

        po2 = self.game.add_policy('Policy 2', 1.0)
        po2.activation = 10.0
        l1 = self.game.add_link(po1, po2, 5.0)

        self.assertFalse(po1.active)

        p1.fund(po1, 10.0)
        for x in range(5):
            self.game.do_inject_funds()
            self.game.do_propogate_funds()
        
        self.assertTrue(po1.active)
        self.assertFalse(po2.active)

        p1.fund(po1, 20.0)
        self.assertTrue(po1.active)
        self.assertFalse(po2.active)

        l1.weight = 30.0
        self.assertTrue(po1.active)
        self.assertTrue(po2.active)

    def testTwoPlayersFundPolicy(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000.0
        p2 = self.game.add_player('Simon')
        p2.balance = 1000.0
        n1 = self.game.add_policy('Policy 1', 1.0)

        p1.fund(n1, 100)
        p2.fund(n1, 90)
        p1.transfer_funds()
        p2.transfer_funds()

        self.assertEqual(p1.balance, 900.0)
        self.assertEqual(p2.balance, 910.0)
        self.assertEqual(n1.balance, 190.0)

        self.assertEqual(len(n1.funded_by), 2)

    def testGameTransferFunds(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000.0
        p2 = self.game.add_player('Simon')
        p2.balance = 1000.0
        p3 = self.game.add_player('Rich')
        p3.balance = 1000.0
    
        n1 = self.game.add_policy('Policy 1', 1.0)

        p1.fund(n1, 10)
        p2.fund(n1, 20)
        p3.fund(n1, 50)

        self.game.do_inject_funds()

        self.assertEqual(p1.balance, 990.0)
        self.assertEqual(p2.balance, 980.0)
        self.assertEqual(p3.balance, 950.0)
        self.assertEqual(n1.balance, 80.0)

        self.assertEqual(len(n1.funded_by), 3)

    def testGameTransferFundsComplex(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000.0
        p2 = self.game.add_player('Simon')
        p2.balance = 1000.0
        p3 = self.game.add_player('Rich')
        p3.balance = 1000.0
    
        n1 = self.game.add_policy('Policy 1', 1.0)
        n2 = self.game.add_policy('Policy 2', 1.0)

        p1.fund(n1, 10)
        p2.fund(n1, 20)
        p3.fund(n1, 50)

        p2.fund(n2, 50)
        p3.fund(n2, 40)

        self.game.do_inject_funds()

        self.assertEqual(p1.balance, 990.0)
        self.assertEqual(p2.balance, 930.0)
        self.assertEqual(p3.balance, 910.0)
        self.assertEqual(n1.balance, 80.0)
        self.assertEqual(n2.balance, 90.0)

        self.assertEqual(len(n1.funded_by), 3)
        self.assertEqual(len(n2.funded_by), 2)


    def testAllocateFundsMultiplePolicies(self):
        p1 = self.game.add_player('Matt')
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

        p1.fund(n1, 10)
        p1.fund(n2, 30)

        p1.transfer_funds()

        self.assertEqual(p1.balance, 960.0)
        self.assertEqual(n1.balance, 10.0)
        self.assertEqual(n2.balance, 30.0)


    def testGameLeak100(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        n2 = self.game.add_policy('Policy 2', 1.0)
        p1 = self.game.add_player('Matt')
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
        p1 = self.game.add_player('Matt')
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
        p1 = self.game.add_player('Matt')
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
        p1 = self.game.add_player('Matt')
        p2 = self.game.add_player('Simon')
        p3 = self.game.add_player('Rich')

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
        p1 = self.game.add_player('Matt')
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
        p1 = self.game.add_player('Matt')

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
        p1 = self.game.add_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        p1.fund(po1, 50)

        self.assertEqual(p1.balance, 1000)
        self.assertEqual(po1.balance, 0)

        p1.transfer_funds_to_node(po1, 60)
        self.assertEqual(po1.balance, 60)

        self.assertEqual(p1.balance, 940)
        self.assertEqual(po1.balance, 60)

    def testTransferGreaterThan100_300(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        p1.fund(po1, 3.0)

        self.assertEqual(p1.balance, 1000)
        self.assertEqual(po1.balance, 0)

        for x in range(50):
            self.game.do_inject_funds()
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 850)
        self.assertEqual(po1.balance, 150)


    def testTransferSlowFunds(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        p1.fund(po1, 1.0)

        g1 = self.game.add_goal('World Peace', 1.0)
        l1 = self.game.add_link(po1, g1, 2.0)

        self.game.do_inject_funds()
        self.game.do_propogate_funds()
        
        self.assertEqual(p1.balance, 999)
        self.assertEqual(po1.balance, 1.0)
        self.assertEqual(g1.balance, 0.0)

        self.game.do_inject_funds()
        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 998)
        self.assertEqual(po1.balance, 0.0)
        self.assertEqual(g1.balance, 2.0)

        self.game.do_inject_funds()
        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 997)
        self.assertEqual(po1.balance, 1.0)
        self.assertEqual(g1.balance, 2.0)

        self.game.do_inject_funds()
        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 996)
        self.assertEqual(po1.balance, 0.0)
        self.assertEqual(g1.balance, 4.0)

        self.game.do_inject_funds()
        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 995)
        self.assertEqual(po1.balance, 1.0)
        self.assertEqual(g1.balance, 4.0)
        
    def testTransferFastFunds(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        p1.fund(po1, 3.0)

        g1 = self.game.add_goal('World Peace', 1.0)
        l1 = self.game.add_link(po1, g1, 1.0)

        self.game.do_inject_funds()
        self.game.do_propogate_funds()
        
        self.assertEqual(p1.balance, 997)
        self.assertEqual(po1.balance, 2.0)
        self.assertEqual(g1.balance, 1.0)

        self.game.do_inject_funds()
        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 994)
        self.assertEqual(po1.balance, 4.0)
        self.assertEqual(g1.balance, 2.0)

        self.game.do_inject_funds()
        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 991)
        self.assertEqual(po1.balance, 6.0)
        self.assertEqual(g1.balance, 3.0)

        self.game.do_inject_funds()
        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 988)
        self.assertEqual(po1.balance, 8.0)
        self.assertEqual(g1.balance, 4.0)

        self.game.do_inject_funds()
        self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 985)
        self.assertEqual(po1.balance, 10.0)
        self.assertEqual(g1.balance, 5.0)
        
        
    def testMoreComplexPlayerCoinsNetwork(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        p1.fund(po1, 0.5)
        po2 = self.game.add_policy('Pollution control', 0.1)
        p1.fund(po2, 1.0)

        g1 = self.game.add_goal('World Peace', 0.5)
        g2 = self.game.add_goal('Clean Water', 0.5)
        l3 = self.game.add_link(po1, g1, 1.0)
        l4 = self.game.add_link(po2, g2, 2.0)

        self.assertEqual(p1.balance, 1000)
        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_inject_funds()
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 850)
        self.assertEqual(po1.balance, 0)
        self.assertEqual(po2.balance, 0)

        self.assertEqual(g1.balance, 50)
        self.assertEqual(g2.balance, 100)

    def testMoreComplexPlayerCoinsNetworkWithFullTick(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 5000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        p1.fund(po1, 10.0)
        po2 = self.game.add_policy('Pollution control', 0.1)
        p1.fund(po2, 15.0)

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
        p1 = self.game.add_player('Matt')
        p1.balance = 1000
        p2 = self.game.add_player('Simon')
        p2.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        p1.fund(po1, 1.0)
        p2.fund(po1, 1.0)

        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_inject_funds()
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 900)
        self.assertEqual(p2.balance, 900)

        self.assertEqual(po1.balance, 200)


    def testActivationLevelLow(self):
        p1 = self.game.add_player('Matt')
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        po1.activation = 0.7
        g1 = self.game.add_goal('World Peace', 0.5)
        p1.fund(po1, 0.5)
        l2 = self.game.add_link(po1, g1, 1.0)

        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 956)
        self.assertEqual(po1.balance, 44)
        self.assertEqual(g1.balance, 0)

    def testActivationLevelHigh(self):
        p1 = self.game.add_player('Matt')
        p1.balance = 1000
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        po1.activation = 0.2
        g1 = self.game.add_goal('World Peace', 0.5)
        p1.fund(po1, 5.0)
        l2 = self.game.add_link(po1, g1, 1.0)

        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_inject_funds()
            self.game.do_propogate_funds()

        self.assertEqual(p1.balance, 500)
        self.assertEqual(po1.balance, 0)
        self.assertEqual(g1.balance, 45)

    def testLoadJsonFile(self):
        json_file = open('example-graph.json', 'r')
        self.game.load_json(json_file)
        self.assertEqual(61, db_session.query(Edge).count())
        self.assertEqual(36, db_session.query(Node).count())
        self.assertEqual(30, db_session.query(Policy).count())
        self.assertEqual(6, db_session.query(Goal).count())
        

    def testNetworkPropogation(self):
        p1 = self.game.add_player('A')
        p1.balance = 1000
        p2 = self.game.add_player('B')
        p2.balance = 1000
        n1 = self.game.add_policy('C', 0.0)
        n1.activation = 20.0
        n2 = self.game.add_policy('D', 0.0)
        n3 = self.game.add_policy('E', 0.0)
        n4 = self.game.add_policy('F', 0.0)
        n4.max_level = 30.0
        n5 = self.game.add_policy('G', 0.0)
        n6 = self.game.add_policy('H', 0.0)

        p1.fund(n1, 20.0)
        p1.fund(n3, 10.0)
        p2.fund(n3, 10.0)
        p2.fund(n4, 10.0)
        p2.fund(n6, 10.0)

        l1 = self.game.add_link(n1, n2, 5.0)
        l2 = self.game.add_link(n3, n5, 5.0)
        l1 = self.game.add_link(n3, n4, 5.0)
        l1 = self.game.add_link(n4, n5, 5.0)

        
        for i in range(10):
            self.game.do_inject_funds()
            self.game.do_propogate_funds()

            nodes = db_session.query(Node).all()
            for node in sorted(nodes, key=lambda n: n.rank):
                print node.rank, node.name, node.balance


            print

        for node in [n2, n5, n6]:
            print node.name
            print "----"
            for wallet in node.wallets:
                print "{:.2f} {}".format(wallet.balance, wallet.owner.name)
            print

if __name__ == '__main__':
    unittest.main()

