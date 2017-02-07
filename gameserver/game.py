import json
from gameserver.utils import random, node_to_dict, update_node_from_dict

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
        # preload players
        junk = db_session.query(Player).all()
        return db_session.query(Node).options(
            joinedload('higher_edges'),
            joinedload('lower_edges')).order_by(Node.rank).all()
    
    def do_leak(self):
        for node in self.get_nodes():
            node.do_leak()

    @property
    def total_players_inflow(self):
        return db_session.query(func.sum(Player.max_outflow)).scalar() or 0.0

    def do_propogate_funds(self):
        if hasattr(self, '_needs_ranking'):
            self.rank_nodes()
            del self._needs_ranking
        total_players_inflow = self.total_players_inflow
        for node in self.get_nodes():
            node.do_propogate_funds(total_players_inflow)

    def do_replenish_budget(self):
        for player in db_session.query(Player).all():
            player.balance = self.money_per_budget_cycle

    def tick(self):
        if hasattr(self, '_needs_ranking'):
            self.rank_nodes()
            del self._needs_ranking
        total_players_inflow =self.total_players_inflow
        for node in self.get_nodes():
            node.do_leak()
            node.do_propogate_funds(total_players_inflow)

    def top_players(self, max_num=20):
        return db_session.query(Player).order_by(Player.goal_funded.desc()).limit(max_num).all()

    def create_player(self, name):
        p = Player(name)
        p.max_outflow = self.standard_max_player_outflow
        p.balance = self.money_per_budget_cycle
        p.goal = self.get_random_goal()
        for policy in self.get_n_policies(5):
            self.add_fund(p, policy, 0)

        db_session.add(p)
        self._needs_ranking = 1
        return p

    def get_players(self):
        return db_session.query(Player).all()

    def get_player(self, id):
        return db_session.query(Player).options(
            joinedload('lower_edges'),
            joinedload('goal'),
            joinedload('lower_edges.higher_node')).filter(Player.id == id).one_or_none()

    def add_policy(self, name, leak=0):
        p = Policy(name, leak)
        db_session.add(p)
        self._needs_ranking = 1
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
        
    def add_goal(self, name, leak=0):
        g = Goal(name, leak)
        db_session.add(g)
        self._needs_ranking = 1
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
        self._needs_ranking = 1
        return l

    def get_link(self, id):
        return db_session.query(Edge).filter(Edge.id == id).one_or_none()

    def add_fund(self, player, node, amount):
        self._needs_ranking = 1
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

    def create_network(self, data):
        
        goals = data['goals']
        policies = data['policies']

        id_mapping = {}
        links = []
        
        for policy in policies:
            p = self.add_policy(policy['name'])
            update_node_from_dict(p, policy)
            id_mapping[policy['id']] = p

            for conn in policy['connections']:
                i = conn['id']
                a = conn['from_id']
                b = conn['to_id']
                w = conn['weight']
                links.append((i,a,b,w))

        for goal in goals:
            g = self.add_goal(goal['name'])
            update_node_from_dict(g, goal)
            id_mapping[goal['id']] = g

            for conn in goal['connections']:
                i = conn['id']
                a = conn['from_id']
                b = conn['to_id']
                w = conn['weight']
                links.append((i,a,b,w))

        for i,a,b,w in links:
            a = id_mapping[a]
            b = id_mapping[b]
            l = self.add_link(a,b,w)
            l.id = i

        self.rank_nodes()

    def get_network(self, players=None):

        def node_recurse_generator(node):
            yield node
            for n in node.children():
                for rn in node_recurse_generator(n):
                    yield rn 

        if not players:
            goals = db_session.query(Goal).options(
                joinedload('lower_edges')).order_by(Goal.name).all()
            policies = db_session.query(Policy).options(
                joinedload('lower_edges'),
                joinedload('lower_edges.higher_node')).order_by(Policy.name).all()
        else:
            # preload goals and policies
            junk2 = db_session.query(Node).options(
                joinedload('lower_edges')).all()
            nodes = set()
            for player in players:
                nodes.add(player)
                nodes.add(player.goal)
                for policy in player.funded_policies:
                    nodes.update(node_recurse_generator(policy))

            goals = [ x for x in nodes if isinstance(x, Goal) ]
            policies = [ x for x in nodes if isinstance(x, Policy) ]
            
        return dict(goals=goals, policies=policies)

    def update_network(self, network):
        goals = network['goals']
        policies = network['policies']
        links = []

        for node in goals+policies:
            n = self.get_node(node['id'])
            if not n:
                return "node id {id} name {name} not found in network".format(**node)
            update_node_from_dict(n, node)

            for conn in node['connections']:
                links.append(conn)

        for link in links:
            l = self.get_link(link['id'])
            if not l:
                return "link id {id} not found in network".format(**link)
            l.weight = link['weight']

        self.rank_nodes()
        
