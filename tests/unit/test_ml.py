"""
Tests for machine learning prediction routes in app/routes/machine_learning.py.

The routes depend on two joblib models that are loaded at module import time
(not inside the route functions).  We therefore patch the module-level
variables directly:

    app.routes.machine_learning.bike_model_pipeline
    app.routes.machine_learning.stand_model_pipeline

rather than patching joblib.load, which would be too late.

The Open-Meteo weather API is called inside fetch_dublin_weather_24h().
We patch:

    app.routes.machine_learning.requests.get

The SQLAlchemy engine is obtained via get_db() inside each route.  We patch:

    app.routes.machine_learning.get_db

The module-level WEATHER_CACHE dict is reset before every test so that a warm
cache from one test cannot mask a patched requests.get in the next test.
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app import create_app
from config import TestingConfig
import app.routes.machine_learning as ml_module

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------
STATION_ID = 42
BIKE_STANDS = 20
DATE_STR = "2026-04-08"
TIME_STR = "12:00:00"

# Feature lists must include the station one-hot column so that reindex()
# does not drop it and the mock predict() receives a coherent DataFrame.
BIKE_FEATURES = [
    "bike_stands", "temp", "humidity", "pressure",
    "hour", "day_of_week", "is_weekend", "wind_speed", "rain_1h",
    f"number_{STATION_ID}",
]

STAND_FEATURES = [
    "bike_stands", "temp", "humidity", "pressure",
    "hour", "day_of_week", "is_weekend",
    f"number_{STATION_ID}",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_db_engine(bike_stands=BIKE_STANDS, station_found=True):
    """
    Return a MagicMock SQLAlchemy engine whose context manager yields a mock
    connection.  conn.execute(...).fetchone() returns a tuple so that
    int(result[0]) works exactly as in production code.
    """
    engine = MagicMock()
    conn = MagicMock()
    row = (bike_stands,) if station_found else None
    conn.execute.return_value.fetchone.return_value = row
    engine.connect.return_value.__enter__ = lambda s: conn
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return engine


def _mock_weather_response():
    """
    Return a MagicMock requests.Response with a valid Open-Meteo hourly
    payload.  The time list starts at the current UTC hour so that
    times.index(now_str) succeeds inside fetch_dublin_weather_24h().
    """
    now = datetime.utcnow()
    times = [
        (now + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00")
        for i in range(48)
    ]
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "hourly": {
            "time": times,
            "temperature_2m": [15.0] * 48,
            "relative_humidity_2m": [60] * 48,
            "surface_pressure": [1013.0] * 48,
        }
    }
    return resp


def _reset_weather_cache():
    """Clear the module-level weather cache before each test."""
    ml_module.WEATHER_CACHE["data"] = None
    ml_module.WEATHER_CACHE["last_update"] = 0


# ===========================================================================
# GET /predict/bike
# ===========================================================================
class TestPredictBike(unittest.TestCase):
    """Tests for GET /predict/bike  (single-point bike availability forecast)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        _reset_weather_cache()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    @patch("app.routes.machine_learning.get_db")
    @patch("app.routes.machine_learning.requests.get")
    @patch("app.routes.machine_learning.bike_model_pipeline")
    def test_predict_bike_happy_path(self, mock_pipeline, mock_requests_get, mock_get_db):
        """
        When all required parameters are supplied and the model, DB, and
        weather API all respond correctly, /predict/bike must return 200 and a
        JSON object whose 'predicted_available_bikes' is a non-negative integer
        no greater than the station's bike_stands capacity.
        """
        mock_pipeline.feature_names_in_ = BIKE_FEATURES
        mock_pipeline.predict.return_value = [5]
        mock_requests_get.return_value = _mock_weather_response()
        mock_get_db.return_value = _mock_db_engine()

        response = self.client.get(
            f"/predict/bike?station_id={STATION_ID}&date={DATE_STR}&time={TIME_STR}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("predicted_available_bikes", data)
        predicted = data["predicted_available_bikes"]
        self.assertIsInstance(predicted, int)
        self.assertGreaterEqual(predicted, 0)
        self.assertLessEqual(predicted, BIKE_STANDS)

    # ------------------------------------------------------------------
    # Missing station_id → 400
    # ------------------------------------------------------------------
    @patch("app.routes.machine_learning.bike_model_pipeline")
    def test_predict_bike_missing_station_id(self, mock_pipeline):
        """
        When station_id is omitted from the query string, /predict/bike must
        return 400 because the route explicitly checks that date, time, and
        station_id are all present.  The model is patched to ensure we reach
        the parameter-validation branch rather than failing on a None model.
        """
        mock_pipeline.feature_names_in_ = BIKE_FEATURES
        mock_pipeline.predict.return_value = [5]

        response = self.client.get(f"/predict/bike?date={DATE_STR}&time={TIME_STR}")

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    # ------------------------------------------------------------------
    # Non-numeric station_id → 400
    # ------------------------------------------------------------------
    @patch("app.routes.machine_learning.bike_model_pipeline")
    def test_predict_bike_invalid_station_id(self, mock_pipeline):
        """
        When station_id is a non-numeric string (e.g. 'abc'), /predict/bike
        must return 400 because int(station_id) raises ValueError which is
        caught and converted to an error response.
        """
        mock_pipeline.feature_names_in_ = BIKE_FEATURES
        mock_pipeline.predict.return_value = [5]

        response = self.client.get(
            f"/predict/bike?station_id=abc&date={DATE_STR}&time={TIME_STR}"
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)


# ===========================================================================
# GET /predict/stand
# ===========================================================================
class TestPredictStand(unittest.TestCase):
    """Tests for GET /predict/stand  (single-point empty-stand forecast)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        _reset_weather_cache()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    @patch("app.routes.machine_learning.get_db")
    @patch("app.routes.machine_learning.requests.get")
    @patch("app.routes.machine_learning.stand_model_pipeline")
    def test_predict_stand_happy_path(self, mock_pipeline, mock_requests_get, mock_get_db):
        """
        When all required parameters are supplied and the model, DB, and
        weather API all respond correctly, /predict/stand must return 200 and a
        JSON object whose 'predicted_empty_stands' is a non-negative integer
        no greater than the station's bike_stands capacity.
        """
        mock_pipeline.feature_names_in_ = STAND_FEATURES
        mock_pipeline.predict.return_value = [5]
        mock_requests_get.return_value = _mock_weather_response()
        mock_get_db.return_value = _mock_db_engine()

        response = self.client.get(
            f"/predict/stand?station_id={STATION_ID}&date={DATE_STR}&time={TIME_STR}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("predicted_empty_stands", data)
        predicted = data["predicted_empty_stands"]
        self.assertIsInstance(predicted, int)
        self.assertGreaterEqual(predicted, 0)
        self.assertLessEqual(predicted, BIKE_STANDS)

    # ------------------------------------------------------------------
    # Missing station_id → 400
    # ------------------------------------------------------------------
    @patch("app.routes.machine_learning.stand_model_pipeline")
    def test_predict_stand_missing_station_id(self, mock_pipeline):
        """
        When station_id is omitted, /predict/stand must return 400 because
        all three parameters (date, time, station_id) are required.
        """
        mock_pipeline.feature_names_in_ = STAND_FEATURES
        mock_pipeline.predict.return_value = [5]

        response = self.client.get(f"/predict/stand?date={DATE_STR}&time={TIME_STR}")

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    # ------------------------------------------------------------------
    # Non-numeric station_id → 400
    # ------------------------------------------------------------------
    @patch("app.routes.machine_learning.stand_model_pipeline")
    def test_predict_stand_invalid_station_id(self, mock_pipeline):
        """
        When station_id is a non-numeric string (e.g. 'xyz'), /predict/stand
        must return 400 because int(station_id) raises ValueError which the
        route catches and returns as a 400 error response.
        """
        mock_pipeline.feature_names_in_ = STAND_FEATURES
        mock_pipeline.predict.return_value = [5]

        response = self.client.get(
            f"/predict/stand?station_id=xyz&date={DATE_STR}&time={TIME_STR}"
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)


# ===========================================================================
# GET /predict/bike/24h
# ===========================================================================
class TestPredictBike24h(unittest.TestCase):
    """Tests for GET /predict/bike/24h  (24-hour bike availability chart data)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        _reset_weather_cache()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    @patch("app.routes.machine_learning.get_db")
    @patch("app.routes.machine_learning.requests.get")
    @patch("app.routes.machine_learning.bike_model_pipeline")
    def test_predict_bike_24h_happy_path(self, mock_pipeline, mock_requests_get, mock_get_db):
        """
        When all inputs are valid and both the weather API and model respond
        correctly, /predict/bike/24h must return 200 and chart_data containing
        'labels' and 'data_available_bikes' lists of exactly 24 entries.
        Every prediction must be a non-negative integer bounded by capacity.
        """
        mock_pipeline.feature_names_in_ = BIKE_FEATURES
        mock_pipeline.predict.return_value = [5] * 24
        mock_requests_get.return_value = _mock_weather_response()
        mock_get_db.return_value = _mock_db_engine()

        response = self.client.get(
            f"/predict/bike/24h?station_id={STATION_ID}&date={DATE_STR}&time={TIME_STR}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        chart = data["chart_data"]
        self.assertIn("labels", chart)
        self.assertIn("data_available_bikes", chart)
        self.assertEqual(len(chart["labels"]), 24)
        self.assertEqual(len(chart["data_available_bikes"]), 24)
        for val in chart["data_available_bikes"]:
            self.assertIsInstance(val, int)
            self.assertGreaterEqual(val, 0)
            self.assertLessEqual(val, BIKE_STANDS)

    # ------------------------------------------------------------------
    # Open-Meteo raises an exception — graceful fallback
    # ------------------------------------------------------------------
    @patch("app.routes.machine_learning.get_db")
    @patch("app.routes.machine_learning.requests.get")
    @patch("app.routes.machine_learning.bike_model_pipeline")
    def test_predict_bike_24h_weather_exception(self, mock_pipeline, mock_requests_get, mock_get_db):
        """
        When requests.get raises a ConnectionError (Open-Meteo unreachable)
        and no prior cache exists, fetch_dublin_weather_24h() must return the
        hardcoded default weather data rather than propagating the exception.
        /predict/bike/24h must still return 200 with 24 predictions, confirming
        the route is resilient to weather API failures.
        """
        mock_pipeline.feature_names_in_ = BIKE_FEATURES
        mock_pipeline.predict.return_value = [5] * 24
        mock_requests_get.side_effect = ConnectionError("Open-Meteo unreachable")
        mock_get_db.return_value = _mock_db_engine()

        response = self.client.get(
            f"/predict/bike/24h?station_id={STATION_ID}&date={DATE_STR}&time={TIME_STR}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["chart_data"]["data_available_bikes"]), 24)


# ===========================================================================
# GET /predict/stand/24h
# ===========================================================================
class TestPredictStand24h(unittest.TestCase):
    """Tests for GET /predict/stand/24h  (24-hour empty-stand chart data)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        _reset_weather_cache()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    @patch("app.routes.machine_learning.get_db")
    @patch("app.routes.machine_learning.requests.get")
    @patch("app.routes.machine_learning.stand_model_pipeline")
    def test_predict_stand_24h_happy_path(self, mock_pipeline, mock_requests_get, mock_get_db):
        """
        When all inputs are valid and both the weather API and model respond
        correctly, /predict/stand/24h must return 200 and chart_data containing
        'labels' and 'data_empty_stands' lists of exactly 24 entries.
        Every prediction must be a non-negative integer bounded by capacity.
        """
        mock_pipeline.feature_names_in_ = STAND_FEATURES
        mock_pipeline.predict.return_value = [5] * 24
        mock_requests_get.return_value = _mock_weather_response()
        mock_get_db.return_value = _mock_db_engine()

        response = self.client.get(
            f"/predict/stand/24h?station_id={STATION_ID}&date={DATE_STR}&time={TIME_STR}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        chart = data["chart_data"]
        self.assertIn("labels", chart)
        self.assertIn("data_empty_stands", chart)
        self.assertEqual(len(chart["labels"]), 24)
        self.assertEqual(len(chart["data_empty_stands"]), 24)
        for val in chart["data_empty_stands"]:
            self.assertIsInstance(val, int)
            self.assertGreaterEqual(val, 0)
            self.assertLessEqual(val, BIKE_STANDS)

    # ------------------------------------------------------------------
    # Open-Meteo raises an exception — graceful fallback
    # ------------------------------------------------------------------
    @patch("app.routes.machine_learning.get_db")
    @patch("app.routes.machine_learning.requests.get")
    @patch("app.routes.machine_learning.stand_model_pipeline")
    def test_predict_stand_24h_weather_exception(self, mock_pipeline, mock_requests_get, mock_get_db):
        """
        When requests.get raises a ConnectionError (Open-Meteo unreachable)
        and no prior cache exists, fetch_dublin_weather_24h() falls back to
        hardcoded default weather data.  /predict/stand/24h must still return
        200 with 24 predictions, confirming the route does not propagate the
        network failure to the client.
        """
        mock_pipeline.feature_names_in_ = STAND_FEATURES
        mock_pipeline.predict.return_value = [5] * 24
        mock_requests_get.side_effect = ConnectionError("Open-Meteo unreachable")
        mock_get_db.return_value = _mock_db_engine()

        response = self.client.get(
            f"/predict/stand/24h?station_id={STATION_ID}&date={DATE_STR}&time={TIME_STR}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["chart_data"]["data_empty_stands"]), 24)


if __name__ == "__main__":
    unittest.main()
