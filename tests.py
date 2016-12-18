import unittest
import os

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

if __name__ == '__main__':
    unittest.main()

