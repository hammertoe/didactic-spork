from sqlalchemy import Column, Integer, String, ForeignKey, \
    Float, create_engine
from sqlalchemy.orm import relationship, sessionmaker, backref
from sqlalchemy.ext.declarative import declared_attr, as_declarative
from sqlalchemy.ext.associationproxy import association_proxy

from gameserver.database import default_uuid, db

from utils import random

db_session = db.session

@as_declarative()
class Base(object):
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()
    id = Column(String(36), primary_key=True, default=default_uuid)

class Table(Base):
    discriminator = Column(String(32))
    __mapper_args__ = {"polymorphic_on": discriminator}
    id = Column(String(36),
                primary_key=True, default=default_uuid)

    name = Column(String(200))

    def __init__(self, name):
        self.id = default_uuid()
        self.name = name

class Node(Base):

    discriminator = Column(String(32))
    __mapper_args__ = {"polymorphic_on": discriminator}
    id = Column(String(36),
                primary_key=True, default=default_uuid)

    name = Column(String(200))
    leak = Column(Float)
    node_type = Column(String(10))
    activation = Column(Float)
    max_level = Column(Integer)

    def __init__(self, name, leak):
        self.id = default_uuid()
        self.name = name
        self.leak = leak
        self.activation = 0.0

    def higher_neighbors(self):
        return [x.higher_node for x in self.lower_edges]

    def lower_neighbors(self):
        return [x.lower_node for x in self.higher_edges]

    children = higher_neighbors
    parents = lower_neighbors

    @property
    def current_outflow(self):
        if not self.active:
            return 0.0
        total = sum([x.weight for x in self.lower_edges])
        return total if total < self.balance else self.balance

    @property
    def current_inflow(self):
        return sum([x.current_flow for x in self.higher_edges])

    @property
    def active(self):
        return self.current_inflow >= self.activation

    @property
    def balance(self):
#        res = db_session.execute("SELECT sum(balance) AS balance FROM wallet WHERE location_id = :id", {'id': self.id})
#        return res.fetchall()[0][0] or 0.0
        
        return float(sum([ wallet.balance for wallet in self.wallets_here ]))
        

    def do_leak(self):
        total = self.balance
        for wallet in self.wallets_here:
            amount = wallet.balance * self.leak
            wallet.balance -= amount

    def get_wallet_by_owner(self, owner, create=True):
        wallet = db_session.query(Wallet).filter(Wallet.location==self, 
                                                 Wallet.owner==owner).one_or_none()
        if wallet is None and create:
            wallet = Wallet(owner)
            self.wallets_here.append(wallet)
            db_session.add(wallet)

        return wallet
    
    
    def do_propogate_funds(self):
        # Check activation
        if not self.active or not self.balance:
            return

        for edge in self.lower_edges:
            child = edge.higher_node
            amount = edge.weight

            # if the amount is greater than the balance, then
            # transfer what we can.
            if amount > self.balance:
                amount = self.balance

            total = self.balance
            for wallet in self.wallets_here:
                subamount = (wallet.balance / total) * amount
                if subamount > 0.0 and subamount <= wallet.balance:
                    wallet.transfer(child, subamount)

    @property
    def rank(self):
        if getattr(self, '__rank__', None) is not None:
            return self.__rank__
        rank = len(self.parents())
        for parent in self.parents():
            rank += parent.rank + 1

        self.__rank__ = rank
        return rank

class Goal(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Goal'
      }

    id = Column(String(36), ForeignKey(Node.id),
                primary_key=True, default=default_uuid)

class Policy(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Policy'
      }

    id = Column(String(36), ForeignKey(Node.id),
                primary_key=True, default=default_uuid)



class Player(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Player'
      }

    id = Column(String(36), ForeignKey(Node.id),
                primary_key=True, default=default_uuid)

    max_outflow = Column(Float)

    goal_id = Column(
        String(36),
        ForeignKey('goal.id')
        )

    goal = relationship(
        Goal,
        primaryjoin=goal_id == Goal.id,
        order_by='Goal.id',
        backref='players'
        )

    table_id = Column(
        String(36),
        ForeignKey('table.id')
        )

    table = relationship(
        Table,
        primaryjoin=table_id == Table.id,
        order_by='Table.id',
        backref='players'
        )

    token = Column(String(36),
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
#        res = db_session.execute("SELECT sum(balance) AS balance FROM wallet WHERE location_id = :id", {'id': self.id})
#        return res.fetchall()[0][0] or 0.0

        return self.wallet.balance

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


class Edge(Base):

    lower_id = Column(
        String(36),
        ForeignKey('node.id'),
        primary_key=True)

    higher_id = Column(
        String(36),
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
        String(36),
        ForeignKey('node.id'),
        index=True)

    owner = relationship(
        'Player',
        primaryjoin=owner_id == Node.id,
        backref='wallets_owned')

    location_id = Column(
        String(36),
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
