import unittest
import os
import random
import utils

if not os.environ.has_key('SQLALCHEMY_DATABASE_URI'):
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
from game import Game
from database import clear_db, init_db, db_session
from models2 import Node, Player, Goal, Policy, Wallet, Edge

class GameNetworkTests(unittest.TestCase):


    def setUp(self):
        utils.random.seed(0)
        init_db()
        self.game = Game()
 
    def tearDown(self):
        clear_db()

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
        po1.wallets_here.append(w1)

        self.assertEqual(w1.location, po1)
        self.assertEqual(po1.wallets_here, [w1,])


    def testAddGoal(self):

        g = self.game.add_goal('World Peace', 0.5)

        self.assertEqual(self.game.get_goal(g.id), g)
        self.assertEqual(self.game.get_goal(g.id).leak, 0.5)

    def testAddWalletToGoal(self):

        g = self.game.add_goal('World Peace', 0.5)
        p1 = self.game.add_player('Matt')
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
        p1 = self.game.add_player('Matt')

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
        p1 = self.game.add_player('Matt')
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
        p1 = self.game.add_player('Matt')
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
        p1 = self.game.add_player('Matt')
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
        p1 = self.game.add_player('Matt')
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


if __name__ == '__main__':
    unittest.main()
