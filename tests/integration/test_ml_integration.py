"""
Integration tests for ML prediction routes.

These tests use the real .joblib model files on disk and make a real HTTP
request to the Open-Meteo weather API via the Flask routes — no mocking,
no @patch, no MagicMock.

The DB is also real: each route queries the 'station' table to look up the
bike_stands capacity for the requested station, so the environment variables
for the database connection must be present (loaded from the project root
.env file via python-dotenv).

Run with:
    python -m unittest tests.integration.test_ml_integration -v
"""

import unittest
from datetime import datetime

from dotenv import load_dotenv

# Must execute before any Config or app import so os.getenv() in Config sees
# the real values rather than None.
load_dotenv()

import app.connection as _conn_module
from app import create_app
from app.routes import machine_learning as _ml_module
from config import DevelopmentConfig


# ---------------------------------------------------------------------------
# Module-level app — created once to avoid double-registering blueprints /
# re-initialising the cache against a different Flask instance.
# The engine singleton is reset first so no stale state from other test
# modules leaks into this suite.
# ---------------------------------------------------------------------------
_conn_module._engine = None
_app = create_app(DevelopmentConfig)

# Station 1 (CLONTARF ROAD) is a known Dublin Bikes station present in the DB.
_STATION_ID = 1

# Generate date and time dynamically so the test is never stale.
_NOW = datetime.now()
_TODAY = _NOW.strftime("%Y-%m-%d")
_NOW_TIME = _NOW.strftime("%H:%M")


class TestPredictBikeIntegration(unittest.TestCase):
    """
    Verifies GET /predict/bike against the real MLP bike-availability model,
    the real MySQL station table, and the real Open-Meteo weather API.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # Verifies that /predict/bike loads the bike MLP pipeline from the .joblib
    # file, queries the real DB for station 1's bike_stands capacity, fetches
    # live weather from Open-Meteo for Dublin, and returns a single integer
    # prediction that has been clamped to the valid [0, capacity] range.
    def test_predict_bike_single_point_returns_valid_integer(self):
        """
        Real integration verified: GET /predict/bike runs the MLP pipeline
        loaded from disk against a live weather forecast and a DB-sourced
        capacity value. Asserts HTTP 200, status == 'success', and that
        predicted_available_bikes is an int within [0, bike_stands_capacity].
        """
        if _ml_module.bike_model_pipeline is None:
            self.skipTest(
                "bike_availability_mlp_pipeline.joblib not loaded — "
                "skipping bike prediction integration test"
            )

        resp = self.client.get(
            "/predict/bike",
            query_string={"station_id": _STATION_ID, "date": _TODAY, "time": _NOW_TIME},
        )

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "success",
                         f"Expected status 'success', got: {data}")

        capacity = data["request_info"]["bike_stands_capacity"]
        predicted = data["predicted_available_bikes"]

        self.assertIsInstance(predicted, int,
                              "'predicted_available_bikes' should be an int")
        self.assertGreaterEqual(predicted, 0,
                                f"predicted_available_bikes {predicted} is negative")
        self.assertLessEqual(predicted, capacity,
                             f"predicted_available_bikes {predicted} exceeds capacity {capacity}")


class TestPredictStandIntegration(unittest.TestCase):
    """
    Verifies GET /predict/stand against the real MLP empty-stands model,
    the real MySQL station table, and the real Open-Meteo weather API.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # Verifies that /predict/stand loads the empty-stands MLP pipeline from
    # the .joblib file, queries the real DB for station 1's capacity, fetches
    # live Dublin weather from Open-Meteo, and returns an integer prediction
    # clamped to [0, capacity].
    def test_predict_stand_single_point_returns_valid_integer(self):
        """
        Real integration verified: GET /predict/stand runs the MLP pipeline
        loaded from disk against a live weather forecast and a DB-sourced
        capacity value. Asserts HTTP 200, status == 'success', and that
        predicted_empty_stands is an int within [0, bike_stands_capacity].
        """
        if _ml_module.stand_model_pipeline is None:
            self.skipTest(
                "bike_stands_mlp_pipeline.joblib not loaded — "
                "skipping stand prediction integration test"
            )

        resp = self.client.get(
            "/predict/stand",
            query_string={"station_id": _STATION_ID, "date": _TODAY, "time": _NOW_TIME},
        )

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "success",
                         f"Expected status 'success', got: {data}")

        capacity = data["request_info"]["bike_stands_capacity"]
        predicted = data["predicted_empty_stands"]

        self.assertIsInstance(predicted, int,
                              "'predicted_empty_stands' should be an int")
        self.assertGreaterEqual(predicted, 0,
                                f"predicted_empty_stands {predicted} is negative")
        self.assertLessEqual(predicted, capacity,
                             f"predicted_empty_stands {predicted} exceeds capacity {capacity}")


class TestPredictBike24hIntegration(unittest.TestCase):
    """
    Verifies GET /predict/bike/24h against the real MLP bike-availability
    model, the real MySQL station table, and the real Open-Meteo 24-hour
    weather forecast.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # Verifies that /predict/bike/24h iterates over the 24-hour Open-Meteo
    # forecast for Dublin, runs one MLP inference per hour using the real
    # .joblib pipeline, and returns exactly 24 integers each clamped to
    # [0, bike_stands_capacity].  This confirms the weather slice indexing,
    # the batch predict call, and the per-prediction clamping logic all work
    # end-to-end without any stubbing.
    def test_predict_bike_24h_returns_24_valid_integers(self):
        """
        Real integration verified: GET /predict/bike/24h runs 24 MLP
        inferences against a live Open-Meteo forecast and a DB-sourced
        capacity. Asserts HTTP 200, status == 'success',
        chart_data.data_available_bikes is a list of exactly 24 ints all
        within [0, bike_stands_capacity].
        """
        if _ml_module.bike_model_pipeline is None:
            self.skipTest(
                "bike_availability_mlp_pipeline.joblib not loaded — "
                "skipping 24h bike prediction integration test"
            )

        resp = self.client.get(
            "/predict/bike/24h",
            query_string={"station_id": _STATION_ID, "date": _TODAY, "time": _NOW_TIME},
        )

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "success",
                         f"Expected status 'success', got: {data}")

        capacity = data["request_info"]["bike_stands_capacity"]
        predictions = data["chart_data"]["data_available_bikes"]

        self.assertIsInstance(predictions, list,
                              "'data_available_bikes' should be a list")
        self.assertEqual(len(predictions), 24,
                         f"Expected 24 hourly predictions, got {len(predictions)}")

        for i, val in enumerate(predictions):
            self.assertIsInstance(val, int,
                                  f"predictions[{i}] = {val!r} is not an int")
            self.assertGreaterEqual(val, 0,
                                    f"predictions[{i}] = {val} is negative")
            self.assertLessEqual(val, capacity,
                                 f"predictions[{i}] = {val} exceeds capacity {capacity}")


class TestPredictStand24hIntegration(unittest.TestCase):
    """
    Verifies GET /predict/stand/24h against the real MLP empty-stands model,
    the real MySQL station table, and the real Open-Meteo 24-hour forecast.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # Verifies that /predict/stand/24h iterates over the 24-hour Open-Meteo
    # forecast for Dublin, runs one MLP inference per hour using the real
    # .joblib pipeline, and returns exactly 24 integers each clamped to
    # [0, bike_stands_capacity].
    def test_predict_stand_24h_returns_24_valid_integers(self):
        """
        Real integration verified: GET /predict/stand/24h runs 24 MLP
        inferences against a live Open-Meteo forecast and a DB-sourced
        capacity. Asserts HTTP 200, status == 'success',
        chart_data.data_empty_stands is a list of exactly 24 ints all within
        [0, bike_stands_capacity].
        """
        if _ml_module.stand_model_pipeline is None:
            self.skipTest(
                "bike_stands_mlp_pipeline.joblib not loaded — "
                "skipping 24h stand prediction integration test"
            )

        resp = self.client.get(
            "/predict/stand/24h",
            query_string={"station_id": _STATION_ID, "date": _TODAY, "time": _NOW_TIME},
        )

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "success",
                         f"Expected status 'success', got: {data}")

        capacity = data["request_info"]["bike_stands_capacity"]
        predictions = data["chart_data"]["data_empty_stands"]

        self.assertIsInstance(predictions, list,
                              "'data_empty_stands' should be a list")
        self.assertEqual(len(predictions), 24,
                         f"Expected 24 hourly predictions, got {len(predictions)}")

        for i, val in enumerate(predictions):
            self.assertIsInstance(val, int,
                                  f"predictions[{i}] = {val!r} is not an int")
            self.assertGreaterEqual(val, 0,
                                    f"predictions[{i}] = {val} is negative")
            self.assertLessEqual(val, capacity,
                                 f"predictions[{i}] = {val} exceeds capacity {capacity}")


if __name__ == "__main__":
    unittest.main()
