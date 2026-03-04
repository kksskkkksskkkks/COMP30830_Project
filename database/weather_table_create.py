import sqlalchemy as sqla
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASSWORD")
PORT = os.getenv("DB_PORT")
DB = os.getenv("DB_NAME")
URI = os.getenv("DB_URI")

connection_string = "mysql+pymysql://{}:{}@{}:{}/{}".format(USER, PASSWORD, URI, PORT, DB)

engine = create_engine(connection_string, echo = True)

with engine.begin() as conn:
    for res in conn.execute(sqla.text("SHOW VARIABLES;")):
        print(res)

    # Table current
    sql = '''
    CREATE TABLE IF NOT EXISTS current (
        dt DATETIME NOT NULL,
        feels_like FLOAT,
        humidity INTEGER,
        pressure INTEGER,
        sunrise DATETIME,
        sunset DATETIME,
        temp FLOAT,
        uvi FLOAT,
        weather_id INTEGER,
        wind_gust FLOAT,
        wind_speed FLOAT,
        rain_1h FLOAT,
        snow_1h FLOAT,
        PRIMARY KEY (dt)
    );
    '''

    # Execute the query
    conn.execute(sqla.text(sql))

    # Use the engine to execute the DESCRIBE command to inspect the table schema
    tab_structure = conn.execute(sqla.text("SHOW COLUMNS FROM current;"))

    # Fetch and print the result to see the columns of the table
    columns = tab_structure.fetchall()
    print(columns)

    # Table daily
    sql = '''
    CREATE TABLE IF NOT EXISTS daily (
        dt DATETIME NOT NULL,
        future_dt DATETIME NOT NULL,
        humidity INTEGER,
        pop FLOAT,
        pressure INTEGER,
        temp_max FLOAT,
        temp_min FLOAT,
        uvi FLOAT,
        weather_id INTEGER,
        wind_speed FLOAT,
        wind_gust FLOAT,
        rain FLOAT,
        snow FLOAT,
        PRIMARY KEY (dt, future_dt)
    );
    '''

    conn.execute(sqla.text(sql))
    tab_structure = conn.execute(sqla.text("SHOW COLUMNS FROM daily;"))

    # Fetch and print the result to see the columns of the table
    columns = tab_structure.fetchall()
    print(columns)

    # Table hourly
    sql = '''
    CREATE TABLE IF NOT EXISTS hourly (
        dt DATETIME NOT NULL,
        future_dt DATETIME NOT NULL,
        feels_like FLOAT,
        humidity INTEGER,
        pop FLOAT,
        pressure INTEGER,
        temp FLOAT,
        uvi FLOAT,
        weather_id INTEGER,
        wind_speed FLOAT,
        wind_gust FLOAT,
        rain_1h FLOAT,
        snow_1h FLOAT,
        PRIMARY KEY (dt, future_dt)
    );
    '''

    conn.execute(sqla.text(sql))
    tab_structure = conn.execute(sqla.text("SHOW COLUMNS FROM hourly;"))

    # Fetch and print the result to see the columns of the table
    columns = tab_structure.fetchall()
    print(columns)