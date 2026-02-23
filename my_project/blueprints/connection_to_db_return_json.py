from flask import Blueprint, g, render_template, jsonify
import json
from sqlalchemy import create_engine
from web_scraper.bike import dbinfo

# 1. Blueprint
db_bp = Blueprint('db', __name__)

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

# 2.  @app.route  @db_bp.route
@db_bp.route('/stations')
def get_stations():
    engine = get_db()
    stations = []
    rows = engine.execute("SELECT * from station;")
    for row in rows:
        stations.append(dict(row))
    return jsonify(stations=stations)

@db_bp.route('/available')
def get_available():
    engine = get_db()
    available = []
    rows = engine.execute("SELECT * from availability;")
    for row in rows:
        available.append(dict(row))
    return jsonify(available=available)

# @db_bp.route('/weather')
# def get_weather():
#     engine = get_db()
#     weather = []
#     rows = engine.execute("SELECT * from weather_dublin;")
#     for row in rows:
#         weather.append(dict(row))
#     return jsonify(weather=weather)


@db_bp.route('/weather/current')
def get_weather_current():
    engine = get_db()
    weather_current = []
    rows = engine.execute("SELECT * from current;")
    for row in rows:
        weather_current.append(dict(row))
    return jsonify(weather_current=weather_current)

@db_bp.route('/weather/daily')
def get_weather_daily():
    engine = get_db()
    weather_daily = []
    rows = engine.execute("SELECT * from daily;")
    for row in rows:
        weather_daily.append(dict(row))
    return jsonify(weather_daily=weather_daily)

@db_bp.route('/weather/hourly')
def get_weather_hourly():
    engine = get_db()
    weather_hourly = []
    rows = engine.execute("SELECT * from hourly;")
    for row in rows:
        weather_hourly.append(dict(row))
    return jsonify(weather_hourly=weather_hourly)




@db_bp.route("/available/<int:station_id>")
def get_specific_station(station_id):
    engine = get_db()
    data = []
    rows = engine.execute("SELECT available_bikes from availability where number = {};".format(station_id))
    for row in rows:
        data.append(dict(row))
    return jsonify(available=data)

@db_bp.route('/')
def root():
    return 'Navigate to /db/stations or /db/available'

# 3.  if __name__ == '__main__': app.run(debug=True)