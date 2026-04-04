import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd
import joblib
import requests
from flask import Blueprint, request, jsonify
from sqlalchemy import text

from app.connection import get_db
from config import Config

# 1. Register Blueprint
ml_bp = Blueprint('ml', __name__)


# 2.loading model
print("Loading MLP models...")

bike_model_pipeline = None
stand_model_pipeline = None

try:
    bike_model_pipeline = joblib.load("machine_learning/output_model/bike_availability_mlp_pipeline.joblib")
    print("[Model A] Available bike prediction model loaded successfully!")
except Exception as e:
    print(f"[Model A] Failed to load available bike prediction model: {e}")

try:
    stand_model_pipeline = joblib.load("machine_learning/output_model/bike_stands_mlp_pipeline.joblib")
    print("[Model B] Empty stand prediction model loaded successfully!")
except Exception as e:
    print(f"[Model B] Failed to load empty stand prediction model: {e}")



# 3. Weather Fetching and Caching Mechanism

# Global cache configuration
WEATHER_CACHE = {
    "data": None,
    "last_update": 0
}
CACHE_TTL = 600  # Cache validity: 600 seconds

def fetch_dublin_weather_24h():
    """
    Fetch 24-hour weather forecast from Open-Meteo with a 10-minute in-memory cache and fault-tolerant fallback mechanism
    """
    global WEATHER_CACHE
    current_time = time.time()

    # 1. Check if cache exists and is not expired
    if WEATHER_CACHE["data"] is not None and (current_time - WEATHER_CACHE["last_update"] < CACHE_TTL):
        print("Weather cache hit, skipping API request")
        return WEATHER_CACHE["data"]

    # 2. If cache is expired or empty, prepare to make a new request
    lat, lon = 53.3498, -6.2603
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,surface_pressure&forecast_days=2"

    try:
        print("Making new weather API request...")
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        hourly_data = data["hourly"]
        times = hourly_data["time"]

        now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:00")
        try:
            start_idx = times.index(now_str)
        except ValueError:
            start_idx = 0

        forecasts = []
        for i in range(start_idx, start_idx + 24):
            forecasts.append({
                "main_temp": hourly_data["temperature_2m"][i],
                "main_humidity": hourly_data["relative_humidity_2m"][i],
                "pressure": hourly_data["surface_pressure"][i]
            })

        # 3. Request successful, update cache data and timestamp
        WEATHER_CACHE["data"] = forecasts
        WEATHER_CACHE["last_update"] = current_time
        print("Weather cache updated")

        return forecasts

    except Exception as e:
        print(f"Failed to fetch weather: {e}")

        # 4. Fault tolerance fallback: If current API request fails, but there is expired cache in memory, prioritize using the old cache
        if WEATHER_CACHE["data"] is not None:
            print("Fallback: Using expired weather cache")
            return WEATHER_CACHE["data"]

        # 5. When no cache is available at all, return hardcoded default fallback data
        print("No cache available, returning default fallback weather data")
        return [{"main_temp": 15.0, "main_humidity": 60, "pressure": 1013.0} for _ in range(24)]


# 4. Route Setup (Blueprint-based)

# Route 1: Predict available bike numbers
@ml_bp.route("/bike", methods=["GET"])
def predict_bike():
    try:
        if bike_model_pipeline is None:
            return jsonify({"error": "Bike prediction model not loaded successfully"}), 500

        date_str = request.args.get("date")
        time_str = request.args.get("time")
        station_id = request.args.get("station_id")

        if not all([date_str, time_str, station_id]):
            return jsonify({"error": "Missing required parameters: date, time, or station_id"}), 400

        try:
            station_id = int(station_id)
        except ValueError:
            return jsonify({"error": "station_id must be a valid number"}), 400

        bike_stands = 0
        try:
            engine = get_db()
            with engine.connect() as conn:
                sql = text("SELECT bike_stands FROM station WHERE number = :station_id")
                result = conn.execute(sql, {"station_id": station_id}).fetchone()
                if not result:
                    return jsonify({"error": f"Error: Station ID '{station_id}' not found in database"}), 404
                bike_stands = int(result[0])
        except Exception as db_err:
            return jsonify({"error": "Database query failed, please check table structure or connection"}), 500

        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        hour = dt.hour
        day_of_week = dt.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0

        forecasts = fetch_dublin_weather_24h()
        delta_hours = int((dt - datetime.now()).total_seconds() // 3600)
        target_idx = max(0, min(23, delta_hours))
        weather = forecasts[target_idx]

        input_dict = {
            'bike_stands': [bike_stands],
            'temp': [weather["main_temp"] + 273.15],
            'humidity': [weather["main_humidity"]],
            'pressure': [weather["pressure"]],
            'hour': [hour],
            'day_of_week': [day_of_week],
            'is_weekend': [is_weekend],
            'wind_speed': [weather.get("wind_speed", 0.0)],
            'rain_1h': [weather.get("rain_1h", 0.0)]
        }

        input_df = pd.DataFrame(input_dict)
        station_col_name = f'number_{station_id}'
        input_df[station_col_name] = 1

        expected_features = bike_model_pipeline.feature_names_in_
        input_df = input_df.reindex(columns=expected_features, fill_value=0)

        prediction = bike_model_pipeline.predict(input_df)
        predicted_bikes = int(round(prediction[0]))
        result = max(0, min(predicted_bikes, bike_stands))

        return jsonify({
            "status": "success",
            "request_info": {
                "station_id": station_id,
                "bike_stands_capacity": bike_stands,
                "forecast_datetime": f"{date_str} {time_str}"
            },
            "predicted_available_bikes": result
        })

    except Exception as e:
        return jsonify({"error": "Internal server prediction error", "details": str(e)}), 500


# Route 2: Predict empty stand numbers
@ml_bp.route("/stand", methods=["GET"])
def predict_stand():
    try:
        if stand_model_pipeline is None:
            return jsonify({"error": "Empty stand prediction model not loaded successfully"}), 500

        date_str = request.args.get("date")
        time_str = request.args.get("time")
        station_id = request.args.get("station_id")

        if not all([date_str, time_str, station_id]):
            return jsonify({"error": "Missing required parameters: date, time or station_id"}), 400

        try:
            station_id = int(station_id)
        except ValueError:
            return jsonify({"error": "station_id must be an integer"}), 400

        bike_stands = 0
        try:
            engine = get_db()
            with engine.connect() as conn:
                sql = text("SELECT bike_stands FROM station WHERE number = :station_id")
                result = conn.execute(sql, {"station_id": station_id}).fetchone()
                if not result:
                    return jsonify({"error": f"Error: Station ID '{station_id}' not found in database"}), 404
                bike_stands = int(result[0])
        except Exception as db_err:
            return jsonify({"error": "Database query failed, please check table structure or connection"}), 500

        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        hour = dt.hour
        day_of_week = dt.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0

        forecasts = fetch_dublin_weather_24h()
        delta_hours = int((dt - datetime.now()).total_seconds() // 3600)
        target_idx = max(0, min(23, delta_hours))
        weather = forecasts[target_idx]

        input_dict = {
            'bike_stands': [bike_stands],
            'temp': [weather["main_temp"] + 273.15],
            'humidity': [weather["main_humidity"]],
            'pressure': [weather["pressure"]],
            'hour': [hour],
            'day_of_week': [day_of_week],
            'is_weekend': [is_weekend]
        }

        input_df = pd.DataFrame(input_dict)
        station_col_name = f'number_{station_id}'
        input_df[station_col_name] = 1

        expected_features = stand_model_pipeline.feature_names_in_
        input_df = input_df.reindex(columns=expected_features, fill_value=0)

        prediction = stand_model_pipeline.predict(input_df)
        predicted_empty_stands = int(round(prediction[0]))
        predicted_empty_stands = max(0, min(predicted_empty_stands, bike_stands))

        return jsonify({
            "status": "success",
            "request_info": {
                "station_id": station_id,
                "bike_stands_capacity": bike_stands,
                "forecast_datetime": f"{date_str} {time_str}"
            },
            "predicted_empty_stands": predicted_empty_stands
        })

    except Exception as e:
        return jsonify({"error": "Internal server prediction error, please check logs", "details": str(e)}), 500


# Route 3: Predict available bikes for the [next 24 hours]
@ml_bp.route("/bike/24h", methods=["GET"])
def predict_bikes_24h():
    if bike_model_pipeline is None:
        return jsonify({"error": "Available bike model not loaded successfully"}), 500

    try:
        date_str = request.args.get("date")
        time_str = request.args.get("time")
        station_id = request.args.get("station_id")

        if not all([date_str, time_str, station_id]):
            return jsonify({"error": "Missing required parameters: date, time or station_id"}), 400

        station_id = int(station_id)

        bike_stands = 0
        try:
            engine = get_db()
            with engine.connect() as conn:
                sql = text("SELECT bike_stands FROM station WHERE number = :station_id")
                result = conn.execute(sql, {"station_id": station_id}).fetchone()
                if not result:
                    return jsonify({"error": f"Error: Station ID '{station_id}' not found in database"}), 404
                bike_stands = int(result[0])
        except Exception as db_err:
            return jsonify({"error": "Database query failed, please check table structure or connection"}), 500

        try:
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        weathers_24h = fetch_dublin_weather_24h()
        input_data_list = []
        timestamps = []

        for i in range(24):
            current_dt = start_dt + timedelta(hours=i)
            weather = weathers_24h[i]
            timestamps.append(current_dt.strftime("%Y-%m-%d %H:00:00"))

            input_data_list.append({
                'bike_stands': bike_stands,
                'temp': weather["main_temp"] + 273.15,
                'humidity': weather["main_humidity"],
                'pressure': weather["pressure"],
                'hour': current_dt.hour,
                'day_of_week': current_dt.weekday(),
                'is_weekend': 1 if current_dt.weekday() >= 5 else 0
            })

        input_df = pd.DataFrame(input_data_list)
        station_col_name = f'number_{station_id}'
        input_df[station_col_name] = 1

        expected_features = bike_model_pipeline.feature_names_in_
        input_df = input_df.reindex(columns=expected_features, fill_value=0)

        predictions = bike_model_pipeline.predict(input_df)
        predicted_available_bikes_list = []

        for pred in predictions:
            avail_bikes = int(round(pred))
            avail_bikes = max(0, min(avail_bikes, bike_stands))
            predicted_available_bikes_list.append(avail_bikes)

        return jsonify({
            "status": "success",
            "request_info": {
                "station_id": station_id,
                "bike_stands_capacity": bike_stands
            },
            "chart_data": {
                "labels": timestamps,
                "data_available_bikes": predicted_available_bikes_list
            }
        })

    except Exception as e:
        return jsonify({"error": "Internal server error, please check backend console logs", "details": str(e)}), 500


# Route 4: Predict empty stands for the [next 24 hours]
@ml_bp.route("/stand/24h", methods=["GET"])
def predict_stands_24h():
    if stand_model_pipeline is None:
        return jsonify({"error": "Empty stand model not loaded successfully"}), 500

    try:
        date_str = request.args.get("date")
        time_str = request.args.get("time")
        station_id = request.args.get("station_id")

        if not all([date_str, time_str, station_id]):
            return jsonify({"error": "Missing required parameters: date, time or station_id"}), 400

        station_id = int(station_id)

        bike_stands = 0
        try:
            engine = get_db()
            with engine.connect() as conn:
                sql = text("SELECT bike_stands FROM station WHERE number = :station_id")
                result = conn.execute(sql, {"station_id": station_id}).fetchone()
                if not result:
                    return jsonify({"error": f"Error: Station ID '{station_id}' not found in database"}), 404
                bike_stands = int(result[0])
        except Exception as db_err:
            return jsonify({"error": "Database query failed, please check table structure or connection"}), 500

        try:
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        weathers_24h = fetch_dublin_weather_24h()
        input_data_list = []
        timestamps = []

        for i in range(24):
            current_dt = start_dt + timedelta(hours=i)
            weather = weathers_24h[i]
            timestamps.append(current_dt.strftime("%Y-%m-%d %H:00:00"))

            input_data_list.append({
                'bike_stands': bike_stands,
                'temp': weather["main_temp"] + 273.15,
                'humidity': weather["main_humidity"],
                'pressure': weather["pressure"],
                'hour': current_dt.hour,
                'day_of_week': current_dt.weekday(),
                'is_weekend': 1 if current_dt.weekday() >= 5 else 0
            })

        input_df = pd.DataFrame(input_data_list)
        station_col_name = f'number_{station_id}'
        input_df[station_col_name] = 1

        expected_features = stand_model_pipeline.feature_names_in_
        input_df = input_df.reindex(columns=expected_features, fill_value=0)

        predictions = stand_model_pipeline.predict(input_df)
        predicted_empty_stands_list = []

        for pred in predictions:
            empty_stands = int(round(pred))
            empty_stands = max(0, min(empty_stands, bike_stands))
            predicted_empty_stands_list.append(empty_stands)

        return jsonify({
            "status": "success",
            "request_info": {
                "station_id": station_id,
                "bike_stands_capacity": bike_stands
            },
            "chart_data": {
                "labels": timestamps,
                "data_empty_stands": predicted_empty_stands_list
            }
        })

    except Exception as e:
        return jsonify({"error": "Internal server error, please check backend console logs", "details": str(e)}), 500