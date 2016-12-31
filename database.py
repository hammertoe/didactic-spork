import os
from uuid import uuid1 as uuid

from sqlalchemy import create_engine
from sqlalchemy import Column, String
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base, declared_attr

engine = create_engine(os.environ['SQLALCHEMY_DATABASE_URI'], convert_unicode=True, echo=False)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=True,
                                         bind=engine))

def default_uuid():
    return str(uuid())


def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    import models
    models.Base.metadata.create_all(bind=engine)

def clear_db():
    import models
    db_session.rollback()
    models.Base.metadata.drop_all(bind=engine)

