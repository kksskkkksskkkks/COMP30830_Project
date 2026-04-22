import os
import requests
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

USER = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASSWORD")
PORT = os.getenv("DB_PORT")
DB = os.getenv("DB_NAME")
URI = os.getenv("DB_URI")
BIKE_KEY = os.getenv("BIKE_KEY")

# Create database connection
connection_string = f"mysql+pymysql://{USER}:{PASSWORD}@{URI}:{PORT}/{DB}"
engine = create_engine(connection_string)

def get_station_data():
    """Fetch station basic info from JCDecaux API."""
    url = "https://api.jcdecaux.com/vls/v1/stations"
    params = {
        "apiKey": BIKE_KEY,
        "contract": "dublin"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching data: {response.status_code}")
        return []

def insert_stations(stations):
    """Insert or update station data in the database."""
    if not stations:
        print("No stations to insert.")
        return

    sql = text("""
        INSERT INTO station (number, contract_name, name, address, bike_stands, lat, lng, banking, bonus)
        VALUES (:number, :contract_name, :name, :address, :bike_stands, :lat, :lng, :banking, :bonus)
        ON DUPLICATE KEY UPDATE
            contract_name = VALUES(contract_name),
            name = VALUES(name),
            address = VALUES(address),
            bike_stands = VALUES(bike_stands),
            lat = VALUES(lat),
            lng = VALUES(lng),
            banking = VALUES(banking),
            bonus = VALUES(bonus)
    """)

    with engine.begin() as conn:
        for station in stations:
            # Prepare values, handling potential discrepancies in field names if any
            vals = {
                "number": station.get('number'),
                "contract_name": station.get('contract_name'),
                "name": station.get('name'),
                "address": station.get('address'),
                "bike_stands": station.get('bike_stands'),
                "lat": station.get('position', {}).get('lat'),
                "lng": station.get('position', {}).get('lng'),
                "banking": 1 if station.get('banking') else 0,
                "bonus": 1 if station.get('bonus') else 0
            }
            conn.execute(sql, vals)
            print(f"Inserted/Updated station: {vals['name']} ({vals['number']})")

if __name__ == "__main__":
    print("Fetching station data from JCDecaux...")
    station_data = get_station_data()
    print(f"Found {len(station_data)} stations. Inserting into database...")
    insert_stations(station_data)
    print("Done.")
