from uuid import uuid1 as uuid
import enum

from sqlalchemy import Column, Integer, String, ForeignKey, \
    Float, create_engine
from sqlalchemy.orm import relationship, sessionmaker
from database import Base
from database import db_session

from utils import random

class Node(Base):
    __tablename__ = 'node'

    id = Column(String(36), primary_key=True)
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
        self.id = str(uuid())
        self.name = name
        self.leak = leak
        self.activation = 0.0

    def higher_neighbors(self):
        return [x.higher_node for x in self.lower_edges]

    def lower_neighbors(self):
        return [x.lower_node for x in self.higher_edges]

    children = higher_neighbors
    parents = lower_neighbors

    def balance(self):
        return len(self.coins)

    def do_leak(self, commit=True):
        if random.random() <= self.leak and self.balance() > 0:
            coin = random.choice(self.coins)
            db_session.delete(coin)
            if commit:
                db_session.commit()
            return True
        return False
    
    def do_transfer(self, commit=True, recurse=False):
        # Check activation
        total = 0
        for edge in self.higher_edges:
            total += edge.weight
        if total < self.activation:
            return

        for edge in self.lower_edges:
            child = edge.higher_node
            w = edge.weight
            while w > 0:
                if random.random() <= w and self.balance() > 0:
                    coin = random.choice(self.coins)
                    coin.location = child
                w -= 1

                if recurse:
                    child.do_transfer(commit, recurse)

        if commit:
            db_session.commit()

    coins = relationship(
        'Coin',
        back_populates='location',
        foreign_keys='Coin.location_id',
        )

class Policy(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Policy'
      }


class Goal(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Goal'
      }


class Player(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Player'
    }    

    coins = relationship(
        'Coin',
        back_populates='owner',
        foreign_keys='Coin.owner_id',
        )

    def __init__(self, name):
        self.id = str(uuid())
        self.name = name
        self.leak = 0.0
        

class Edge(Base):
    __tablename__ = 'edge'

    id = Column(String(36), primary_key=True)

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
        self.id = str(uuid())
        self.lower_node = n1
        self.higher_node = n2
        self.weight = weight


class Coin(Base):
    __tablename__ = 'coin'

    id = Column(String(36), primary_key=True)
    
    location_id = Column(
        String(36),
        ForeignKey('node.id'),
        index=True)

    owner_id = Column(
        String(36),
        ForeignKey('node.id'),
        index=True)

    location = relationship(
        'Node',
        primaryjoin='Node.id == Coin.location_id',
        back_populates='coins')

    owner = relationship(
        'Player',
        primaryjoin='Player.id == Coin.owner_id',
        back_populates='coins')

    def __init__(self, owner):
        self.id = str(uuid())
        self.owner = owner



