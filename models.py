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
    
    
    def do_transfer(self, commit=True, recurse=False):
        # Check activation
        # no activation for now

        for edge in self.lower_edges:
            child = edge.higher_node
            amount = edge.weight

            total = self.balance
            for wallet in self.wallets:
                foo = (wallet.balance / total) * amount
                wallet.transfer(child, foo)

            if recurse:
                child.do_transfer(commit, recurse)

        if commit:
            db_session.commit()

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

    @property
    def wallet(self):
        return self.get_wallet_by_owner(self)

    @property
    def balance(self):
        return self.wallet.balance

    @balance.setter
    def balance(self, amount):
        self.wallet.balance = amount

    def fund(self, node, amount):
        self.wallet.transfer(node, amount)

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
        self.id = str(uuid())
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
