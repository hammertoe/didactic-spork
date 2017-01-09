import json
import random

#from database import db_session
from database import db
from models import Node, Player, Policy, Goal, Edge, Wallet

db_session = db.session

class Game:

    def __init__(self):
        self.coins_per_budget_cycle = 150000
        self.standard_max_player_outflow = 100

    @property
    def num_players(self):
        return db_session.query(Player).count()

    def do_leak(self):
        for node in db_session.query(Node).order_by(Node.id).all():
            node.do_leak()

    def do_propogate_funds(self):
        nodes = db_session.query(Node).all()
        for node in sorted(nodes, key=lambda n: n.rank):
            node.do_propogate_funds()

    def do_replenish_budget(self):
        for player in db_session.query(Player).all():
            player.balance = self.coins_per_budget_cycle

    def tick(self):
        self.do_leak()
        self.do_propogate_funds()

    def add_player(self, name):
        p = Player(name)
        p.max_outflow = self.standard_max_player_outflow
        db_session.add(p)
        db_session.commit()
        return p

    def get_players(self):
        return db_session.query(Player).all()

    def get_player(self, id):
        return db_session.query(Player).filter(Player.id == id).one()

    def add_policy(self, name, leak):
        p = Policy(name, leak)
        db_session.add(p)
        return p


    def get_policy(self, id):
        return db_session.query(Policy).filter(Policy.id == id).one()

    def add_goal(self, name, leak):
        g = Goal(name, leak)
        db_session.add(g)
        return g

    def get_goal(self, id):
        return db_session.query(Goal).filter(Goal.id == id).one()

    def add_link(self, a, b, weight):
        l = Edge(a, b, weight)
        db_session.add(l)
        return l

    def get_link(self, id):
        return db_session.query(Edge).filter(Edge.id == id).one()

    def add_fund(self, player, node, amount):
        return player.fund(node, amount)

    def get_fund(self, id):
        return db_session.query(Fund).filter(Fund.id == id).one()

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
