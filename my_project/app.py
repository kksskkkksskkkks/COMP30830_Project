import dbinfo_jcd
import dbinfo_weather
import requests
import json
from flask import Flask, jsonify

# Helper functions
def get_station_by_id(number):
    """Returns json format for a station inputting an ID as parameter
    
    Requires jsonify function"""
    JCKEY = dbinfo_jcd.JCKEY
    NAME = dbinfo_jcd.NAME
    STATIONS_URI = dbinfo_jcd.STATIONS_URI
    # Max = 117, missing 34, 46, 81
    NUMBER = str(number)
    STATION_NUMBER = str(NUMBER)

    r = requests.get(STATIONS_URI+STATION_NUMBER, params={"contract": NAME, "apiKey": JCKEY})
    data = json.loads(r.text)
    return data


def get_current_weather_information():
    """Returns json format for current (only) weather in Dublin
    
    Requires jsonify function"""
    WEATHERKEY = dbinfo_weather.WEATHERKEY
    UNITS = dbinfo_weather.UNITS
    WEATHERAPI = dbinfo_weather.WEATHERAPI
    EXCLUDE = dbinfo_weather.EXCLUDE
    LAT = 53.3498
    LON = -6.2603

    r = requests.get(WEATHERAPI, params={"lat":LAT, "lon":LON, "appid": WEATHERKEY, "units": UNITS, "exclude": EXCLUDE})
    data = json.loads(r.text)
    return data



app = Flask(__name__, static_url_path='')


@app.route('/api/station/<int:station_id>')
def station_by_id(station_id):
    return jsonify(get_station_by_id(station_id))

@app.route("/api/weather")
def current_weather():
    return jsonify(get_current_weather_information())

if __name__ == "__main__":
    app.run(debug=True) 