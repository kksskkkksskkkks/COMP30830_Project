"""
This file includes business logic related functions (e.g. bike, weather, google map)
"""
from config import Config
from flask import Blueprint, g, jsonify, render_template, session, redirect, url_for, request
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


@main_bp.route("/")
def home():
    return render_template("index.html", MAP_KEY=Config.MAP_KEY, MAP_ID=Config.MAP_ID)

@main_bp.route("/safety")
def safety():
    return render_template("safety.html")

@main_bp.route("/faq")
def faq():
    return render_template("faq.html")

@main_bp.route("/account")
def account():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    from sqlalchemy import text as sql_text
    engine = get_db()
    uid = session['user_id']
    with engine.connect() as conn:
        user = dict(conn.execute(
            sql_text("SELECT user_id, full_name, preferred_language, created_at FROM users WHERE user_id = :uid"),
            {"uid": uid}
        ).fetchone()._mapping)
        rows = conn.execute(
            sql_text("""
                SELECT f.station_number, s.name AS station_name, f.added_at
                FROM user_favorites f
                JOIN station s ON s.number = f.station_number
                WHERE f.user_id = :uid
                ORDER BY f.added_at DESC
            """),
            {"uid": uid}
        ).fetchall()
        favorites = [dict(r._mapping) for r in rows]
    return render_template('account.html', user=user, favorites=favorites)


@main_bp.route("/api/geocode")
def geocode():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    try:
        resp = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": q, "limit": 5, "bbox": "-6.32,53.32,-6.14,53.40"},  # (lng_min,lat_min,lng_max,lat_max) Limit search result to Dublin only
            headers={"User-Agent": "DublinBikesApp/1.0"},
            timeout=5,
        )
        results = []
        for f in resp.json().get("features", []):
            props  = f.get("properties", {})
            coords = f["geometry"]["coordinates"]   # [lng, lat]
            parts  = [props.get("name"), props.get("street"), props.get("district") or props.get("suburb")]
            name   = ", ".join(p for p in parts if p)
            if not name:
                continue
            results.append({"name": name, "lat": coords[1], "lng": coords[0]})
        return jsonify(results)
    except Exception:
        return jsonify([])


@main_bp.route("/bike/plot")
def bike_plot():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    return render_template("bike_plot.html")

@main_bp.route("/bike/number")
def bike_return():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    return render_template("bike_return_number.html")


# 1. Bike
# ✅ 1.1. Scrape/fetch bike info from API
# ====== TODO: Request periodically without user's action? ======
def get_bike_data():
    response = requests.get("https://api.jcdecaux.com/vls/v1/stations", params={"apiKey": Config.BIKE_KEY, "contract": "dublin"})
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
    response = requests.get("https://api.openweathermap.org/data/2.5/weather", params={"appid": Config.WEATHER_KEY, "q": "dublin, ie"})
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
