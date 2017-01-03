import enum

from sqlalchemy import Column, Integer, String, ForeignKey, \
    Float, create_engine
from sqlalchemy.orm import relationship, sessionmaker, backref
from sqlalchemy.ext.declarative import declared_attr, as_declarative
from sqlalchemy.ext.associationproxy import association_proxy
from database import db_session
from database import default_uuid

from utils import random


@as_declarative()
class Base(object):
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()
    id = Column(String(36), primary_key=True, default=default_uuid)

class WalletInterface(Base):
    discriminator = Column(String)

    __mapper_args__ = {"polymorphic_on": discriminator}



class Wallet(Base):

    owner_id = Column(
        String(36),
        ForeignKey('player.id'),
        index=True)

    owner = relationship(
        'Player',
        backref='wallets')

    location_id = Column(
        String(36),
        ForeignKey('node.id'),
        index=True)

    location = relationship(
        'Node',
        backref='wallets')

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
            


class Node(Base):

    discriminator = Column(String)
    __mapper_args__ = {"polymorphic_on": discriminator}
    id = Column(String(36), ForeignKey(WalletInterface.id), 
                primary_key=True, default=default_uuid)

    name = Column(String(100))
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
        return sum([x.rate for x in self.lower_edges])

    @property
    def current_inflow(self):
        # the amount coming in from players
        from_players = sum([x.rate for x in self.funded_by])
        # plus the amount coming in from other nodes
        from_nodes = sum([x.current_flow for x in self.higher_edges])

        return from_nodes + from_players

    @property
    def active(self):
        return self.current_inflow >= self.activation

    @property
    def balance(self):
        return float(sum([ wallet.balance for wallet in self.wallets ]))

    def do_leak(self):
        total = self.balance
        for wallet in self.wallets:
            amount = wallet.balance * self.leak
            wallet.balance -= amount

    def get_wallet_by_owner(self, owner, create=True):
        wallet = db_session.query(Wallet).filter(Wallet.location==self, 
                                                 Wallet.owner==owner).first()
        if wallet is None and create:
            wallet = Wallet(owner)
            self.wallets.append(wallet)
            db_session.add(wallet)

        return wallet
    
    
    def do_propogate_funds(self, recurse=False):
        # Check activation
        if not self.active:
            return

        for edge in self.lower_edges:
            child = edge.higher_node
            amount = edge.weight

            total = self.balance
            for wallet in self.wallets:
                foo = (wallet.balance / total) * amount
                if foo > 0.0 and foo <= wallet.balance:
                    wallet.transfer(child, foo)

            if recurse:
                child.do_propogate_funds(commit, recurse)


class Policy(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Policy'
      }

    id = Column(String(36), ForeignKey(Node.id), 
                primary_key=True, default=default_uuid)


class Goal(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Goal'
      }

    id = Column(String(36), ForeignKey(Node.id),
                primary_key=True, default=default_uuid)


class Player(Base):

    name = Column(String(100))
    leak = Column(Float)


    def __init__(self, name):
        self.id = default_uuid()
        self.name = name
        self.leak = 0.0
        self.max_outflow = 0.0

        # create a wallet for the player
        w = Wallet(self, 0.0)
        db_session.add(w)
        w.location_id = self.id

    @property
    def wallet(self):
        return db_session.query(Wallet).filter(Wallet.location_id == self.id).one()

    @property
    def balance(self):
        return self.wallet.balance

    @balance.setter
    def balance(self, amount):
        self.wallet.balance = amount

    def transfer_funds_to_node(self, node, amount):
        self.wallet.transfer(node, amount)

    def fund(self, node, rate):
        # Do we already fund this node? If so change value
        f = db_session.query(Fund).filter(Fund.node == node,
                                          Fund.player == self).one_or_none()
        # check we are not exceeding our max fund outflow rate
        tmp_rate = self.current_outflow
        if f is not None:
            tmp_rate -= f.rate
        tmp_rate += rate
        if tmp_rate > self.max_outflow:
            raise ValueError, "Exceeded max outflow rate"

        if f is not None:
            f.rate = rate
            if rate == 0.0:
                # if we set funding level to 0 then delete fund link
                db_session.delete(f)
        else: # create new fund link
            f = Fund(self, node, rate)
            db_session.add(f)

    @property
    def current_outflow(self):
        funds = db_session.query(Fund).filter(Fund.player == self).all()
        return sum([fund.rate for fund in funds])

    def transfer_funds(self):
        for fund in self.funds:
            self.transfer_funds_to_node(fund.node, fund.rate)


class Fund(Base):

    player_id = Column(
        String(36),
        ForeignKey('player.id'),
        primary_key=True)

    node_id = Column(
        String(36),
        ForeignKey('node.id'),
        primary_key=True)

    player = relationship(
        Player,
        order_by='Player.id',
        backref='funds')

    node = relationship(
        Node,
        order_by='Node.id',
        backref='funded_by')

    rate = Column(Float())

    def __init__(self, player, node, rate):
        self.id = default_uuid()
        self.player = player
        self.node = node
        self.rate = rate
        

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
        if self.lower_node.active \
                and self.weight <= self.lower_node.balance:
            return self.weight
        return 0.0
