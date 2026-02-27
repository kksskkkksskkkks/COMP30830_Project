import requests
import traceback
from datetime import datetime, timezone
import time
import os
import sqlalchemy as sqla
from sqlalchemy import create_engine
# import dbinfo
import json
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASSWORD")
PORT = os.getenv("DB_PORT")
DB = os.getenv("DB_NAME")
URI = os.getenv("DB_URI")
KEY = os.getenv("OWKEY")
CURRENT_URI = os.getenv("CURRENT_URI")

def current_weather_to_db(text, in_engine):
    
    current = json.loads(text)
    
    dt = datetime.fromtimestamp(current["dt"], tz=timezone.utc)
    feels_like = current.get('main', {}).get('feels_like') # dict
    humidity = current.get('main', {}).get('humidity')   # dict
    pressure = current.get('main', {}).get('pressure')   # dict
    sunrise = datetime.fromtimestamp(current["sys"]["sunrise"], tz=timezone.utc)
    sunset = datetime.fromtimestamp(current["sys"]["sunset"], tz=timezone.utc)
    temp = current.get('main', {}).get('temp')
    weather_id = current.get('weather')[0].get('id')
    wind_gust = current.get('wind', {}).get('gust')
    wind_speed = current.get('wind', {}).get('speed')
    rain_1h = current.get('rain', {}).get('1h')
    snow_1h = current.get('snow', {}).get('1h')

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


def main():
    connection_string = "mysql+pymysql://{}:{}@{}:{}/{}".format(USER, PASSWORD, URI, PORT, DB)

    engine = create_engine(connection_string, echo = True)

    try:
        r = requests.get(CURRENT_URI, params={"appid": KEY, "q": "dublin, ie"})
        current_weather_to_db(r.text, engine)
        time.sleep(5*60)
    except:
        print(traceback.format_exc())


main()