import random

from database import db_session
from models import Node, Player, Policy, Goal, Edge, Coin
from utils import weighted_choice


class Game:

    def do_leak(self):
        pass

    def do_transfer(self):
        pass

    def do_add(self):
        pass

    def tick(self):
        do_leak()
        do_transfer()
        do_add()

    def add_player(self, name):
        p = Player(name)
        db_session.add(p)
        db_session.commit()
        return p

    def get_player(self, id):
        return Player.query.filter(Player.id == id).first()

    def add_policy(self, name, leak):
        p = Policy(name, leak)
        db_session.add(p)
        db_session.commit()
        return p

    def get_policy(self, id):
        return Policy.query.filter(Policy.id == id).first()

    def add_goal(self, name, leak):
        g = Goal(name, leak)
        db_session.add(g)
        db_session.commit()
        return g

    def get_goal(self, id):
        return Goal.query.filter(Goal.id == id).first()

    def add_link(self, a, b, weight):
        l = Edge(a, b, weight)
        db_session.add(l)
        db_session.commit()
        return l

    def get_link(self, id):
        return Edge.query.filter(Edge.id == id).first()

    def add_coin(self, player):
        c = Coin(player)
        db_session.add(c)
        db_session.commit()
        return c
