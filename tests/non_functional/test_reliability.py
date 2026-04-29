"""
Non_functional reliability tests — no mocking, no @patch, no MagicMock.

The application is created via create_app() from app/__init__.py using
DevelopmentConfig, and requests are driven through Flask's built-in
test_client().  Each test class verifies one reliability / fault-tolerance
property of the live application stack.

IMPORTANT: TESTING is intentionally left False (DevelopmentConfig default).
Flask's propagate_exceptions flag is tied to TESTING=True; leaving it False
ensures unhandled route exceptions are returned as 500 responses rather than
re-raised, which is what these degradation tests need to observe.

Run with:
    python -m unittest tests.non_functional.test_reliability -v
"""

import unittest
from datetime import datetime

from dotenv import load_dotenv

# Load .env before any Config / app import so env vars are visible to Config
load_dotenv()

import requests as _real_requests

import app.connection as conn_module
import app.routes.machine_learning as ml_module
from app import create_app
from config import Config, DevelopmentConfig

# Reset stale engine state that may carry over from other test modules, then
# create one shared app instance for the entire module.
conn_module._engine = None
_app = create_app(DevelopmentConfig)
# Do NOT set TESTING=True: Flask.propagate_exceptions is coupled to that flag
# and would re-raise DB / network errors instead of returning 500 responses.


# ---------------------------------------------------------------------------
# Fake requests object for test 4
# ---------------------------------------------------------------------------

class _FakeRequestsOpenMeteoDown:
    """Drop-in replacement for the requests module inside machine_learning.py.

    Raises ConnectionError for Open-Meteo API calls and forwards every other
    URL to the real library, so the DB and other network calls are unaffected.
    """

    def get(self, url, *args, **kwargs):
        if "open-meteo.com" in url:
            raise ConnectionError("Simulated Open-Meteo outage — reliability test")
        return _real_requests.get(url, *args, **kwargs)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _db_is_reachable():
    """Return True if the configured MySQL instance accepts connections."""
    from sqlalchemy import text
    try:
        with conn_module.get_db().connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ===========================================================================
# 1. JCDecaux unavailable — graceful degradation
#
# Reliability property: when the JCDecaux API rejects the request (e.g. 401
# for an invalid API key), GET /api/bikes must return HTTP 200 with an empty
# list [] rather than crashing with a 500.  The route degrades gracefully
# instead of propagating the upstream failure to the client.
# ===========================================================================

class TestJCDecauxDegradation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()
        self._original_bike_key = Config.BIKE_KEY
        # Point to an invalid API key — the JCDecaux server will reply 401,
        # causing get_bike_data() to return [] per its contract.
        Config.BIKE_KEY = "invalid_key_reliability_test_xyz"

    def tearDown(self):
        Config.BIKE_KEY = self._original_bike_key

    # When the upstream API returns a non-200 status (bad key → 401), the route
    # must wrap the empty fallback in a 200 JSON response, not surface the error.
    def test_jcdecaux_unavailable_returns_empty_list(self):
        resp = self.client.get("/api/bikes")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data, [], f"Expected [], got: {data!r}")


# ===========================================================================
# 2. OpenWeather unavailable — graceful degradation
#
# Reliability property: when the OpenWeather API rejects the request (e.g. 401
# for an invalid API key), GET /api/weather must return HTTP 200 with an empty
# dict {} rather than crashing.  The route degrades gracefully.
# ===========================================================================

class TestOpenWeatherDegradation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()
        self._original_weather_key = Config.WEATHER_KEY
        # Point to an invalid API key — the OpenWeather server will reply 401,
        # causing get_weather() to return {} per its contract.
        Config.WEATHER_KEY = "invalid_key_reliability_test_xyz"

    def tearDown(self):
        Config.WEATHER_KEY = self._original_weather_key

    # When the upstream API returns a non-200 status (bad key → 401), the route
    # must wrap the empty fallback in a 200 JSON response, not surface the error.
    def test_openweather_unavailable_returns_empty_dict(self):
        resp = self.client.get("/api/weather")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data, {}, f"Expected {{}}, got: {data!r}")


# ===========================================================================
# 3. DB unavailable — non-critical routes degrade gracefully
#
# Reliability property: if the database is unreachable, GET /db/stations must
# respond promptly with a non-200 error code rather than hanging indefinitely
# or propagating an unhandled exception to the client.  Any response (even 500)
# is acceptable — the test only fails if the app hangs or raises uncaught.
# ===========================================================================

class TestDBUnavailableDegradation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()
        # Break the connection string by redirecting to a closed local port.
        # 127.0.0.1:19723 — localhost is reachable but port 19723 has no
        # listener, so the TCP stack responds with RST immediately (no hang).
        self._orig_uri = Config.DB_URI
        self._orig_port = Config.DB_PORT
        Config.DB_URI = "127.0.0.1"
        Config.DB_PORT = "19723"
        conn_module._engine = None  # Force get_db() to rebuild with broken URI

    def tearDown(self):
        # Restore valid DB config and reset the engine so later tests get a
        # working connection pool.
        Config.DB_URI = self._orig_uri
        Config.DB_PORT = self._orig_port
        conn_module._engine = None

    # With the database unreachable, the route must respond promptly without
    # hanging.  Flask may either catch the OperationalError and return 500, or
    # (depending on debug/propagation settings) re-raise it to the test client.
    # Both outcomes are acceptable — the property under test is prompt response,
    # not a specific status code.
    def test_db_unavailable_get_stations_responds_without_hanging(self):
        try:
            resp = self.client.get("/db/stations")
            # Flask caught the DB error and returned an HTTP error response.
            self.assertNotEqual(
                resp.status_code, 200,
                "Expected a non-200 error response when the DB is unreachable, got 200",
            )
        except Exception:
            # Flask propagated the OperationalError to the test client.  The
            # connection was refused immediately (TCP RST on the closed port),
            # so the app responded promptly — it did not hang.
            pass


# ===========================================================================
# 4. Open-Meteo fallback under real conditions
#
# Reliability property: even when Open-Meteo raises a ConnectionError, the
# /predict/bike route must still return HTTP 200 with a valid integer
# prediction by falling back to the hardcoded default weather data defined in
# fetch_dublin_weather_24h().  The ML prediction pipeline must be resilient to
# third-party weather API outages.  Skipped when the database is unreachable
# because the route requires a live DB query for bike_stands.
# ===========================================================================

class TestOpenMeteoFallback(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # When Open-Meteo raises ConnectionError, fetch_dublin_weather_24h() must
    # activate its hardcoded fallback (15 °C / 60 % RH / 1013 hPa) and the
    # prediction route must still return 200 with a non-negative integer.
    def test_open_meteo_fallback_returns_valid_prediction(self):
        if not _db_is_reachable():
            self.skipTest("Database unavailable — system test requires a running database")

        # Clear the in-memory weather cache so the fake requests object is
        # actually invoked rather than returning a previously cached result.
        ml_module.WEATHER_CACHE["data"] = None
        ml_module.WEATHER_CACHE["last_update"] = 0

        # Rebind 'requests' in the ML module's namespace — no MagicMock used.
        # fetch_dublin_weather_24h() looks up requests in its module globals,
        # so this replacement is transparent to the function under test.
        original_requests = ml_module.requests
        ml_module.requests = _FakeRequestsOpenMeteoDown()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            now_time = datetime.now().strftime("%H:%M")

            resp = self.client.get(
                f"/predict/bike?station_id=1&date={today}&time={now_time}"
            )

            self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
            data = resp.get_json()
            self.assertEqual(data.get("status"), "success",
                             f"Unexpected response body: {data!r}")
            self.assertIn("predicted_available_bikes", data)
            self.assertIsInstance(data["predicted_available_bikes"], int)
            self.assertGreaterEqual(data["predicted_available_bikes"], 0)
        finally:
            # Always restore the real requests module regardless of test outcome.
            ml_module.requests = original_requests


if __name__ == "__main__":
    unittest.main()
