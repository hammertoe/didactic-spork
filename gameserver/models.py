from sqlalchemy import Column, Integer, String, ForeignKey, \
    Float, CHAR, DateTime, create_engine, event, Table as SATable, inspect
from sqlalchemy.orm import relationship, sessionmaker, backref
from sqlalchemy.ext.declarative import declared_attr, as_declarative
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy import func
from sqlalchemy.orm.attributes import instance_state

from flask_sqlalchemy import SignallingSession

from gameserver.database import default_uuid, db
from gameserver.utils import pack_amount, checksum
from gameserver.wallet_sqlalchemy import WalletType, Wallet

from utils import random

db_session = db.session

# define the temp table
ledger = SATable("ledger", db.metadata,
                 Column("node_id", CHAR(36), primary_key=True),
                 Column("wallet", WalletType),
                 )    

#@event.listens_for(SignallingSession, 'before_flush')
def before_flush(session, flush_context, instances): # pragma: no cover
    # Only do this on MySQL
    if session.connection().engine.dialect.name != 'mysql':
        return

    temp_items = {}

    if session.dirty:

        for elem in session.dirty:
            if ( session.is_modified(elem, include_collections=False) ):
                state = inspect(elem)
                if state.committed_state.keys() == ['wallet']:
                    temp_items[elem.id] = elem.wallet
                    session.expire(elem, ['wallet'])

    if temp_items:

        # insert the temp values
        session.execute(ledger.insert().values([{"node_id": k, "wallet": v}
                                           for k, v in temp_items.items()]))

        # perform the update to the main table
        session.execute(Node.__table__
                        .update()
                        .values(wallet=ledger.c.wallet)
                        .where(Node.__table__.c.id == ledger.c.node_id))
        
        # drop temp table
        session.execute(ledger.delete())

@as_declarative()
class Base(object):
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()
    id = Column(CHAR(36), primary_key=True, default=default_uuid)


class Settings(Base):
    game_id = Column(String(100), primary_key=True)
    current_game_year = Column(Integer)
    current_game_year_start = Column(DateTime)
    next_game_year_start = Column(DateTime)
    budget_per_cycle = Column(Float)


class Table(Base):
    id = Column(CHAR(36),
                primary_key=True, default=default_uuid)

    name = Column(String(200))

    def __init__(self, name):
        self.id = default_uuid()
        self.name = name


class Client(Base):
    id = Column(CHAR(36),
                primary_key=True, default=default_uuid)

    name = Column(String(200))

    def __init__(self, name):
        self.id = default_uuid()
        self.name = name

class Node(Base):

    discriminator = Column(String(32))
    __mapper_args__ = {"polymorphic_on": discriminator}
    id = Column(CHAR(36),
                primary_key=True, default=default_uuid)

    name = Column(String(200))
    short_name = Column(String(50))
    group = Column(Integer)
    leak = Column(Float)
    node_type = Column(String(10))
    activation = Column(Float)
    max_level = Column(Integer)
    active_level = Column(Float)
    rank = Column(Integer)
    wallet = Column(Wallet.as_mutable(WalletType))
    
    def __init__(self, name, leak):
        self.id = default_uuid()
        self.name = name
        self.short_name = ''
        self.group = 0
        self.leak = leak
        self.activation = 0.0
        self.max_level = 0.0
        self.active_level = 0.0
        self.rank = 0
        self.wallet = Wallet()

    def higher_neighbors(self):
        return [x.higher_node for x in self.lower_edges]

    def lower_neighbors(self):
        return [x.lower_node for x in self.higher_edges]

    children = higher_neighbors
    parents = lower_neighbors

    def get_leak(self):
        leak = self.leak
        for edge in self.higher_edges:
            if edge.weight < 0:
                leak += abs(edge.weight)

        return leak

    @property
    def total_children_weight(self):
        return sum([max(e.weight,0) for e in self.lower_edges])

    @property
    def active_percent(self):
        if not self.activation:
            return 1.0
        return self.active_level / self.activation

    @property
    def active(self):
        return self.active_level >= self.activation

    @property
    def balance(self):
        wallet = self.wallet
        if wallet is not None:
            return wallet.total
        else:
            return 0.0

    @balance.setter
    def balance(self, amount):
        self.wallet = Wallet([(self.id, amount)])

    def do_leak(self):
        leak = self.get_leak()
        if self.balance and leak:
            self.wallet.leak(leak)

    @property
    def wallet_owner_map(self):
        return self.wallet.todict()

    def reset(self):
        self.wallet = Wallet()

    def do_propogate_funds(self, total_player_inflow):
        previous_balance = self.balance
        for edge in self.higher_edges:
            if getattr(edge, 'wallet', None):
                self.wallet &= edge.wallet
                # delete the wallet after we get from it
                edge.wallet = None 
        new_balance = self.balance
        max_level = self.max_level or 0
        if max_level and new_balance > max_level:
            # if we are over out level then remove excess
            self.wallet -= new_balance - max_level
        # set the active level on the node
        if total_player_inflow > 0:
            self.active_level = (new_balance - previous_balance) / total_player_inflow
        else:
            self.active_level = 1.0
        # check if we are active
        if self.active_level < self.activation:
            # not active so stop here
            return
        # yes we are active so distribute funds
        if self.balance <= 0:
            return # no balance to propogate

        total_balance = self.balance
        total_children_weight = self.total_children_weight

        if not total_children_weight:
            return # no children weight so return

        # max we can distribute is our balance or what children need
        current_outflow = min(total_children_weight, total_balance)

        # calculate the factor to multiply each player amount by
        total_out_factor = min(1.0, total_balance / total_children_weight)

        for edge in self.lower_edges:
            child = edge.higher_node
            amount = edge.weight
            if amount <= 0: # don't try to propogate negative values
                continue
            factored_amount = amount * total_out_factor

            # due to rounding errors in floats this is needed
            # otherwise we overdraw by like 5.10702591328e-15
            if factored_amount > self.balance:
                factored_amount = self.balance

            # create a wallet on the edge and transfer to it
            edge.wallet = Wallet()
            self.wallet.transfer(edge.wallet, factored_amount)


    def calc_rank(self):
        rank = 1
        for parent in self.parents():
            rank += parent.calc_rank()

        return rank

class Goal(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Goal'
      }

    id = Column(CHAR(36), ForeignKey(Node.id),
                primary_key=True, default=default_uuid)

class Policy(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Policy'
      }

    id = Column(CHAR(36), ForeignKey(Node.id),
                primary_key=True, default=default_uuid)



class Player(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Player'
      }

    id = Column(CHAR(36), ForeignKey(Node.id),
                primary_key=True, default=default_uuid)

    max_outflow = Column(Float)
    goal_funded = Column(Float, default=0.0)
    unclaimed_budget = Column(Float, default=0.0)

    goal_id = Column(
        CHAR(36),
        ForeignKey('goal.id')
        )

    goal = relationship(
        Goal,
        primaryjoin=goal_id == Goal.id,
        order_by='Goal.id',
        backref='players'
        )

    table_id = Column(
        CHAR(36),
        ForeignKey('table.id')
        )

    table = relationship(
        Table,
        primaryjoin=table_id == Table.id,
        order_by='Table.id',
        backref=backref('players', lazy='joined')
        )

    token = Column(CHAR(36),
                index=True, default=default_uuid)

    def __init__(self, name):
        self.id = default_uuid()
        self.name = name
        self.leak = 0.0
        self.max_outflow = 0.0
        self.rank = 0
        self.unclaimed_budget = 0.0
        self.token = default_uuid()
        self.wallet = Wallet()
        self.group = 8

    def transfer_funds_to_node(self, node, amount):
        self.wallet.transfer(node.wallet, amount)

    def fund(self, node, rate):
        # Do we already fund this node? If so change value
        f = db_session.query(Edge).filter(Edge.higher_node == node,
                                          Edge.lower_node == self).one_or_none()
        # check we are not exceeding our max fund outflow rate
        tmp_rate = self.total_funding
        if f is not None:
            tmp_rate -= f.weight
        tmp_rate += rate
        if tmp_rate > self.max_outflow:
            raise ValueError, "Exceeded max outflow rate"

        if f is not None:
            f.weight = rate
        else: # create new fund link
            f = Edge(self, node, rate)
            db_session.add(f)

    @property
    def funded_policies(self):
        return [ e.higher_node for e in self.lower_edges if e.weight ]

    @property
    def policies(self):
        return [ e.higher_node for e in self.lower_edges ]

    @property
    def active(self):
        return True

    @property
    def total_funding(self):
        return sum([ x.weight for x in self.lower_edges ])

    def transfer_funds(self):
        for fund in self.lower_edges:
            self.transfer_funds_to_node(fund.higher_node, fund.weight)

    def calc_goal_funded(self):
        goal = self.goal
        if not goal:
            return 0.0
        wallet = goal.wallet
        self.goal_funded =  wallet.get(self.id, 0.0)

    def do_propogate_funds(self, total_player_inflow):
        Node.do_propogate_funds(self, total_player_inflow)
        self.calc_goal_funded()
                               

    def offer_policy(self, policy_id, price):
        policy = db_session.query(Policy).filter(Policy.id == policy_id).one()
        if policy not in self.children():
            raise ValueError, "Seller doesn't have this policy"
        
        chk = checksum(self.id, policy_id, price, self.token)

        data = {'seller_id': self.id,
                'policy_id': policy_id,
                'price': price,
                'checksum': chk,
                }
        return data

    def buy_policy(self, seller, policy, price, chk):

        salt = seller.token
        if chk != checksum(seller.id, policy.id, price, salt):
            raise ValueError, "Checksum mismatch"

        # check the seller has the funds:
        if self.balance < price:
            raise ValueError, "Not enough funds for sale"

        # check the buyer doesn't alreay have this policy
        if policy in self.children():
            raise ValueError, "The buyer already has this policy"

        # sort out the money first
        seller.balance += price
        self.balance -= price
        
        # then give the buyer the policy
        self.fund(policy, 0.0)

        return True


class Edge(Base):

    lower_id = Column(
        CHAR(36),
        ForeignKey('node.id'),
        primary_key=True)

    higher_id = Column(
        CHAR(36),
        ForeignKey('node.id'),
        primary_key=True)

    lower_node = relationship(
        Node,
        primaryjoin=lower_id == Node.id,
        order_by='Node.id',
        backref='lower_edges')
#        backref=backref('lower_edges', lazy='subquery'))

    higher_node = relationship(
        Node,
        primaryjoin=higher_id == Node.id,
        order_by='Node.id',
#        lazy='joined',
        backref='higher_edges')

    weight = Column(Float())

    def __init__(self, n1, n2, weight):
        self.id = default_uuid()
        self.lower_node = n1
        self.higher_node = n2
        self.weight = weight
        self.wallet = None

    @property
    def current_flow(self):
        return self.lower_node.current_outflow


