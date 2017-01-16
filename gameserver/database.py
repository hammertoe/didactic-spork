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



