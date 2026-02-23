import dbinfo
import requests
import json
import sqlalchemy as sqla
from sqlalchemy import create_engine
import traceback
import glob
import os
from pprint import pprint
import simplejson as json
import time
from IPython.display import display


USER = dbinfo.USER
PASSWORD = dbinfo.PASSWORD
PORT = dbinfo.PORT
DB = dbinfo.DB
URI = dbinfo.URI

connection_string = "mysql+pymysql://{}:{}@{}:{}/{}".format(USER, PASSWORD, URI, PORT, DB)

engine = create_engine(connection_string, echo = True)

for res in engine.execute("SHOW VARIABLES;"):
    print(res)

# Create a station table

sql = '''
CREATE TABLE IF NOT EXISTS station (
`number` Integer not null,
contract_name VARCHAR(128),
`name` VARCHAR(128),
address VARCHAR(128),
bike_stands integer,
lat FLOAT,
lng FLOAT,
banking boolean,
bonus boolean
    );
'''

# Execute the query
res = engine.execute(sql)

# Use the engine to execute the DESCRIBE command to inspect the table schema
tab_structure = engine.execute("SHOW COLUMNS FROM station;")

# Fetch and print the result to see the columns of the table
columns = tab_structure.fetchall()
print(columns)

# CREATE AVAILABILITY TABLE
sql = """
CREATE TABLE IF NOT EXISTS availability (
`number` integer not null,
available_bike_stands integer,
available_bikes integer,
status varchar(128),
last_update bigint not null
);
"""

engine.execute(sql)