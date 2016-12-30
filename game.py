import json
import random

from database import db_session
from models import Node, Player, Policy, Goal, Edge, Wallet

class Game:

    def __init__(self):
        self.coins_per_budget_cycle = 150000
        self.standard_max_player_outflow = 100

    def do_leak(self):
        for node in Node.query.order_by(Node.id).all():
            node.do_leak(commit=False)
        db_session.commit()

    def do_transfer(self):
        for node in Policy.query.order_by(Node.id).all():
            node.do_transfer(commit=False)
        db_session.commit()

    def do_fund_players(self):
        for player in Player.query.all():
            player.balance = self.coins_per_budget_cycle

    def tick(self):
        self.do_leak()
        self.do_transfer()

    def add_player(self, name):
        p = Player(name)
        db_session.add(p)
        return p

    def get_player(self, id):
        return Player.query.filter(Player.id == id).first()

    def add_policy(self, name, leak):
        p = Policy(name, leak)
        db_session.add(p)
        return p


    def get_policy(self, id):
        return db_session.query(Policy).filter(Policy.id == id).first()

    def add_goal(self, name, leak):
        g = Goal(name, leak)
        db_session.add(g)
        return g

    def get_goal(self, id):
        return Goal.query.filter(Goal.id == id).first()

    def add_link(self, a, b, weight):
        l = Edge(a, b, weight)
        db_session.add(l)
        return l

    def get_link(self, id):
        return Edge.query.filter(Edge.id == id).first()

    def add_wallet(self, player, amount=None):
        w = Wallet(player, amount)
        db_session.add(w)
        return w

    def load_json(self, json_file):
        data = json.load(json_file)
        
        goals = data['Goals']
        policies = data['Policies']

        id_mapping = {}
        links = []
        
        for policy in policies:
            p = self.add_policy(policy['Name'], policy['Leakage'])
            p.max_level = policy['MaxAmount']
            p.activation = policy['ActivationAmount']
            id_mapping[policy['Id']] = p

        for goal in goals:
            g = self.add_goal(goal['Name'], goal['Leakage'])
            g.max_level = goal['MaxAmount'] 
            g.activation = goal['ActivationAmount']  
            id_mapping[goal['Id']] = g

            for conn in goal['Connections']:
                a = conn['FromId']
                b = conn['ToId']
                w = conn['Weight']
                links.append((a,b,w))

        for a,b,w in links:
            a = id_mapping[a]
            b = id_mapping[b]
            self.add_link(a,b,w)

        db_session.commit()
