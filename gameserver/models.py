from sqlalchemy import Column, Integer, String, ForeignKey, \
    Float, CHAR, create_engine, event, Table as SATable
from sqlalchemy.orm import relationship, sessionmaker, backref
from sqlalchemy.ext.declarative import declared_attr, as_declarative
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy import func
from sqlalchemy.orm.attributes import instance_state

from flask_sqlalchemy import SignallingSession

from gameserver.database import default_uuid, db
from gameserver.utils import pack_amount, checksum

from utils import random

db_session = db.session
db_session.ledgers = []

# define the temp table
ledger = SATable("ledger", db.metadata,
                 Column("wallet_id", CHAR(36), primary_key=True),
                 Column("new_balance", Float),
                 prefixes=["TEMPORARY"],
                 )    

@event.listens_for(SignallingSession, 'before_flush')
def before_flush(session, flush_context, instances):
    temp_items = {}

    if session.dirty:

        for elem in session.dirty:
            if ( session.is_modified(elem, include_collections=False) ):
                if isinstance(elem, Wallet):
                    instance_state(elem).committed_state.clear()
                    temp_items[elem.id] = elem.balance

    if temp_items:

        # create the temp table
        ledger.create(session.connection(), checkfirst=True)

        # insert the temp values
        session.execute(ledger.insert().values([{"wallet_id": k, "new_balance": v}
                                           for k, v in temp_items.items()]))

        # perform the update to the main table
        session.execute(Wallet.__table__
                        .update()
                        .values(balance=ledger.c.new_balance)
                        .where(Wallet.__table__.c.id == ledger.c.wallet_id))
        
        # drop temp table
        session.execute(ledger.delete())


@as_declarative()
class Base(object):
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()
    id = Column(CHAR(36), primary_key=True, default=default_uuid)


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
    leak = Column(Float)
    node_type = Column(String(10))
    activation = Column(Float)
    max_level = Column(Integer)
    rank = Column(Integer)
    
    def __init__(self, name, leak):
        self.id = default_uuid()
        self.name = name
        self.leak = leak
        self.activation = 0.0
        self.rank = 0

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
    def current_outflow(self):
        balance = self.balance or 0.0
        if balance == 0.0 or not self.active:
            return 0.0
        total = self.total_children_weight or 0.0
        if total < balance:
            return total
        else:
            return balance

    @property
    def total_children_weight(self):
        return sum([e.weight for e in self.lower_edges])

    @property
    def current_inflow(self):
        return sum([x.current_flow for x in self.higher_edges])

    @property
    def active(self):
        return self.current_inflow >= self.activation

    @property
    def balance(self):
        return float(sum([ wallet.balance for wallet in self.wallets_here ]))
 
    def do_leak(self):
        total = self.balance
        leak = 0.2
        for wallet in self.wallets_here:
            amount = wallet.balance * leak
            wallet.balance -= amount

    def get_wallet_by_owner(self, owner, create=True):
        wallet = None
        for w in self.wallets_here:
            if w.owner == owner:
                wallet = w
                break
            
        if wallet is None and create:
            wallet = Wallet(owner)
            self.wallets_here.append(wallet)
            db_session.add(wallet)

        return wallet

    def do_propogate_funds(self):
        # Check activation
        if not self.active or not self.balance or not self.current_outflow:
            return

        total_balance = self.balance
        ratio = max(total_balance/self.current_outflow, 1.0)

        for edge in self.lower_edges:
            child = edge.higher_node
            amount = edge.weight

            for wallet in self.wallets_here:
                subamount = (wallet.balance / total_balance) * amount * ratio
                subamount = max(subamount, wallet.balance)
                if subamount > 0.0:
                    wallet.transfer(child, subamount)

    def calc_rank(self):
        rank = len(self.parents())
        for parent in self.parents():
            rank += parent.calc_rank() + 1

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
        backref='players'
        )

    token = Column(CHAR(36),
                index=True, default=default_uuid)

    def __init__(self, name):
        self.id = default_uuid()
        self.name = name
        self.leak = 0.0
        self.max_outflow = 0.0
        self.token = default_uuid()

        # create a wallet for the player
        w = Wallet(self, 0.0)
        db_session.add(w)
        self.wallets_here.append(w)

    @property
    def wallet(self):
        return self.wallets_here[0]

    @property
    def balance(self):
        try:
            return self.wallet.balance
        except IndexError:
            return 0.0

    @balance.setter
    def balance(self, amount):
        self.wallet.balance = amount

    def transfer_funds_to_node(self, node, amount):
        self.wallet.transfer(node, amount)

    def fund(self, node, rate):
        # Do we already fund this node? If so change value
        f = db_session.query(Edge).filter(Edge.higher_node == node,
                                          Edge.lower_node == self).one_or_none()
        # check we are not exceeding our max fund outflow rate
        tmp_rate = self.current_outflow
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

    def transfer_funds(self):
        for fund in self.lower_edges:
            self.transfer_funds_to_node(fund.higher_node, fund.weight)

    @property
    def goal_funded(self):
        res = db_session.query(Wallet.balance).filter(Wallet.location == self.goal,
                                                      Wallet.owner == self).scalar()
        return res or 0.0

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

    higher_node = relationship(
        Node,
        primaryjoin=higher_id == Node.id,
        order_by='Node.id',
        backref='higher_edges')

    weight = Column(Float())

    def __init__(self, n1, n2, weight):
        self.id = default_uuid()
        self.lower_node = n1
        self.higher_node = n2
        self.weight = weight

    @property
    def current_flow(self):
        return self.lower_node.current_outflow


class Wallet(Base):

    owner_id = Column(
        CHAR(36),
        ForeignKey('node.id'),
        index=True)

    owner = relationship(
        'Player',
        primaryjoin=owner_id == Node.id,
        backref='wallets_owned')

    location_id = Column(
        CHAR(36),
        ForeignKey('node.id'),
        index=True)

    location = relationship(
        'Node',
        primaryjoin=location_id == Node.id,
        backref='wallets_here')

    balance = Column(Float)

    def __init__(self, owner, balance=None):
        self.id = default_uuid()
        self.owner = owner
        self.balance = balance or 0.0

    def transfer(self, dest, amount):
        if type(dest) == type(Wallet):
            self.transfer_to_wallet(dest, amount)
        else:
            self.transfer_to_node(dest, amount) 

    def transfer_to_wallet(self, dest, amount):
        # check we have funds for this transfer
        if amount > self.balance:
            raise ValueError, "Insufficient balance for transfer"

        # update the balances of source and dest
        self.balance -= amount
        dest.balance += amount

    def transfer_to_node(self, node, amount):
        # check we have funds for this transfer
        if amount > self.balance:
            raise ValueError, "Insufficient balance for transfer"

        # get dest wallet, create one if non-existant
        dest_wallet = node.get_wallet_by_owner(self.owner)

        # do the transfer between wallets
        self.transfer_to_wallet(dest_wallet, amount)

        # If wallet is empty at the end, delete it
        if self.balance == 0.0:
            db_session.delete(self)
            
    def __repr__(self):
        return "<Wallet: {} balance {:.2f}>".format(self.id, self.balance)
