from uuid import uuid4 as uuid
import enum

from sqlalchemy import Column, Integer, String, ForeignKey, \
    Float, create_engine
from sqlalchemy.orm import relationship, sessionmaker
from database import Base
from database import db_session


class Node(Base):
    __tablename__ = 'node'

    id = Column(String(36), primary_key=True)
    name = Column(String(100))
    leak = Column(Float)
    node_type = Column(String(10))

    __mapper_args__ = {
        'polymorphic_on': node_type,
        'polymorphic_identity': 'Node'
    }

    def __init__(self, name, leak):
        self.id = str(uuid())
        self.name = name
        self.leak = leak

    def higher_neighbors(self):
        return [x.higher_node for x in self.lower_edges]

    def lower_neighbors(self):
        return [x.lower_node for x in self.higher_edges]

    children = higher_neighbors

class Policy(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Policy'
   }


class Player(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Player'
   }

class Goal(Node):

    __mapper_args__ = {
      'polymorphic_identity': 'Goal'
   }

class Coin(Base):
    __tablename__ = 'coin'

    id = Column(String(36), primary_key=True)
    
    location_id = Column(
        String(36),
        ForeignKey('node.id'),
        unique=True)

    owner_id = Column(
        String(36),
        ForeignKey('node.id'),
        unique=True)

    location = relationship(
        Node,
        primaryjoin=location_id == Node.id,
        backref='coins')

    owner = relationship(
        Node,
        primaryjoin=owner_id == Node.id,
        backref='coins2')

    def __init__(self, name, leak):
        self.id = str(uuid())



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
        backref='lower_edges')

    higher_node = relationship(
        Node,
        primaryjoin=higher_id == Node.id,
        backref='higher_edges')

    weight = Column(Float())

    def __init__(self, n1, n2, weight):
        self.id = str(uuid())
        self.lower_node = n1
        self.higher_node = n2
        self.weight = weight

