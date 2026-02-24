from flask import Blueprint, render_template, jsonify
import requests
from web_scraper.bike import dbinfo
from flask_caching import Cache


live_bp = Blueprint('live', __name__)


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
