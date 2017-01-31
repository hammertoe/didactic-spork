import json
from gameserver.utils import random, node_to_dict

from gameserver.database import db
from gameserver.models import Node, Player, Policy, Goal, Edge, Table, Client

from sqlalchemy.orm import joinedload, subqueryload
from sqlalchemy import func

db_session = db.session

class Game:

    def __init__(self):
        self.money_per_budget_cycle = 150000
        self.standard_max_player_outflow = 100
        self.default_offer_price = 20000

    def validate_api_key(self, token):
        return db_session.query(Client.name).filter(Client.id == token).scalar()

    @property
    def num_players(self):
        return db_session.query(Player).count()

    def rank_nodes(self):
        for node in self.get_nodes():
            node.rank = node.calc_rank()

    def get_nodes(self):
        return db_session.query(Node).options(
            joinedload('higher_edges'),
            joinedload('lower_edges')).order_by(Node.rank).all()
    
    def do_leak(self):
        for node in self.get_nodes():
            node.do_leak()

    def do_propogate_funds(self):
        for node in self.get_nodes():
            node.do_propogate_funds()

    def do_replenish_budget(self):
        for player in db_session.query(Player).all():
            player.balance = self.money_per_budget_cycle

    def tick(self):
        for node in self.get_nodes():
            node.do_leak()
            node.do_propogate_funds()

    def top_players(self, max_num=20):
        players = self.get_players()
        return db_session.query(Player).order_by(Player.goal_funded.desc()).all()

    def create_player(self, name):
        p = Player(name)
        p.max_outflow = self.standard_max_player_outflow
        p.balance = self.money_per_budget_cycle
        p.goal = self.get_random_goal()
        for policy in self.get_n_policies(5):
            self.add_fund(p, policy, 0)

        db_session.add(p)
        return p

    def get_total_inflow(self):
        return db_session.query(func.sum(Player.max_outflow)).scalar() or 0.0
    
    def get_players(self):
        return db_session.query(Player).all()

    def get_player(self, id):
        return db_session.query(Player).filter(Player.id == id).one_or_none()

    def add_policy(self, name, leak):
        p = Policy(name, leak)
        db_session.add(p)
        return p

    def get_policy(self, id):
        return db_session.query(Policy).filter(Policy.id == id).one_or_none()

    def get_policies(self):
        return db_session.query(Policy).order_by(Policy.name).all()

    def offer_policy(self, seller_id, policy_id, price):
        seller = self.get_player(seller_id)
        return seller.offer_policy(policy_id, price)

    def buy_policy(self, buyer_id, data):
        buyer = self.get_player(buyer_id)
        seller = self.get_player(data['seller_id'])
        policy = self.get_policy(data['policy_id'])
        price = data['price']
        chk = data['checksum']

        if not (buyer and seller and policy):
            raise ValueError, "Cannot find buyer, seller, or policy"

        return buyer.buy_policy(seller, policy, price, chk)
        
    def add_goal(self, name, leak):
        g = Goal(name, leak)
        db_session.add(g)
        return g

    def get_goal(self, id):
        return db_session.query(Goal).filter(Goal.id == id).one()        

    def get_goals(self):
        return db_session.query(Goal).order_by(Goal.name).all()

    def get_node(self, id):
        return db_session.query(Node).filter(Node.id == id).one_or_none()

    def get_wallets_by_location(self, id):
        node = self.get_node(id)
        return node.wallet.todict()

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

    def add_client(self, name):
        client = Client(name)
        db_session.add(client)
        return client

    def add_link(self, a, b, weight):
        l = Edge(a, b, weight)
        db_session.add(l)
        return l

    def add_fund(self, player, node, amount):
        return player.fund(node, amount)

    def set_funding(self, id, funding = None):
        if not funding:
            return
        funding = { x['to_id']:x['amount'] for x in funding }
        player = self.get_player(id)
        if sum(funding.values()) > player.max_outflow:
            raise ValueError, "Sum of funds exceeds max allowed for player"

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

    def create_table(self, name):
        table = Table(name)
        db_session.add(table)
        return table

    def get_table(self, id):
        return db_session.query(Table).filter(Table.id == id).one_or_none()

    def get_tables(self):
        return db_session.query(Table).all()

    def get_network_for_table(self, id):

        table = self.get_table(id)
        if not table:
            return None
        return self.get_network(table.players)

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

        self.rank_nodes()

        db_session.commit()

    def get_network(self, players=None):

        def node_recurse_generator(node):
            yield node
            for n in node.children():
                for rn in node_recurse_generator(n):
                    yield rn 

        if not players:
            goals = db_session.query(Goal).options(
                joinedload('lower_edges')).all()
            policies = db_session.query(Policy).options(
                joinedload('lower_edges')).all()
        else:
            goals = set()
            policies = set()
            for player in players:
                goals.add(player.goal)
                p = [ x for x in node_recurse_generator(player) \
                      if isinstance(x, Policy) ]
                policies.update(p)
            
        return dict(goals=goals, policies=policies)



    def create_network(self, network):
        
#        db_session.execute(Edge.__table__.delete())
#        db_session.execute(Player.__table__.delete())
#        db_session.execute(Goal.__table__.delete())
#        db_session.execute(Policy.__table__.delete())

        goals = network['goals']
        policies = network['policies']
        edges = network['edges']

        id_mapping = {}
        links = []
        
        for policy in policies:
            p = self.add_policy(policy['name'], policy.get('leakage', 0))
            p.id = policy['id']
            p.max_level = policy.get('max_amount', 0)
            p.activation = policy.get('activation_amount', 0)
            id_mapping[p.id] = p

        for goal in goals:
            g = self.add_goal(goal['name'], goal.get('leakage', 0))
            g.id = goal['id']
            g.max_level = goal.get('max_amount', 0)
            g.activation = goal.get('activation_amount', 0)
            id_mapping[g.id] = g


        for edge in edges:
            i = id_mapping
            l = self.add_link(i[edge['source']],
                              i[edge['target']],
                              edge['weight'],
                              )

        self.rank_nodes()

        db_session.commit()

