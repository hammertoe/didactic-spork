import json
import random

#from database import db_session
from gameserver.database import db
from gameserver.models import Node, Player, Policy, Goal, Edge, Wallet

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

    def create_player(self, name):
        p = Player(name)
        p.max_outflow = self.standard_max_player_outflow
        p.goal = self.get_random_goal()
        for policy in self.get_n_policies(5):
            self.add_fund(p, policy, 0)

        db_session.add(p)
        return p

    def get_players(self):
        return db_session.query(Player).all()

    def get_player(self, id):
        return db_session.query(Player).filter(Player.id == id).one_or_none()

    def add_policy(self, name, leak):
        p = Policy(name, leak)
        db_session.add(p)
        return p

    def get_policy(self, id):
        return db_session.query(Policy).filter(Policy.id == id).one()

    def get_policies(self):
        return db_session.query(Policy).all()

    def add_goal(self, name, leak):
        g = Goal(name, leak)
        db_session.add(g)
        return g

    def get_goal(self, id):
        return db_session.query(Goal).filter(Goal.id == id).one()        

    def get_goals(self):
        return db_session.query(Goal).all()

    def get_random_goal(self):
        goals = self.get_goals()
        if goals:
            return(random.choice(goals))

    def get_n_policies(self, goal, n=5):
        # for now just get n random policies
        policies = self.get_policies()
        if not policies:
            return []
        random.shuffle(policies)
        return policies[:n]

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

    def set_funding(self, id, funding = None):
        if not funding:
            return
        funding = { x['to_id']:x['amount'] for x in funding }
        player = self.get_player(id)
        for fund in player.lower_edges:
            dest_id = fund.higher_node.id
            fund.weight = funding.get(dest_id, 0.0)

    def get_funding(self,id):
        player = self.get_player(id)
        funds = []
        for fund in player.lower_edges:
            dest_id = fund.higher_node.id
            funds.append({'from_id':id, 'to_id': dest_id, 'amount': fund.weight})
            
        return funds

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

    def node_to_dict(self, node):
        connections = []
        for edge in node.higher_edges:
            connections.append(
                {"from_id": edge.lower_node.id,
                 "to_id": node.id,
                 "weight": edge.weight,
                 }
                )

        data = {"id": node.id,
                "name": node.name,
                "leakage": node.leak,
                "max_amount": node.max_level,
                "activation_amount": node.activation,
                "balance": node.balance,
                "connections": connections
                }

        return data


    def get_network(self):
        goals = db_session.query(Goal).all()
        policies = db_session.query(Policy).all()
        goals = [self.node_to_dict(g) for g in goals ]
        policies = [self.node_to_dict(p) for p in policies ]
        return dict(goals=goals, policies=policies)



    def create_network(self, network):
        
        goals = network['goals']
        policies = network['policies']

        id_mapping = {}
        links = []
        
        for policy in policies:
            p = self.add_policy(policy['name'], policy['leakage'])
            p.id = policy['id']
            p.max_level = policy['max_amount']
            p.activation = policy['activation_amount']
            id_mapping[p.id] = p

            for conn in policy['connections']:
                a = conn['from_id']
                b = conn['to_id']
                w = conn['weight']
                links.append((a,b,w))

        for goal in goals:
            g = self.add_goal(goal['name'], goal['leakage'])
            g.id = goal['id']
            g.max_level = goal['max_amount']
            g.activation = goal['activation_amount']
            id_mapping[g.id] = g

            for conn in goal['connections']:
                a = conn['from_id']
                b = conn['to_id']
                w = conn['weight']
                links.append((a,b,w))

        for a,b,w in links:
            a = id_mapping[a]
            b = id_mapping[b]
            self.add_link(a,b,w)

        db_session.commit()
