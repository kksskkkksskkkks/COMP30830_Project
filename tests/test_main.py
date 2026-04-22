"""
Tests for /api/bikes and /api/weather in app/routes/main.py.

Both routes delegate to get_bike_data() / get_weather(), which call
requests.get against external APIs (JCDecaux and OpenWeather).  We mock
requests.get so no real network traffic is produced and tests are fully
deterministic.

Each test class covers one route with three scenarios:
  - happy-path   : API returns valid data  →  200 + correct JSON shape
  - empty-data   : API returns empty payload  →  200, no crash
  - correct-url  : requests.get was invoked with the right URL/params
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app import create_app
from config import TestingConfig
from app.routes.main import cache

# ---------------------------------------------------------------------------
# External API endpoints used by the routes under test
# ---------------------------------------------------------------------------
BIKES_URL = "https://api.jcdecaux.com/vls/v1/stations"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

# ---------------------------------------------------------------------------
# Fixture data — realistic payloads matching real API shapes
# ---------------------------------------------------------------------------
FAKE_BIKES = [
    {
        "number": 42,
        "name": "GRAFTON ST",
        "address": "Grafton Street",
        "position": {"lat": 53.3418, "lng": -6.2597},
        "available_bike_stands": 12,
        "available_bikes": 8,
        "status": "OPEN",
        "last_update": 1700000000000,
    }
]

FAKE_WEATHER = {
    "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
    "main": {"temp": 285.5, "feels_like": 283.1, "humidity": 72, "pressure": 1015},
    "wind": {"speed": 4.5, "gust": 7.2},
    "name": "Dublin",
}


def _mock_response(status_code, json_data):
    """Return a MagicMock that mimics a requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    return mock


# ===========================================================================
# /api/bikes
# ===========================================================================
class TestApiBikes(unittest.TestCase):
    """Tests for GET /api/bikes  (wraps JCDecaux, cached 5 min)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        # Clear Flask-Cache before every test so a cached response from one
        # test cannot satisfy the mock-patched request in the next test.
        with self.app.app_context():
            cache.clear()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    @patch("app.routes.main.requests.get")
    def test_bikes_happy_path(self, mock_get, mock_get_db):
        """
        When JCDecaux responds HTTP 200 with station data, /api/bikes must
        return 200 and a JSON array that preserves the expected fields.
        This confirms the route correctly forwards the external payload
        through jsonify() without mutation.
        get_db is patched because the route persists results to DB after a
        successful API fetch.
        """
        mock_get.return_value = _mock_response(200, FAKE_BIKES)
        mock_get_db.return_value = MagicMock()

        response = self.client.get("/api/bikes")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        # Shape checks
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

        station = data[0]
        self.assertIn("number", station)
        self.assertIn("available_bikes", station)
        self.assertIn("available_bike_stands", station)
        self.assertIn("status", station)

        # Value checks
        self.assertEqual(station["number"], 42)
        self.assertEqual(station["available_bikes"], 8)
        self.assertEqual(station["status"], "OPEN")

    # ------------------------------------------------------------------
    # Empty response — API returns [] (no stations active)
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    @patch("app.routes.main.requests.get")
    def test_bikes_empty_response(self, mock_get, mock_get_db):
        """
        When JCDecaux returns HTTP 200 with an empty list (e.g. all stations
        offline or a maintenance window), /api/bikes must still return 200
        and an empty JSON array.  No crash, no 500, no KeyError.
        This guards against any code that assumes at least one station exists.
        """
        mock_get.return_value = _mock_response(200, [])
        mock_get_db.return_value = MagicMock()

        response = self.client.get("/api/bikes")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 0)

    # ------------------------------------------------------------------
    # Correct URL — verify the right endpoint and contract are used
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    @patch("app.routes.main.requests.get")
    def test_bikes_calls_correct_url(self, mock_get, mock_get_db):
        """
        Asserts that get_bike_data() hits the exact JCDecaux v1 stations
        endpoint with contract='dublin'.  Protects against URL regressions
        (e.g. wrong API version, wrong contract string) that would silently
        return data for a different city.
        """
        mock_get.return_value = _mock_response(200, FAKE_BIKES)
        mock_get_db.return_value = MagicMock()

        self.client.get("/api/bikes")

        mock_get.assert_called_once()
        call_args = mock_get.call_args

        # Positional arg 0 is the URL
        self.assertEqual(call_args[0][0], BIKES_URL)

        # Keyword arg 'params' must specify the dublin contract
        params = call_args[1]["params"]
        self.assertEqual(params["contract"], "dublin")


# ===========================================================================
# /api/weather
# ===========================================================================
class TestApiWeather(unittest.TestCase):
    """Tests for GET /api/weather  (wraps OpenWeather, cached 10 min)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        # Same cache-clearing rationale as TestApiBikes.setUp.
        with self.app.app_context():
            cache.clear()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    @patch("app.routes.main.requests.get")
    def test_weather_happy_path(self, mock_get, mock_get_db):
        """
        When OpenWeather responds HTTP 200 with a full weather object,
        /api/weather must return 200 and a JSON dict that contains the
        standard top-level keys (weather, main, wind, name).
        Confirms the route forwards the payload without stripping fields.
        get_db is patched because the route persists results to DB after a
        successful API fetch.
        """
        mock_get.return_value = _mock_response(200, FAKE_WEATHER)
        mock_get_db.return_value = MagicMock()

        response = self.client.get("/api/weather")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        # Shape checks
        self.assertIsInstance(data, dict)
        self.assertIn("weather", data)
        self.assertIn("main", data)
        self.assertIn("wind", data)
        self.assertIn("name", data)

        # Value checks
        self.assertEqual(data["name"], "Dublin")
        self.assertEqual(data["main"]["humidity"], 72)
        self.assertEqual(data["wind"]["speed"], 4.5)

    # ------------------------------------------------------------------
    # Empty response — API returns {} (service hiccup)
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    @patch("app.routes.main.requests.get")
    def test_weather_empty_response(self, mock_get, mock_get_db):
        """
        When OpenWeather returns HTTP 200 with an empty dict, /api/weather
        must still return 200 and an empty JSON object.
        No crash, no 500, no AttributeError on missing keys.
        get_weather() returns {} for non-200 too, so this also covers the
        fallback branch indirectly.
        """
        mock_get.return_value = _mock_response(200, {})
        mock_get_db.return_value = MagicMock()

        response = self.client.get("/api/weather")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, dict)
        self.assertEqual(len(data), 0)

    # ------------------------------------------------------------------
    # Correct URL — verify the right endpoint and city are queried
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    @patch("app.routes.main.requests.get")
    def test_weather_calls_correct_url(self, mock_get, mock_get_db):
        """
        Asserts that get_weather() hits the exact OpenWeather 2.5 endpoint
        with q='dublin, ie'.  Protects against URL regressions or accidental
        changes to the queried city/country that would silently return
        weather for a different location.
        """
        mock_get.return_value = _mock_response(200, FAKE_WEATHER)
        mock_get_db.return_value = MagicMock()

        self.client.get("/api/weather")

        mock_get.assert_called_once()
        call_args = mock_get.call_args

        # Positional arg 0 is the URL
        self.assertEqual(call_args[0][0], WEATHER_URL)

        # Keyword arg 'params' must query Dublin, Ireland
        params = call_args[1]["params"]
        self.assertEqual(params["q"], "dublin, ie")


# ===========================================================================
# DB routes — shared helpers
# ===========================================================================

def _fake_engine(rows):
    """
    Return a MagicMock SQLAlchemy engine whose .execute() yields the given
    rows.  Each row is a plain dict; dict(row) in the view produces an
    identical copy, which is exactly what the routes do.
    """
    mock_engine = MagicMock()
    mock_engine.execute.return_value = rows
    return mock_engine


def _fake_engine_connect(rows):
    """
    Return a MagicMock SQLAlchemy engine whose engine.connect() context
    manager yields a connection whose .execute() returns rows directly.
    Used for routes that use 'with engine.connect() as conn: conn.execute()'.
    Each row is a plain dict so dict(row) works correctly.
    """
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value = rows
    return engine


# ---------------------------------------------------------------------------
# Fixture rows — columns match the real table schemas
# ---------------------------------------------------------------------------
FAKE_STATION_ROWS = [
    {
        "number": 42,
        "name": "GRAFTON ST",
        "address": "Grafton Street",
        "lat": 53.3418,
        "lng": -6.2597,
        "bike_stands": 20,
    }
]

FAKE_AVAILABILITY_ROWS = [
    {
        "number": 42,
        "available_bike_stands": 12,
        "available_bikes": 8,
        "status": "OPEN",
        "last_update": 1700000000000,
    }
]

FAKE_STATION_AVAIL_ROWS = [
    {"available_bikes": 8},
    {"available_bikes": 5},
]

FAKE_WEATHER_CURRENT_ROWS = [
    {
        "dt": "2024-01-01 12:00:00",
        "feels_like": 283.1,
        "humidity": 72,
        "pressure": 1015,
        "sunrise": "2024-01-01 08:00:00",
        "sunset": "2024-01-01 16:30:00",
        "temp": 285.5,
        "weather_id": 800,
        "wind_gust": 7.2,
        "wind_speed": 4.5,
        "rain_1h": None,
        "snow_1h": None,
    }
]


# ===========================================================================
# GET /db/stations
# ===========================================================================
class TestDbStations(unittest.TestCase):
    """Tests for GET /db/stations  (reads from the `station` table)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        with self.app.app_context():
            cache.clear()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    def test_stations_happy_path(self, mock_get_db):
        """
        When the station table contains rows, /db/stations must return 200
        and a JSON object with a 'stations' key holding the full list.
        Confirms that dict(row) conversion and jsonify wrapping both work
        correctly for real-shaped station data.
        """
        mock_get_db.return_value = _fake_engine(FAKE_STATION_ROWS)

        response = self.client.get("/db/stations")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        # Envelope key
        self.assertIn("stations", data)
        stations = data["stations"]

        # Shape
        self.assertIsInstance(stations, list)
        self.assertEqual(len(stations), 1)

        # Values
        first = stations[0]
        self.assertEqual(first["number"], 42)
        self.assertEqual(first["name"], "GRAFTON ST")
        self.assertEqual(first["bike_stands"], 20)

    # ------------------------------------------------------------------
    # Empty DB
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    def test_stations_empty_db(self, mock_get_db):
        """
        When the station table is empty (e.g. after a schema reset or before
        the first scrape), /db/stations must return 200 and an empty list
        under the 'stations' key — no crash, no 500, no IndexError.
        """
        mock_get_db.return_value = _fake_engine([])

        response = self.client.get("/db/stations")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("stations", data)
        self.assertEqual(data["stations"], [])


# ===========================================================================
# GET /db/available
# ===========================================================================
class TestDbAvailable(unittest.TestCase):
    """Tests for GET /db/available  (reads from the `availability` table)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        with self.app.app_context():
            cache.clear()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    def test_available_happy_path(self, mock_get_db):
        """
        When the availability table has rows, /db/available must return 200
        and a JSON object with an 'available' key holding the full list.
        Verifies that live availability fields (available_bikes, status) are
        preserved without transformation.
        """
        mock_get_db.return_value = _fake_engine(FAKE_AVAILABILITY_ROWS)

        response = self.client.get("/db/available")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertIn("available", data)
        available = data["available"]

        self.assertIsInstance(available, list)
        self.assertEqual(len(available), 1)

        first = available[0]
        self.assertEqual(first["number"], 42)
        self.assertEqual(first["available_bikes"], 8)
        self.assertEqual(first["status"], "OPEN")

    # ------------------------------------------------------------------
    # Empty DB
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    def test_available_empty_db(self, mock_get_db):
        """
        When the availability table is empty, /db/available must return 200
        and an empty list under 'available'.  Guards against code that
        assumes at least one availability record exists.
        """
        mock_get_db.return_value = _fake_engine([])

        response = self.client.get("/db/available")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("available", data)
        self.assertEqual(data["available"], [])


# ===========================================================================
# GET /db/available/<station_id>
# ===========================================================================
class TestDbAvailableStation(unittest.TestCase):
    """
    Tests for GET /db/available/<int:station_id>.

    Flask's <int:> converter rejects non-integer path segments before the
    view function is reached, so the invalid-ID test requires no DB mock.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        with self.app.app_context():
            cache.clear()

    # ------------------------------------------------------------------
    # Happy path — valid integer ID with data
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    def test_specific_station_happy_path(self, mock_get_db):
        """
        When the availability table has rows for station 42, GET
        /db/available/42 must return 200 and a JSON object with an
        'available' list containing one dict per historical reading.
        Confirms the station_id is used as a filter and the per-row
        dict conversion works on the narrower result set.
        Uses _fake_engine_connect because the route uses engine.connect()
        context manager after the SQL injection fix.
        """
        mock_get_db.return_value = _fake_engine_connect(FAKE_STATION_AVAIL_ROWS)

        response = self.client.get("/db/available/42")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertIn("available", data)
        available = data["available"]

        self.assertIsInstance(available, list)
        self.assertEqual(len(available), 2)
        self.assertEqual(available[0]["available_bikes"], 8)
        self.assertEqual(available[1]["available_bikes"], 5)

    # ------------------------------------------------------------------
    # Empty DB — valid integer ID, no rows for that station
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    def test_specific_station_empty_db(self, mock_get_db):
        """
        When no availability rows exist for the requested station_id,
        /db/available/<id> must return 200 and an empty list under
        'available'.  This is a normal state (new station, not yet scraped)
        and must not cause a crash or a 404.
        """
        mock_get_db.return_value = _fake_engine_connect([])

        response = self.client.get("/db/available/99")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("available", data)
        self.assertEqual(data["available"], [])

    # ------------------------------------------------------------------
    # Invalid ID — non-numeric path segment
    # ------------------------------------------------------------------
    def test_specific_station_invalid_id(self):
        """
        Flask's <int:station_id> converter rejects non-integer path segments
        at the routing layer, before the view or any DB call is made.
        The expected response is 404.  No DB mock is needed because the
        view function is never invoked.
        This protects against SQL injection via the URL segment — the route
        simply does not exist for non-integer inputs.
        """
        response = self.client.get("/db/available/abc")
        self.assertEqual(response.status_code, 404)


# ===========================================================================
# [NOT IN USE] GET /db/weather/current
# Weather info access has moved api
# ===========================================================================
class TestDbWeatherCurrent(unittest.TestCase):
    # Tests for GET /db/weather/current  (reads from the `current` table).

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        with self.app.app_context():
            cache.clear()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    def test_weather_current_happy_path(self, mock_get_db):
        """
        When the current weather table has rows, /db/weather/current must
        return 200 and a JSON object with a 'weather_current' key holding
        the full list of readings.  Verifies that all meteorological fields
        (temp, humidity, wind_speed, etc.) survive the dict(row) conversion
        and jsonify serialisation without being dropped or renamed.
        """
        mock_get_db.return_value = _fake_engine(FAKE_WEATHER_CURRENT_ROWS)

        response = self.client.get("/db/weather/current")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertIn("weather_current", data)
        readings = data["weather_current"]

        self.assertIsInstance(readings, list)
        self.assertEqual(len(readings), 1)

        reading = readings[0]
        self.assertEqual(reading["humidity"], 72)
        self.assertEqual(reading["temp"], 285.5)
        self.assertEqual(reading["wind_speed"], 4.5)
        self.assertIsNone(reading["rain_1h"])

    # ------------------------------------------------------------------
    # Empty DB
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    def test_weather_current_empty_db(self, mock_get_db):
        """
        When the current weather table is empty (e.g. before the first
        scrape run), /db/weather/current must return 200 and an empty list
        under 'weather_current'.  No crash, no 500, no IndexError.
        """
        mock_get_db.return_value = _fake_engine([])

        response = self.client.get("/db/weather/current")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("weather_current", data)
        self.assertEqual(data["weather_current"], [])

# ===========================================================================
# GET /api/geocode
# ===========================================================================

PHOTON_FEATURE = {
    "properties": {
        "name": "Trinity College",
        "street": "College Green",
        "district": "Dublin 2",
        "suburb": None,
    },
    "geometry": {"coordinates": [-6.2546, 53.3438]},   # [lng, lat]
}


def _photon_response(features):
    """Return a MagicMock requests.Response with a Photon-style GeoJSON body."""
    mock = MagicMock()
    mock.json.return_value = {"features": features}
    return mock


class TestApiGeocode(unittest.TestCase):
    """Tests for GET /api/geocode  (proxies Photon address search for Dublin)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        with self.app.app_context():
            cache.clear()

    # ------------------------------------------------------------------
    # Happy path — Photon returns a feature
    # ------------------------------------------------------------------
    @patch("app.routes.main.requests.get")
    def test_geocode_happy_path(self, mock_get):
        """
        When Photon returns one feature, /api/geocode must return 200 and
        a JSON list with one result that has 'name', 'lat', and 'lng'.
        The name is assembled from the feature's name, street, and district
        properties; coordinates are extracted in (lat, lng) order from the
        GeoJSON [lng, lat] array.
        """
        mock_get.return_value = _photon_response([PHOTON_FEATURE])

        response = self.client.get("/api/geocode?q=Trinity+College")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        result = data[0]
        self.assertIn("name", result)
        self.assertIn("lat", result)
        self.assertIn("lng", result)
        self.assertAlmostEqual(result["lat"], 53.3438)
        self.assertAlmostEqual(result["lng"], -6.2546)
        self.assertIn("Trinity College", result["name"])

    # ------------------------------------------------------------------
    # Empty query string — no Photon call, immediate []
    # ------------------------------------------------------------------
    def test_geocode_empty_query(self):
        """
        When q is an empty string, /api/geocode must return 200 and []
        without calling the Photon API at all.  This is enforced by the
        'if not q: return jsonify([])' guard at the top of the route.
        """
        response = self.client.get("/api/geocode?q=")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    # ------------------------------------------------------------------
    # Missing q parameter — treated as empty
    # ------------------------------------------------------------------
    def test_geocode_missing_query_param(self):
        """
        When the q parameter is absent entirely, request.args.get('q', '')
        returns '' and the route returns [] without hitting Photon.
        """
        response = self.client.get("/api/geocode")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    # ------------------------------------------------------------------
    # Photon returns no features — location not found
    # ------------------------------------------------------------------
    @patch("app.routes.main.requests.get")
    def test_geocode_no_features(self, mock_get):
        """
        When Photon finds no matches (empty 'features' list), /api/geocode
        must return 200 and [] without raising an error.
        """
        mock_get.return_value = _photon_response([])

        response = self.client.get("/api/geocode?q=xyznonexistentplace")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    # ------------------------------------------------------------------
    # Photon unreachable — exception swallowed, returns []
    # ------------------------------------------------------------------
    @patch("app.routes.main.requests.get")
    def test_geocode_photon_down(self, mock_get):
        """
        When requests.get raises (e.g. timeout, connection error), the route's
        except-clause must catch it and return 200 with [] so the frontend
        degrades gracefully rather than showing a 500 error.
        """
        mock_get.side_effect = Exception("Connection timeout")

        response = self.client.get("/api/geocode?q=Grafton+Street")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])


# ===========================================================================
# Page routes — smoke tests
# ===========================================================================
class TestPageRoutes(unittest.TestCase):
    """
    Smoke tests for pages that render templates with no DB interaction
    (/, /safety, /faq) and for auth-guarded pages (/bike/plot, /bike/number).
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)

    def setUp(self):
        # Fresh client per test so session state from authenticated tests
        # never leaks into unauthenticated tests in the same class.
        with self.app.app_context():
            cache.clear()
        self.client = self.app.test_client()

    # ------------------------------------------------------------------
    # Public pages — no session required, no DB call
    # ------------------------------------------------------------------
    def test_home_returns_200(self):
        """GET / must return 200 with no session and no DB interaction."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_safety_returns_200(self):
        """GET /safety must return 200."""
        response = self.client.get("/safety")
        self.assertEqual(response.status_code, 200)

    def test_faq_returns_200(self):
        """GET /faq must return 200."""
        response = self.client.get("/faq")
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # Bike ML pages - unauthenticated
    # ------------------------------------------------------------------
    def test_bike_plot_unauthenticated_redirects(self):
        """
        GET /bike/plot without a session must redirect to /auth/login (302).
        """
        response = self.client.get("/bike/plot")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])

    def test_bike_number_unauthenticated_redirects(self):
        """
        GET /bike/number without a session must redirect to /auth/login (302).
        """
        response = self.client.get("/bike/number")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])

    # ------------------------------------------------------------------
    # Bike ML pages — authenticated
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")   # load_logged_in_user (before_request) calls get_db to populate g.user
    def test_bike_plot_authenticated_returns_200(self, mock_get_db):
        """
        When a user is logged in, GET /bike/plot must return 200 and render the bike_plot template.
        """
        engine = MagicMock()
        conn = engine.connect.return_value.__enter__.return_value
        user_row = MagicMock()
        user_row._mapping = {"user_id": "testuser", "full_name": "Test User",
                             "preferred_language": "en", "created_at": "2024-01-01"}
        conn.execute.return_value.fetchone.return_value = user_row
        mock_get_db.return_value = engine

        with self.client.session_transaction() as sess:
            sess["user_id"] = "testuser"

        response = self.client.get("/bike/plot")
        self.assertEqual(response.status_code, 200)

    @patch("app.routes.auth.get_db")
    def test_bike_number_authenticated_returns_200(self, mock_get_db):
        """
        When a user is logged in, GET /bike/number must return 200 and render
        the bike_return_number template.
        """
        engine = MagicMock()
        conn = engine.connect.return_value.__enter__.return_value
        user_row = MagicMock()
        user_row._mapping = {"user_id": "testuser", "full_name": "Test User",
                             "preferred_language": "en", "created_at": "2024-01-01"}
        conn.execute.return_value.fetchone.return_value = user_row
        mock_get_db.return_value = engine

        with self.client.session_transaction() as sess:
            sess["user_id"] = "testuser"

        response = self.client.get("/bike/number")
        self.assertEqual(response.status_code, 200)


# ===========================================================================
# GET /account
# ===========================================================================

FAKE_USER_ACCOUNT = {
    "user_id": "testuser",
    "full_name": "Test User",
    "preferred_language": "en",
    "created_at": datetime(2024, 1, 1),   # template calls .strftime() on this
}

FAKE_FAV_ROW_MAPPING = {
    "station_number": 42,
    "station_name": "GRAFTON ST",
    "added_at": datetime(2024, 1, 10),    # template calls .strftime() on this
}


class TestAccount(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)

    def setUp(self):
        with self.app.app_context():
            cache.clear()
        self.client = self.app.test_client()

    # ------------------------------------------------------------------
    # Unauthenticated — redirect to login
    # ------------------------------------------------------------------
    def test_account_unauthenticated_redirects(self):
        """
        GET /account without a session must redirect to /auth/login (302).
        """
        response = self.client.get("/account")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])

    # ------------------------------------------------------------------
    # Authenticated — renders page with user data and favorites
    # ------------------------------------------------------------------
    @patch("app.routes.main.get_db")
    @patch("app.routes.auth.get_db")
    def test_account_authenticated_returns_200(self, mock_auth_db, mock_main_db):
        """
        When a user is logged in, GET /account must return 200.
        """
        # Shared engine mock for before_request (auth) and route (main)
        def _make_engine():
            engine = MagicMock()
            conn = engine.connect.return_value.__enter__.return_value
            user_row = MagicMock()
            user_row._mapping = FAKE_USER_ACCOUNT
            conn.execute.return_value.fetchone.return_value = user_row
            fav_row = MagicMock()
            fav_row._mapping = FAKE_FAV_ROW_MAPPING
            conn.execute.return_value.fetchall.return_value = [fav_row]
            return engine

        mock_auth_db.return_value = _make_engine()
        mock_main_db.return_value = _make_engine()

        with self.client.session_transaction() as sess:
            sess["user_id"] = "testuser"

        response = self.client.get("/account")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test User", response.data)


if __name__ == "__main__":
    unittest.main()
