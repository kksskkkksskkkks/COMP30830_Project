from flask import Blueprint, jsonify, render_template

from my_project.app.main import get_db, get_bike_data, get_weather, cache

db_bp = Blueprint('db', __name__)


#connect to db return json

#   @app.route  @db_bp.route

#   /db
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

# @db_bp.route('/')
# def root():
#     return 'Here is the index page!'






# get current data return json
live_bp = Blueprint('live', __name__)

#   @app.route    @live_bp.route
@live_bp.route("/")
def home():
    return render_template("index.html")

@live_bp.route("/api/bikes")
@cache.cached(timeout=60*5)
def bikes():
    return jsonify(get_bike_data())

@live_bp.route("/api/weather")
@cache.cached(timeout=60*10)
def weather():
    return jsonify(get_weather())

