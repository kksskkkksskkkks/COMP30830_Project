from config import Config
from flask import Flask, g
from sqlalchemy import create_engine
import os



def connect_to_db():
    connection_string = "mysql+pymysql://{}:{}@{}:{}/{}".format(Config.DB_USER, Config.DB_PASSWORD, Config.DB_URI, Config.DB_PORT, Config.DB_NAME)
    engine = create_engine(connection_string, echo = True)

    return engine

# Create the engine variable and store it in the global Flask variable 'g'
def get_db():
    db_engine = getattr(g, '_database', None)
    if db_engine is None:
        db_engine = g._database = connect_to_db()
    return db_engine

