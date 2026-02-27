import requests
import traceback
import datetime
import time
from my_project import dbinfo
import json
from sqlalchemy import create_engine
import os
import simplejson as json


# Will be used to store text in a file
def write_to_file(text):
    # I first need to create a folder data where the files will be stored.

    if not os.path.exists('data'):
        os.mkdir('data')
        print("Folder 'data' created!")
    else:
        print("Folder 'data' already exists.")

    # now is a variable from datetime, which will go in {}.
    # replace is replacing white spaces with underscores in the file names
    now = datetime.datetime.now()
    with open("data/bikes_{}".format(now).replace(" ", "_"), "w") as f:
        f.write(text)


# Empty for now
# def write_to_db(text):
#     return 0


def stations_to_db(text, in_engine):
    # let us load the stations from the text received from jcdecaux
    stations = json.loads(text)

    # print type of the stations object, and number of stations
    print(type(stations), len(stations))

    # let us print the type of the object stations (a dictionary) and load the content
    for station in stations:
        print(type(station))

        # let us load only the parts that we have included in our db:

        # let us extract the relevant info from the dictionary
        vals = (station.get('number'), station.get('available_bike_stands'),
                station.get('available_bikes'), station.get('status'),station.get('last_update'))

        # now let us use the engine to insert into the stations
        in_engine.execute("""
                          INSERT INTO availability (number, available_bike_stands, available_bikes,
                                               status,last_update)
                          VALUES (%s,  %s, %s, %s, %s);
                          """, vals)


def main():
    USER = dbinfo.USER
    PASSWORD = dbinfo.PASSWORD
    PORT = dbinfo.PORT
    DB = dbinfo.DB
    URI = dbinfo.URI

    connection_string = "mysql+pymysql://{}:{}@{}:{}/{}".format(USER, PASSWORD, URI, PORT, DB)

    engine = create_engine(connection_string, echo=True)
    while True:
        try:
            r = requests.get(dbinfo.STATIONS_URI, params={"apiKey": dbinfo.JCKEY, "contract": dbinfo.NAME})
            stations_to_db(r.text, engine)
            write_to_file(r.text)
        except:
            print(traceback.format_exc())
        time.sleep(5 * 60)





# CTRL + Z or CTRL + C to stop it
main()

















