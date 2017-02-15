import os
from uuid import uuid1 as uuid

from MySQLdb import string_literal
from sqlalchemy import create_engine, event
from sqlalchemy.pool import Pool
from sqlalchemy import Column, String
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from flask_sqlalchemy import SQLAlchemy
from flask import Flask


#db = SQLAlchemy(session_options={"autoflush": True})
db = SQLAlchemy()

def default_uuid():
    return str(uuid())

def bytes_encoder(b, dummy=None):
    return b'_binary' + string_literal(b)

def str_encoder(s, dummy=None):
    return string_literal(str(s).encode('utf8'))

@event.listens_for(Pool, 'connect')
def set_encoders(dbapi_conn, conn_record):
    try:
        dbapi_conn.encoders[bytes] = bytes_encoder
        dbapi_conn.encoders[bytearray] = bytes_encoder
        dbapi_conn.encoders[str] = str_encoder
    except AttributeError:
        # sqlite doesn't allow this, and not needed so just pass silently
        pass
