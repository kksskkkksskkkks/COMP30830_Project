from flask import Blueprint, render_template, jsonify
import requests
from my_project import dbinfo
from flask_caching import Cache

from flask import Blueprint, g, jsonify
from sqlalchemy import create_engine
from my_project import dbinfo


#connect to db return json

USER = dbinfo.USER
PASSWORD = dbinfo.PASSWORD
PORT = dbinfo.PORT
DB = dbinfo.DB
URI = dbinfo.URI

def connect_to_db():
    connection_string = "mysql+pymysql://{}:{}@{}:{}/{}".format(USER, PASSWORD, URI, PORT, DB)
    engine = create_engine(connection_string, echo = True)
    return engine

def get_db():
    db_engine = getattr(g, '_database', None)
    if db_engine is None:
        db_engine = g._database = connect_to_db()
    return db_engine



#get current data return json

cache = Cache()


JCDECAUX_API_KEY = dbinfo.JCKEY
OPENWEATHER_API_KEY = dbinfo.WEATHER_KEY
CITY_NAME = dbinfo.CITY_NAME
CONTRACT_NAME = dbinfo.NAME

def get_bike_data():
    url = f"https://api.jcdecaux.com/vls/v1/stations?contract={CONTRACT_NAME}&apiKey={JCDECAUX_API_KEY}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else []

def get_weather():
    url = f"https://api.openweathermap.org/data/2.5/weather?q={CITY_NAME}&appid={OPENWEATHER_API_KEY}&units=metric"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else {}



from.import routes
