import sqlalchemy.types as types
from gameserver.wallet import Wallet as BaseWallet
from sqlalchemy.ext.mutable import Mutable
from uuid import uuid4, UUID
import unittest
from gameserver.database import default_uuid

from sqlalchemy import Table, Column, Integer, MetaData, create_engine, CHAR
from sqlalchemy.ext.declarative import declared_attr, as_declarative
from sqlalchemy.orm import sessionmaker

class WalletType(types.TypeDecorator):

    impl = types.BLOB

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = value.dumps()

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            w = Wallet()
            w.loads(value)
            return w
        return value

    def compare_values(self, x, y):
        return x == y

class Wallet(Mutable, BaseWallet):

    @classmethod
    def coerce(cls, key, value):
        if not isinstance(value, cls):
            return cls(value)
        else:
            return value

    def __init__(self, items=None):
        return BaseWallet.__init__(self, items)
    
    def add(self, player_id, amount):
        ret = BaseWallet.add(self, player_id, amount)
        self.changed()
        return ret

    def transfer(self, amount, dest):
        ret = BaseWallet.transfer(self, amount, dest)
        self.changed()
        dest.changed()
        return ret

    
class SQLAWalletTests(unittest.TestCase):

    def testSQLWalletType(self):

        engine = create_engine('sqlite:///:memory:', echo=False)
        meta = MetaData()
        players = Table('players', meta,
                        Column('id', Integer, primary_key=True),
                        Column('wallet', WalletType),
                        )

        meta.create_all(engine)

        player1_id = uuid4()
        player2_id = uuid4()
        w = Wallet()
        w.add(player1_id, 23.6)
        w.add(player2_id, 10.9)

        conn = engine.connect()
        ins = players.insert().values(wallet=w)
        conn.execute(ins)

        sel = players.select()

        result = conn.execute(sel)
        row = result.fetchone()

        w = row[1]

        expected = {str(player1_id): 23.6,
                    str(player2_id): 10.9,
                    }

        for k,v in w.todict().items():
            self.assertAlmostEqual(v, expected[k], 5)

    def testORMWalletTransfer(self):

        engine = create_engine('sqlite:///:memory:', echo=False)
        Session = sessionmaker(bind=engine)
        session = Session()

        @as_declarative()
        class Base(object):
            @declared_attr
            def __tablename__(cls):
                return cls.__name__.lower()
            id = Column(CHAR(36), primary_key=True, default=default_uuid)

        class Node(Base):
            wallet = Column(Wallet.as_mutable(WalletType))

            def __init__(self):
                self.wallet = Wallet()

        Base.metadata.create_all(engine)

        n1 = Node()
        n2 = Node()

        session.add(n1)
        session.add(n2)

        session.flush()

        self.assertEqual(len(n1.wallet), 0)
        self.assertEqual(n1.wallet.total, 0.0)

        u1 = default_uuid()
        u2 = default_uuid()
        n1.wallet.add(u1, 30.5)

        self.assertEqual(len(session.dirty), 1)

        session.flush()

        self.assertEqual(n1.wallet.total, 30.5)

        session.expire(n1)

        self.assertEqual(n1.wallet.total, 30.5)
        self.assertEqual(n1.wallet[0], (UUID(u1).bytes, 30.5))

        # test transfer
        n1.wallet.transfer(20.0, n2.wallet)
        self.assertEqual(n1.wallet.total, 10.5)
        self.assertEqual(n2.wallet.total, 20.0)
        
        session.flush()
        session.expire(n1)
        session.expire(n2)

        self.assertEqual(n1.wallet.total, 10.5)
        self.assertEqual(n2.wallet.total, 20.0)

        n1.wallet = Wallet()
        self.assertEqual(n1.wallet.total, 0)



if __name__ == '__main__':
    unittest.main()

