"""
This file includes business logic related functions (e.g. bike, weather, google map)
"""

from flask import Blueprint, g, jsonify, render_template

import os
import requests
from datetime import datetime, timezone
from flask_caching import Cache
from app.connection import get_db

main_bp = Blueprint(
    "main",
    __name__,
    template_folder="templates",
    static_folder="static"
)

cache = Cache()


JCDECAUX_API_KEY = os.getenv("JCKEY")
OPENWEATHER_API_KEY = os.getenv("OWKEY")


@main_bp.route("/")
def home():
    return render_template("index.html")


# 1. Bike
# ✅ 1.1. Scrape/fetch bike info from API
# ====== TODO: Request periodically without user's action? ======
def get_bike_data():
    response = requests.get("https://api.jcdecaux.com/vls/v1/stations", params={"apiKey": JCDECAUX_API_KEY, "contract": "dublin"})
    return response.json() if response.status_code == 200 else []


# 1.2. Store bike info to DB availability table
def stations_to_db(station_json: dict, in_engine):
    for station in station_json:
        # Extract relevant info from the dictionary
        vals = (station.get('number'), station.get('available_bike_stands'),
                station.get('available_bikes'), station.get('status'),station.get('last_update'))

        # Use the engine to insert into DB stations table
        in_engine.execute("""
                          INSERT INTO availability (number, available_bike_stands, available_bikes,
                                               status,last_update)
                          VALUES (%s,  %s, %s, %s, %s);
                          """, vals)


# 1.3. Retrive from DB STATION table
@main_bp.route('/db/stations')
def get_stations():
    engine = get_db()
    stations = []
    rows = engine.execute("SELECT * from station;")
    for row in rows:
        stations.append(dict(row))
    return jsonify(stations=stations)


# 1.4. Retrive from DB AVAILABILITY table
@main_bp.route('/db/available')
def get_available():
    engine = get_db()
    available = []
    rows = engine.execute("SELECT * from availability;")
    for row in rows:
        available.append(dict(row))
    return jsonify(available=available)


# 1.3 get all availability from cache
@main_bp.route("/api/bikes")
@cache.cached(timeout=60*5)
def get_all_stations_current(): # Originally called "bikes()"
    return jsonify(get_bike_data())


# 1.4 get specific station availiability from DB
@main_bp.route('/db/available/<int:station_id>')
def get_specific_station(station_id):
    engine = get_db()
    data = []
    rows = engine.execute("SELECT available_bikes from availability where number = {};".format(station_id))
    for row in rows:
        data.append(dict(row))
    return jsonify(available=data)


# 2. Weather
# ✅ 2.1 Scrape/fetch from API
# ====== TODO: Request periodically without user's action? ======
def get_weather():
    response = requests.get("https://api.openweathermap.org/data/2.5/weather", params={"appid": OPENWEATHER_API_KEY, "q": "dublin, ie"})
    return response.json() if response.status_code == 200 else {}


# 2.2. Store weather info to DB current table
def current_weather_to_db(weather_json: dict, in_engine):
    dt = datetime.fromtimestamp(weather_json["dt"], tz=timezone.utc)
    feels_like = weather_json.get('main', {}).get('feels_like') # dict
    humidity = weather_json.get('main', {}).get('humidity')   # dict
    pressure = weather_json.get('main', {}).get('pressure')   # dict
    sunrise = datetime.fromtimestamp(weather_json["sys"]["sunrise"], tz=timezone.utc)
    sunset = datetime.fromtimestamp(weather_json["sys"]["sunset"], tz=timezone.utc)
    temp = weather_json.get('main', {}).get('temp')
    weather_id = weather_json.get('weather')[0].get('id')
    wind_gust = weather_json.get('wind', {}).get('gust')
    wind_speed = weather_json.get('wind', {}).get('speed')
    rain_1h = weather_json.get('rain', {}).get('1h')
    snow_1h = weather_json.get('snow', {}).get('1h')

    sql = """
        INSERT INTO `current`
        (dt, feels_like, humidity, pressure, sunrise, sunset, `temp`,
        weather_id, wind_gust, wind_speed, rain_1h, snow_1h)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

    vals = (
        dt, feels_like, humidity, pressure, sunrise, sunset, temp,
        weather_id, wind_gust, wind_speed, rain_1h, snow_1h
    )

    with in_engine.begin() as conn:
        conn.exec_driver_sql(sql, vals)



# ✅ 2.3. Get weather FROM DB CURRENT table
@main_bp.route('/db/weather/current')
def get_weather_current():
    engine = get_db()
    weather_current = []
    rows = engine.execute("SELECT * from current;")
    for row in rows:
        weather_current.append(dict(row))
    return jsonify(weather_current=weather_current)


# ✅ 2.3. get weather current FROM API/chace
@main_bp.route("/api/weather")
@cache.cached(timeout=60*10)
def weather():
    return jsonify(get_weather())


"""
========= NOT CURRNETLY IN USE =========
# 2.3 get_weather_daily() ALWAYS FROM DB
@db_bp.route('/weather/daily')
def get_weather_daily():
    engine = get_db()
    weather_daily = []
    rows = engine.execute("SELECT * from daily;")
    for row in rows:
        weather_daily.append(dict(row))
    return jsonify(weather_daily=weather_daily)

# 2.4 get_weather_hourly() ALWAYS FROM DB
@db_bp.route('/weather/hourly')
def get_weather_hourly():
    engine = get_db()
    weather_hourly = []
    rows = engine.execute("SELECT * from hourly;")
    for row in rows:
        weather_hourly.append(dict(row))
    return jsonify(weather_hourly=weather_hourly)
"""

# 3. Map
