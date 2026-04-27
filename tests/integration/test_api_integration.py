"""
Integration tests for external API-backed routes.

These tests make real HTTP requests to the JCDecaux, OpenWeather, and Photon
geocoding APIs via the Flask routes — no mocking, no @patch, no MagicMock.

Environment variables (BIKE_KEY, WEATHER_KEY) must be present; they are loaded
from the project root .env file via python-dotenv.

Run with:
    python -m unittest tests.integration.test_api_integration -v
"""

import os
import unittest

from dotenv import load_dotenv

# Must execute before any Config or app import so os.getenv() in Config sees
# the real values rather than None.
load_dotenv()

from app import create_app
from config import DevelopmentConfig


# ---------------------------------------------------------------------------
# Module-level app — created once to avoid double-registering blueprints /
# re-initialising the cache against a different Flask instance.
# ---------------------------------------------------------------------------
_app = create_app(DevelopmentConfig)


class TestBikesAPIIntegration(unittest.TestCase):
    """
    Verifies GET /api/bikes makes a real request to the JCDecaux VLS API and
    returns well-formed station data for the Dublin contract.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # Verifies that /api/bikes calls the live JCDecaux endpoint with the Dublin
    # contract and API key, and that each station object has the fields and types
    # the map frontend depends on (number, available_bikes, available_bike_stands,
    # status).
    def test_bikes_200_non_empty_list_with_correct_shape(self):
        """
        Real integration verified: GET /api/bikes proxies to
        https://api.jcdecaux.com/vls/v1/stations?contract=dublin and returns
        the live station list. Asserts HTTP 200, a non-empty list, and that the
        first item has the expected fields with the correct types.
        """
        if not os.getenv("BIKE_KEY"):
            self.skipTest("BIKE_KEY not set — skipping JCDecaux live-API integration test")

        resp = self.client.get("/api/bikes")

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIsInstance(data, list, "/api/bikes did not return a JSON list")
        self.assertGreater(len(data), 0, "/api/bikes returned an empty list")

        first = data[0]
        for field in ("number", "available_bikes", "available_bike_stands", "status"):
            self.assertIn(field, first, f"station object is missing field '{field}'")

        self.assertIsInstance(first["number"], int,
                              "'number' should be an int")
        self.assertIsInstance(first["available_bikes"], int,
                              "'available_bikes' should be an int")
        self.assertIsInstance(first["available_bike_stands"], int,
                              "'available_bike_stands' should be an int")
        self.assertIsInstance(first["status"], str,
                              "'status' should be a string")


class TestWeatherAPIIntegration(unittest.TestCase):
    """
    Verifies GET /api/weather makes a real request to the OpenWeather current-
    weather endpoint and returns a well-formed payload for Dublin, Ireland.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # Verifies that /api/weather calls the live OpenWeather API with the correct
    # city (dublin, ie) and API key, parses the JSON response, and exposes the
    # top-level keys the frontend weather widget reads (main, weather, wind, name)
    # along with a numeric temp inside the main block.
    def test_weather_200_non_empty_dict_with_correct_shape(self):
        """
        Real integration verified: GET /api/weather proxies to
        https://api.openweathermap.org/data/2.5/weather?q=dublin,ie and returns
        the live weather payload. Asserts HTTP 200, a non-empty dict with keys
        main, weather, wind, name, and that main.temp is numeric.
        """
        if not os.getenv("WEATHER_KEY"):
            self.skipTest("WEATHER_KEY not set — skipping OpenWeather live-API integration test")

        resp = self.client.get("/api/weather")

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIsInstance(data, dict, "/api/weather did not return a JSON object")
        self.assertGreater(len(data), 0, "/api/weather returned an empty dict")

        for key in ("main", "weather", "wind", "name"):
            self.assertIn(key, data, f"/api/weather response is missing top-level key '{key}'")

        main = data["main"]
        self.assertIn("temp", main, "'main' block is missing 'temp'")
        self.assertIsInstance(main["temp"], (int, float),
                              "'main.temp' should be a numeric value")


class TestGeocodeAPIIntegration(unittest.TestCase):
    """
    Verifies GET /api/geocode?q=Dublin makes a real request to the Photon
    geocoding API (photon.komoot.io) and returns Dublin-area results.
    No API key is required — Photon is a free, open service.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # Verifies that /api/geocode calls the live Photon API, parses the GeoJSON
    # FeatureCollection response, and returns results whose coordinates fall
    # within the expected Dublin bounding box.  No API key skip needed —
    # Photon requires no authentication.
    def test_geocode_dublin_200_non_empty_with_valid_coordinates(self):
        """
        Real integration verified: GET /api/geocode?q=Dublin proxies to
        https://photon.komoot.io/api/?q=Dublin&bbox=... and parses the GeoJSON
        response into a flat list. Asserts HTTP 200, a non-empty list, that the
        first item has name, lat, lng fields, that lat and lng are floats, and
        that both fall within the valid Dublin coordinate ranges.
        """
        resp = self.client.get("/api/geocode?q=Dublin")

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIsInstance(data, list, "/api/geocode did not return a JSON list")
        self.assertGreater(len(data), 0, "/api/geocode?q=Dublin returned an empty list")

        first = data[0]
        for field in ("name", "lat", "lng"):
            self.assertIn(field, first, f"geocode result is missing field '{field}'")

        lat = first["lat"]
        lng = first["lng"]

        self.assertIsInstance(lat, float, "'lat' should be a float")
        self.assertIsInstance(lng, float, "'lng' should be a float")

        self.assertGreaterEqual(lat, 53.2,
                                f"lat {lat} is below the Dublin range (53.2–53.5)")
        self.assertLessEqual(lat, 53.5,
                              f"lat {lat} is above the Dublin range (53.2–53.5)")
        self.assertGreaterEqual(lng, -6.4,
                                f"lng {lng} is below the Dublin range (-6.4 to -6.0)")
        self.assertLessEqual(lng, -6.0,
                              f"lng {lng} is above the Dublin range (-6.4 to -6.0)")


if __name__ == "__main__":
    unittest.main()
