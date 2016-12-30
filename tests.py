import unittest
import os
import random
import utils

if not os.environ.has_key('SQLALCHEMY_DATABASE_URI'):
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
from game import Game
from database import clear_db, init_db, db_session
from models import Edge, Node, Player, Goal, Policy, Wallet

class GameNetworkTests(unittest.TestCase):

    def setUp(self):
        utils.random.seed(0)
        init_db()
        self.game = Game()
 
    def tearDown(self):
        clear_db()

    def testAddPlayer(self):

        p = self.game.add_player('Matt')
        db_session.commit()

        self.assertEqual(self.game.get_player(p.id), p)

    def testAddWalletToPlayer(self):

        p = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p, 5.0)
        w1.location_id = p.id

        db_session.commit()

        self.assertEqual(self.game.get_player(p.id), p)
        self.assertAlmostEqual(p.balance, 5.0)

    def testPlayerSetBalance(self):

        p = self.game.add_player('Matt')
        p.balance = 5000

        db_session.commit()

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
        db_session.commit()

        self.assertEqual(self.game.get_goal(g.id), g)
        self.assertEqual(self.game.get_goal(g.id).leak, 0.5)

    def testAddWalletToGoal(self):

        g = self.game.add_goal('World Peace', 0.5)
        p1 = self.game.add_player('Matt')
        w1 = Wallet(p1)
        g.wallets = [w1,]

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

        import pdb; pdb.set_trace()

        self.assertEqual(n1.balance, 0)

        w1 = self.game.add_wallet(p1, 5.0)

        self.assertEqual(n1.balance, 0)

        w1.location = n1

        self.assertEqual(n1.balance, 5.0)

        w2 = self.game.add_wallet(p1, 10.0)

        w2.location = n1

        self.assertEqual(n1.balance, 15.0)

    def testNodeLeak100(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        p1 = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p1, 5.0)
        w1.location = n1
        w2 = self.game.add_wallet(p1, 10.0)
        w2.location = n1

        db_session.commit()

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 0.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 0.0)

    def testNodeLeak0(self):
        n1 = self.game.add_policy('Policy 1', 0.0)
        p1 = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p1, 5.0)
        w1.location = n1
        w2 = self.game.add_wallet(p1, 10.0)
        w2.location = n1

        db_session.commit()

        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 15.0)
        n1.do_leak()
        self.assertEqual(n1.balance, 15.0)

    def testNodeLeak20(self):
        n1 = self.game.add_policy('Policy 1', 0.2)
        p1 = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p1, 5.0)
        w1.location = n1
        w2 = self.game.add_wallet(p1, 10.0)
        w2.location = n1

        db_session.commit()

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
        w1.location = n1
        n2 = self.game.add_policy('Policy 2', 1.0)

        self.assertAlmostEqual(n1.balance, 100.0)
        self.assertAlmostEqual(n2.balance, 0.0)

        db_session.commit()

        self.assertEqual(Wallet.query.count(), 1)

        w1.transfer_to_node(n2, 70.0)

        db_session.commit()

        self.assertAlmostEqual(n1.balance, 30.0)
        self.assertAlmostEqual(n2.balance, 70.0)

        db_session.commit()

        self.assertEqual(Wallet.query.count(), 2)

        w1.transfer_to_node(n2, 10.0)

        db_session.commit()

        self.assertAlmostEqual(n1.balance, 20.0)
        self.assertAlmostEqual(n2.balance, 80.0)

        self.assertEqual(Wallet.query.count(), 2)

        w1.transfer_to_node(n2, 20.0)

        db_session.commit()

        self.assertAlmostEqual(n1.balance, 0.0)
        self.assertAlmostEqual(n2.balance, 100.0)

        self.assertEqual(Wallet.query.count(), 1)


    def testTransferToWalletInsufficientFunds(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        p1 = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p1, 100)
        w1.location = n1
        n2 = self.game.add_policy('Policy 2', 1.0)

        self.assertAlmostEqual(n1.balance, 100.0)
        self.assertAlmostEqual(n2.balance, 0.0)

        with self.assertRaises(ValueError):
            w1.transfer_to_node(n2, 110.0)

        self.assertAlmostEqual(n1.balance, 100.0)
        self.assertAlmostEqual(n2.balance, 0.0)



    def testGameLeak100(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        n2 = self.game.add_policy('Policy 2', 1.0)
        p1 = self.game.add_player('Matt')
        w1 = self.game.add_wallet(p1, 100.0)
        w1.location = n1
        w2 = self.game.add_wallet(p1, 100.0)
        w2.location = n2

        db_session.commit()

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

        db_session.commit()

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

        db_session.commit()

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

        db_session.commit()

        self.game.do_fund_players()

        db_session.commit()

        self.assertAlmostEqual(p1.balance, self.game.coins_per_budget_cycle)
        self.assertAlmostEqual(p2.balance, self.game.coins_per_budget_cycle)
        self.assertAlmostEqual(p3.balance, self.game.coins_per_budget_cycle)

        n1 = self.game.add_policy('Policy 1', 1.0)

        p1.fund(n1, 100)
        p2.fund(n1, 200)
        p3.fund(n1, 400)

        db_session.commit()

        self.assertAlmostEqual(p1.balance, self.game.coins_per_budget_cycle-100)
        self.assertAlmostEqual(p2.balance, self.game.coins_per_budget_cycle-200)
        self.assertAlmostEqual(p3.balance, self.game.coins_per_budget_cycle-400)

        self.assertAlmostEqual(n1.balance, 100+200+400)

        self.game.do_fund_players()

        db_session.commit()

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

        db_session.commit()

        self.game.do_fund_players()

        db_session.commit()

        p1.fund(n1, 100)

        db_session.commit()

        self.assertEqual(n1.balance, 100)
        self.assertEqual(n2.balance, 0)
        self.assertEqual(n3.balance, 0)
        
        self.game.do_transfer()

        self.assertAlmostEqual(n1.balance, 55.0)
        self.assertAlmostEqual(n2.balance, 15.0)
        self.assertAlmostEqual(n3.balance, 30.0)

        self.game.do_transfer()

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

        db_session.commit()
        
        self.game.do_fund_players()

        self.assertEqual(n1.balance, 0)
        self.assertEqual(n2.balance, 0)
        self.assertEqual(n3.balance, 0)

        self.assertEqual(g1.balance, 0)
        self.assertEqual(g2.balance, 0)
        self.assertEqual(g3.balance, 0)

        db_session.commit()

        for i in range(200):
            p1.fund(n1, 10)
            p1.fund(n2, 10)
            p1.fund(n3, 10)
            self.game.do_transfer()

        self.assertAlmostEqual(n1.balance, 607.0)
        self.assertAlmostEqual(n2.balance, 2597.0)
        self.assertAlmostEqual(n3.balance, 1005.0)

        self.assertAlmostEqual(g1.balance, 199.0)
        self.assertAlmostEqual(g2.balance, 597.0)
        self.assertAlmostEqual(g3.balance, 995.0)


    def testSimplePlayerCoinsNetwork(self):
        p1 = self.game.add_player('Matt')
        import pdb; pdb.set_trace()
        p1.balance = self.game.coins_per_budget_cycle
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        l1 = self.game.add_link(p1, po1, 50)
        db_session.commit()

        self.assertEqual(p1.balance, self.game.coins_per_budget_cycle)
        self.assertEqual(po1.balance, 0)

        import pdb; pdb.set_trace()
        p1.fund(po1, 60)
        self.assertEqual(po1.balance, 60)

#       db_session.commit()
#        for x in range(50):
#            self.game.do_transfer()

        self.assertEqual(p1.balance, self.game.coins_per_budget_cycle-60)
        self.assertEqual(po1.balance, 60)

    def testTransferGreaterThan100_300(self):
        p1 = self.game.add_player('Matt')
        p1.set_balance(self.game.coins_per_budget_cycle)
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        l1 = self.game.add_link(p1, po1, 3.0)
        db_session.commit()

        self.assertEqual(p1.balance, self.game.coins_per_budget_cycle)
        self.assertEqual(po1.balance, 0)

        for x in range(50):
            self.game.do_transfer()

        self.assertEqual(p1.balance, 850)
        self.assertEqual(po1.balance, 150)

    def testTransferGreaterThan100_350(self):
        p1 = self.game.add_player('Matt')
        p1.set_balance(self.game.coins_per_budget_cycle)
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        l1 = self.game.add_link(p1, po1, 3.5)
        db_session.commit()

        self.assertEqual(p1.balance, self.game.coins_per_budget_cycle)
        self.assertEqual(po1.balance, 0)

        for x in range(50):
            self.game.do_transfer()

        self.assertEqual(p1.balance, 829)
        self.assertEqual(po1.balance, 171)
        
    def testMoreComplexPlayerCoinsNetwork(self):
        p1 = self.game.add_player('Matt')
        p1.set_balance(self.game.coins_per_budget_cycle)
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        l1 = self.game.add_link(p1, po1, 0.5)
        po2 = self.game.add_policy('Pollution control', 0.1)
        l2 = self.game.add_link(p1, po2, 1.0)

        g1 = self.game.add_goal('World Peace', 0.5)
        g2 = self.game.add_goal('Clean Water', 0.5)
        l3 = self.game.add_link(po1, g1, 1.0)
        l4 = self.game.add_link(po2, g2, 2.0)

        db_session.commit()

        self.assertEqual(p1.balance, self.game.coins_per_budget_cycle)
        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_transfer()

        self.assertEqual(p1.balance, 853)
        self.assertEqual(po1.balance, 0)
        self.assertEqual(po2.balance, 0)

        self.assertEqual(g1.balance, 47)
        self.assertEqual(g2.balance, 100)

    def testMoreComplexPlayerCoinsNetworkWithFullTick(self):
        p1 = self.game.add_player('Matt')
        p1.set_balance(self.game.coins_per_budget_cycle)
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        l1 = self.game.add_link(p1, po1, 0.5)
        po2 = self.game.add_policy('Pollution control', 0.1)
        l2 = self.game.add_link(p1, po2, 1.0)

        g1 = self.game.add_goal('World Peace', 0.5)
        g2 = self.game.add_goal('Clean Water', 0.5)
        l3 = self.game.add_link(po1, g1, 1.0)
        l4 = self.game.add_link(po2, g2, 2.0)

        db_session.commit()

        self.assertEqual(p1.balance, self.game.coins_per_budget_cycle)
        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.tick()

        self.assertEqual(p1.balance, 848)
        self.assertEqual(po1.balance, 0)
        self.assertEqual(po2.balance, 0)

        self.assertEqual(g1.balance, 3)
        self.assertEqual(g2.balance, 44)

    def testTwoPlayersFundAPolicyEqually(self):
        p1 = self.game.add_player('Matt')
        p2 = self.game.add_player('Simon')
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        l1 = self.game.add_link(p1, po1, 1.0)
        l1 = self.game.add_link(p2, po1, 1.0)

        db_session.commit()

        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_transfer()

        self.assertEqual(p1.balance, 900)
        self.assertEqual(p2.balance, 900)

        self.assertEqual(po1.balance, 200)


    def testActivationLevelLow(self):
        p1 = self.game.add_player('Matt')
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        po1.activation = 0.7
        g1 = self.game.add_goal('World Peace', 0.5)
        l1 = self.game.add_link(p1, po1, 0.5)
        l2 = self.game.add_link(po1, g1, 1.0)

        db_session.commit()

        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_transfer()

        self.assertEqual(p1.balance, 956)
        self.assertEqual(po1.balance, 44)
        self.assertEqual(g1.balance, 0)

    def testActivationLevelHigh(self):
        p1 = self.game.add_player('Matt')
        p1.set_balance(self.game.coins_per_budget_cycle)
        po1 = self.game.add_policy('Arms Embargo', 0.1)
        po1.activation = 0.2
        g1 = self.game.add_goal('World Peace', 0.5)
        l1 = self.game.add_link(p1, po1, 0.5)
        l2 = self.game.add_link(po1, g1, 1.0)

        db_session.commit()

        self.assertEqual(po1.balance, 0)

        for x in range(100):
            self.game.do_transfer()

        self.assertEqual(p1.balance, 955)
        self.assertEqual(po1.balance, 0)
        self.assertEqual(g1.balance, 45)

    def testLoadJsonFile(self):
        json_file = open('example-graph.json', 'r')
        self.game.load_json(json_file)
        self.assertEqual(61, Edge.query.count())
        self.assertEqual(36, Node.query.count())
        self.assertEqual(30, Policy.query.count())
        self.assertEqual(6, Goal.query.count())
        


if __name__ == '__main__':
    unittest.main()

