import os
from uuid import uuid1 as uuid

from sqlalchemy import create_engine
from sqlalchemy import Column, String
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from flask_sqlalchemy import SQLAlchemy
from flask import Flask


db = SQLAlchemy()

def default_uuid():
    return str(uuid())

def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    import models
    models.Base.metadata.create_all(bind=db.engine)

def clear_db():
    import models
    db.session.rollback()
    models.Base.metadata.drop_all(bind=db.engine)
