import enum

from sqlalchemy import Column, Integer, String, ForeignKey, \
    Float, create_engine
from sqlalchemy.orm import relationship, sessionmaker, backref
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.associationproxy import association_proxy
from database import Base
from database import db_session
from database import default_uuid

from utils import random




    
class WalletAssociation(Base):
    """Associates a collection of wallets to a particular parent"""

    __tablename__ = "wallet_association"

    @classmethod
    def creator(cls, discriminator):
        """Provide a 'creator' function to use with 
        the association proxy."""

        return lambda wallets: WalletAssociation(
                               wallets=wallets,
                               discriminator=discriminator)

    discriminator = Column(String)
    """Refers to the type of parent."""

    @property
    def location(self):
        """Return the parent object."""
        return getattr(self, "%s_parent" % self.discriminator)


class Wallet(Base):

    association_id = Column(Integer, 
                            ForeignKey("wallet_association.id")
                            )
    
    owner_id = Column(
        String(36),
        ForeignKey('player.id'),
        index=True)

    owner = relationship(
        'Player',
        primaryjoin='Player.id == Wallet.owner_id',
        back_populates='wallets')

    balance = Column(Float)

    association = relationship(
        "WalletAssociation", 
        backref="wallets")

    location = association_proxy("association", "location")

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
            

class HasWallets(object):
    """HasWallets mixin, creates a relationship to
    the wallet_association table for each parent.
    
    """
    @declared_attr
    def wallet_association_id(cls):
        return Column(Integer, 
                      ForeignKey("wallet_association.id"))

    @declared_attr
    def wallet_association(cls):
        discriminator = cls.__name__.lower()
        cls.wallets = association_proxy(
            "wallet_association", "wallets",
            creator=WalletAssociation.creator(discriminator)
            )
        return relationship("WalletAssociation", 
                            uselist=True,
                            backref=backref("%s_parent" % discriminator, 
                                            uselist=False))


class Node(HasWallets, Base):

    __tablename__ = 'node'

    name = Column(String(100))
    leak = Column(Float)
    node_type = Column(String(10))
    activation = Column(Float)
    max_level = Column(Integer)

    __mapper_args__ = {
        'polymorphic_on': node_type,
        'polymorphic_identity': 'Node'
    }

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

    def do_leak(self, commit=True):
        total = self.balance
        for wallet in self.wallets:
            amount = wallet.balance * self.leak
            wallet.balance -= amount

        if commit:
            db_session.commit()

    def get_wallet_by_owner(self, owner, create=True):
        wallet = db_session.query(Wallet).filter_by(location=self,
                                                    owner=owner).first()        
        if wallet is None and create:
            wallet = Wallet(owner)
#            wallet.location_id = self.id
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


class Goal(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Goal'
      }


class Player(Base):

    name = Column(String(100))
    leak = Column(Float)

    wallets = relationship(
        'Wallet',
        back_populates='owner',
        foreign_keys='Wallet.owner_id',
        )

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
    __tablename__ = 'fund'

    id = Column(String(36), primary_key=True)

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
