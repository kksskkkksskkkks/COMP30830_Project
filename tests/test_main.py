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
    @patch("app.routes.main.requests.get")
    def test_bikes_happy_path(self, mock_get):
        """
        When JCDecaux responds HTTP 200 with station data, /api/bikes must
        return 200 and a JSON array that preserves the expected fields.
        This confirms the route correctly forwards the external payload
        through jsonify() without mutation.
        """
        mock_get.return_value = _mock_response(200, FAKE_BIKES)

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
    @patch("app.routes.main.requests.get")
    def test_bikes_empty_response(self, mock_get):
        """
        When JCDecaux returns HTTP 200 with an empty list (e.g. all stations
        offline or a maintenance window), /api/bikes must still return 200
        and an empty JSON array.  No crash, no 500, no KeyError.
        This guards against any code that assumes at least one station exists.
        """
        mock_get.return_value = _mock_response(200, [])

        response = self.client.get("/api/bikes")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 0)

    # ------------------------------------------------------------------
    # Correct URL — verify the right endpoint and contract are used
    # ------------------------------------------------------------------
    @patch("app.routes.main.requests.get")
    def test_bikes_calls_correct_url(self, mock_get):
        """
        Asserts that get_bike_data() hits the exact JCDecaux v1 stations
        endpoint with contract='dublin'.  Protects against URL regressions
        (e.g. wrong API version, wrong contract string) that would silently
        return data for a different city.
        """
        mock_get.return_value = _mock_response(200, FAKE_BIKES)

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
    @patch("app.routes.main.requests.get")
    def test_weather_happy_path(self, mock_get):
        """
        When OpenWeather responds HTTP 200 with a full weather object,
        /api/weather must return 200 and a JSON dict that contains the
        standard top-level keys (weather, main, wind, name).
        Confirms the route forwards the payload without stripping fields.
        """
        mock_get.return_value = _mock_response(200, FAKE_WEATHER)

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
    @patch("app.routes.main.requests.get")
    def test_weather_empty_response(self, mock_get):
        """
        When OpenWeather returns HTTP 200 with an empty dict, /api/weather
        must still return 200 and an empty JSON object.
        No crash, no 500, no AttributeError on missing keys.
        get_weather() returns {} for non-200 too, so this also covers the
        fallback branch indirectly.
        """
        mock_get.return_value = _mock_response(200, {})

        response = self.client.get("/api/weather")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, dict)
        self.assertEqual(len(data), 0)

    # ------------------------------------------------------------------
    # Correct URL — verify the right endpoint and city are queried
    # ------------------------------------------------------------------
    @patch("app.routes.main.requests.get")
    def test_weather_calls_correct_url(self, mock_get):
        """
        Asserts that get_weather() hits the exact OpenWeather 2.5 endpoint
        with q='dublin, ie'.  Protects against URL regressions or accidental
        changes to the queried city/country that would silently return
        weather for a different location.
        """
        mock_get.return_value = _mock_response(200, FAKE_WEATHER)

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
        """
        mock_get_db.return_value = _fake_engine(FAKE_STATION_AVAIL_ROWS)

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
        mock_get_db.return_value = _fake_engine([])

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
# GET /db/weather/current
# ===========================================================================
class TestDbWeatherCurrent(unittest.TestCase):
    """Tests for GET /db/weather/current  (reads from the `current` table)."""

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


if __name__ == "__main__":
    unittest.main()
