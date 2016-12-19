import unittest
import os
import random

os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
from game import Game
from database import init_db

init_db()

class GameNetworkTests(unittest.TestCase):

    def setUp(self):
        self.game = Game()

    def testAddPlayer(self):

        p = self.game.add_player('Matt')
        self.assertEqual(self.game.get_player(p.id), p)

    def testAddPolicy(self):

        p = self.game.add_policy('Arms Embargo', 0.1)
        self.assertEqual(self.game.get_policy(p.id), p)
        self.assertEqual(self.game.get_policy(p.id).leak, 0.1)

    def testAddGoal(self):

        g = self.game.add_goal('World Peace', 0.5)
        self.assertEqual(self.game.get_goal(g.id), g)
        self.assertEqual(self.game.get_goal(g.id).leak, 0.5)

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

    def testAddCoins(self):
        n1 = self.game.add_policy('Policy 1', 0.1)
        p1 = self.game.add_player('Matt')

        self.assertEqual(n1.balance(), 0)

        c1 = self.game.add_coin(p1)

        self.assertEqual(n1.balance(), 0)

        c1.location = n1

        self.assertEqual(n1.balance(), 1)

        c2 = self.game.add_coin(p1)
        c2.location = n1

        self.assertEqual(n1.balance(), 2)

    def testNodeLeak100(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        p1 = self.game.add_player('Matt')
        c1 = self.game.add_coin(p1)
        c1.location = n1
        c2 = self.game.add_coin(p1)
        c2.location = n1

        self.assertEqual(n1.balance(), 2)
        n1.do_leak()
        self.assertEqual(n1.balance(), 1)
        n1.do_leak()
        self.assertEqual(n1.balance(), 0)
        n1.do_leak()
        self.assertEqual(n1.balance(), 0)        

    def testNodeLeak0(self):
        n1 = self.game.add_policy('Policy 1', 0.0)
        p1 = self.game.add_player('Matt')
        c1 = self.game.add_coin(p1)
        c1.location = n1
        c2 = self.game.add_coin(p1)
        c2.location = n1

        self.assertEqual(n1.balance(), 2)
        n1.do_leak()
        self.assertEqual(n1.balance(), 2)
        n1.do_leak()
        self.assertEqual(n1.balance(), 2)
        n1.do_leak()
        self.assertEqual(n1.balance(), 2)        

    def testGameLeak100(self):
        n1 = self.game.add_policy('Policy 1', 1.0)
        n2 = self.game.add_policy('Policy 2', 1.0)
        p1 = self.game.add_player('Matt')
        c1 = self.game.add_coin(p1)
        c1.location = n1
        c2 = self.game.add_coin(p1)
        c2.location = n1
        c3 = self.game.add_coin(p1)
        c3.location = n2

        self.assertEqual(n1.balance(), 2)
        self.assertEqual(n2.balance(), 1)

        self.game.do_leak()
        self.assertEqual(n1.balance(), 1)
        self.assertEqual(n2.balance(), 0)

    def testGameLeak0_100(self):
        n1 = self.game.add_policy('Policy 1', 0.0)
        n2 = self.game.add_policy('Policy 2', 1.0)
        p1 = self.game.add_player('Matt')
        c1 = self.game.add_coin(p1)
        c1.location = n1
        c2 = self.game.add_coin(p1)
        c2.location = n1
        c3 = self.game.add_coin(p1)
        c3.location = n2

        self.assertEqual(n1.balance(), 2)
        self.assertEqual(n2.balance(), 1)

        self.game.do_leak()
        self.assertEqual(n1.balance(), 2)
        self.assertEqual(n2.balance(), 0)

    def testGameLeak50(self):
        n1 = self.game.add_policy('Policy 1', 0.5)
        n2 = self.game.add_policy('Policy 2', 0.5)
        p1 = self.game.add_player('Matt')
        c1 = self.game.add_coin(p1)
        c1.location = n1
        c2 = self.game.add_coin(p1)
        c2.location = n1
        c3 = self.game.add_coin(p1)
        c3.location = n2

        self.assertEqual(n1.balance(), 2)
        self.assertEqual(n2.balance(), 1)

        # Seed the RNG so that the tests below are deteministic
        random.seed(0)
        self.game.do_leak()
        self.assertEqual(n1.balance(), 1)
        self.assertEqual(n2.balance(), 1)

        self.game.do_leak()
        self.assertEqual(n1.balance(), 1)
        self.assertEqual(n2.balance(), 1)

        self.game.do_leak()
        self.assertEqual(n1.balance(), 0)
        self.assertEqual(n2.balance(), 0)

        self.game.do_leak()
        self.assertEqual(n1.balance(), 0)
        self.assertEqual(n2.balance(), 0)

    def testNodeTransfer100(self):
        n1 = self.game.add_policy('Policy 1', 0.5)
        n2 = self.game.add_policy('Policy 2', 0.5)
        p1 = self.game.add_player('Matt')
        c1 = self.game.add_coin(p1)
        c1.location = n1
        c2 = self.game.add_coin(p1)
        c2.location = n1
        c3 = self.game.add_coin(p1)
        c3.location = n2
        l1 = self.game.add_link(n1, n2, 1.0)

        self.assertEqual(n1.balance(), 2)
        self.assertEqual(n2.balance(), 1)
        
        n1.do_transfer()

        self.assertEqual(n1.balance(), 1)
        self.assertEqual(n2.balance(), 2)

    def testNodeTransfer0(self):
        n1 = self.game.add_policy('Policy 1', 0.5)
        n2 = self.game.add_policy('Policy 2', 0.5)
        p1 = self.game.add_player('Matt')
        c1 = self.game.add_coin(p1)
        c1.location = n1
        c2 = self.game.add_coin(p1)
        c2.location = n1
        c3 = self.game.add_coin(p1)
        c3.location = n2
        l1 = self.game.add_link(n1, n2, 0.0)

        self.assertEqual(n1.balance(), 2)
        self.assertEqual(n2.balance(), 1)
        
        n1.do_transfer()

        self.assertEqual(n1.balance(), 2)
        self.assertEqual(n2.balance(), 1)

    def testGameTransfer100(self):
        n1 = self.game.add_policy('Policy 1', 0.5)
        n2 = self.game.add_policy('Policy 2', 0.5)
        n3 = self.game.add_policy('Policy 3', 0.5)
        p1 = self.game.add_player('Matt')
        c1 = self.game.add_coin(p1)
        c1.location = n1
        c2 = self.game.add_coin(p1)
        c2.location = n1
        c3 = self.game.add_coin(p1)
        c3.location = n2
        l1 = self.game.add_link(n1, n2, 1.0)
        l2 = self.game.add_link(n1, n3, 1.0)

        self.assertEqual(n1.balance(), 2)
        self.assertEqual(n2.balance(), 1)
        self.assertEqual(n3.balance(), 0)
        
        self.game.do_transfer()

        self.assertEqual(n1.balance(), 0)
        self.assertEqual(n2.balance(), 2)
        self.assertEqual(n3.balance(), 1)

    def testGameTransfer50(self):
        n1 = self.game.add_policy('Policy 1', 0.5)
        n2 = self.game.add_policy('Policy 2', 0.5)
        n3 = self.game.add_policy('Policy 3', 0.5)
        p1 = self.game.add_player('Matt')

        for x in range(100):
            self.game.add_coin(p1).location = n1

        l1 = self.game.add_link(n1, n2, 0.5)
        l2 = self.game.add_link(n1, n3, 0.5)

        self.assertEqual(n1.balance(), 100)
        self.assertEqual(n2.balance(), 0)
        self.assertEqual(n3.balance(), 0)

        # Seed the RNG so that the tests below are deteministic
        random.seed(1)

        for x in range(50):
            self.game.do_transfer()

        self.assertEqual(n1.balance(), 55)
        self.assertEqual(n2.balance(), 20)
        self.assertEqual(n3.balance(), 25)

    def testGameTransfer50_goal(self):
        n1 = self.game.add_policy('Policy 1', 0.5)
        n2 = self.game.add_policy('Policy 2', 0.5)
        n3 = self.game.add_policy('Policy 3', 0.5)
        g1 = self.game.add_goal('Goal 1', 0.5)
        g2 = self.game.add_goal('Goal 2', 0.5)
        g3 = self.game.add_goal('Goal 3', 0.5)
        p1 = self.game.add_player('Matt')

        for x in range(100):
            self.game.add_coin(p1).location = n1

        l1 = self.game.add_link(n1, n2, 0.5)
        l2 = self.game.add_link(n1, n3, 0.5)

        l3 = self.game.add_link(n2, g1, 0.5)
        l4 = self.game.add_link(n3, g2, 0.5)
        l5 = self.game.add_link(n3, g3, 0.5)

        self.assertEqual(n1.balance(), 100)
        self.assertEqual(n2.balance(), 0)
        self.assertEqual(n3.balance(), 0)

        # Seed the RNG so that the tests below are deteministic
        random.seed(1)

        for x in range(50):
            self.game.do_transfer()

        self.assertEqual(n1.balance(), 53)
        self.assertEqual(n2.balance(), 4)
        self.assertEqual(n3.balance(), 0)

        self.assertEqual(g1.balance(), 18)
        self.assertEqual(g2.balance(), 14)
        self.assertEqual(g3.balance(), 11)


if __name__ == '__main__':
    unittest.main()

