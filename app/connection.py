from flask import Flask, g
from sqlalchemy import create_engine
import os


USER = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASSWORD")
PORT = os.getenv("DB_PORT")
DB = os.getenv("DB_NAME")
URI = os.getenv("DB_URI")

def connect_to_db():
    connection_string = "mysql+pymysql://{}:{}@{}:{}/{}".format(USER, PASSWORD, URI, PORT, DB)
    engine = create_engine(connection_string, echo = True)

    return engine

# Create the engine variable and store it in the global Flask variable 'g'
def get_db():
    db_engine = getattr(g, '_database', None)
    if db_engine is None:
        db_engine = g._database = connect_to_db()
    return db_engine

