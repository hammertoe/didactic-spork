from flaskext.zodb import ZODB
from flaskext.zodb import BTree

from flask import g

def get_db():
    if '_zodb' not in g:
        g._zodb = ZODB()
    return g._zodb

def Xreset_database(db):
    db['players'] = BTree()
    db['policies'] = BTree()
    db['goals'] = BTree()

