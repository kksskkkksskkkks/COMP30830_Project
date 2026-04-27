"""
Integration tests for database-backed routes.

These tests use the real MySQL database via get_db() — no mocks, no patches.
Environment variables (DB_USER, DB_PASSWORD, DB_URI, DB_PORT, DB_NAME) must
be present; they are loaded from the project root .env file via python-dotenv.

Run with:
    python -m unittest tests.integration.test_db_integration -v
"""

import unittest

from dotenv import load_dotenv

# Must execute before any Config or app import so os.getenv() in Config sees
# the real values rather than None.
load_dotenv()

import app.connection as _conn_module   # exposes _engine singleton for reset
from app import create_app
from app.connection import get_db
from config import DevelopmentConfig
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Module-level app — created once to avoid double-registering blueprints /
# re-initialising the cache against a different Flask instance.
# The singleton engine is reset first so no stale mock from unit tests leaks.
# ---------------------------------------------------------------------------
_conn_module._engine = None
_app = create_app(DevelopmentConfig)

# ---------------------------------------------------------------------------
# Test-user credentials — distinctive enough to avoid clashing with real data.
# ---------------------------------------------------------------------------
_TEST_USER_ID = "test_integ_xk9z"
_TEST_PASSWORD = "IntTest_P@ss1"


def _delete_test_user():
    """Remove the integration test user if present (idempotent helper)."""
    engine = get_db()
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM users WHERE user_id = :uid"),
            {"uid": _TEST_USER_ID},
        )


# ===========================================================================
# /db/stations, /db/available, /db/available/<id>, /db/weather/current
# ===========================================================================

class TestDBReadRoutes(unittest.TestCase):
    """
    Exercises the five DB-read routes against the live MySQL database.
    No authentication is required so the before_request hook sets g.user = None
    without touching the DB — only the route itself hits the connection pool.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        # Fresh client per test — no session state carried between tests.
        self.client = self.app.test_client()

    # ------------------------------------------------------------------
    # GET /db/stations
    # ------------------------------------------------------------------
    def test_stations_200_non_empty_and_shape(self):
        """
        Real integration verified: the route connects to MySQL, executes
        'SELECT * FROM station', and serialises every row to JSON.
        Asserts: HTTP 200, envelope key 'stations', list is non-empty, and
        each row exposes number / name / lat / lng / bike_stands — the exact
        fields the map frontend reads to render station markers.
        """
        resp = self.client.get("/db/stations")

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIn("stations", data)

        stations = data["stations"]
        self.assertGreater(len(stations), 0, "station table returned no rows")

        first = stations[0]
        for field in ("number", "name", "lat", "lng", "bike_stands"):
            self.assertIn(field, first, f"station row is missing field '{field}'")

    # ------------------------------------------------------------------
    # GET /db/available
    # ------------------------------------------------------------------
    def test_available_200_non_empty_and_shape(self):
        """
        Real integration verified: the route connects to MySQL, executes
        'SELECT * FROM availability', and serialises every row to JSON.
        Asserts: HTTP 200, envelope key 'available', list is non-empty, and
        each row exposes available_bikes and status — the fields displayed in
        the station popup on the map.
        """
        resp = self.client.get("/db/available")

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIn("available", data)

        available = data["available"]
        self.assertGreater(len(available), 0, "availability table returned no rows")

        first = available[0]
        for field in ("available_bikes", "status"):
            self.assertIn(field, first, f"availability row is missing field '{field}'")

    # ------------------------------------------------------------------
    # GET /db/available/1
    # ------------------------------------------------------------------
    def test_available_station_1_returns_correct_structure(self):
        """
        Real integration verified: the parameterised query
        'SELECT available_bikes FROM availability WHERE number = 1'
        runs against the real DB. Station 1 (CLONTARF ROAD) exists in the
        Dublin Bikes network.
        Asserts: HTTP 200 and the 'available' envelope key is present.
        Any rows returned must expose available_bikes (the only selected column).
        """
        resp = self.client.get("/db/available/1")

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIn("available", data)

        # If the availability scraper has run, each row must have available_bikes.
        for row in data["available"]:
            self.assertIn(
                "available_bikes", row,
                "availability row for station 1 is missing 'available_bikes'",
            )

    # ------------------------------------------------------------------
    # GET /db/available/99999
    # ------------------------------------------------------------------
    def test_available_nonexistent_station_returns_empty_list(self):
        """
        Real integration verified: querying availability for a station number
        that does not exist (99999) returns zero rows from MySQL.
        Asserts: HTTP 200 (not 404 — the route treats no rows as a valid
        empty result) and 'available' is an empty list. This confirms the
        route does not conflate 'no data' with 'server error'.
        """
        resp = self.client.get("/db/available/99999")

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIn("available", data)
        self.assertEqual(data["available"], [])

    # ------------------------------------------------------------------
    # GET /db/weather/current
    # ------------------------------------------------------------------
    def test_weather_current_200_regardless_of_table_contents(self):
        """
        Real integration verified: the route executes 'SELECT * FROM current'
        against the real MySQL 'current' table and returns whatever rows exist.
        Asserts: HTTP 200 and 'weather_current' is a list (possibly empty if
        the weather scraper has not yet populated the table). The route must
        not crash on an empty table.
        """
        resp = self.client.get("/db/weather/current")

        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIn("weather_current", data)
        self.assertIsInstance(data["weather_current"], list)


# ===========================================================================
# POST /auth/register and POST /auth/login — real DB writes and reads
# ===========================================================================

class TestAuthDBIntegration(unittest.TestCase):
    """
    Exercises user registration and login against the real MySQL 'users' table.
    Each test that creates a user row also removes it in tearDown so the suite
    is idempotent across repeated runs.

    Tests are deliberately independent: the login test inserts its own user
    directly via engine.begin() rather than relying on the register route, so
    a bug in register cannot cascade into a login failure.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        # Fresh client per test (session isolation) and guaranteed clean state.
        self.client = self.app.test_client()
        _delete_test_user()

    def tearDown(self):
        # Always clean up even if the test body raised an assertion.
        _delete_test_user()

    # ------------------------------------------------------------------
    # POST /auth/register — persists to DB
    # ------------------------------------------------------------------
    def test_register_redirects_and_user_exists_in_db(self):
        """
        Real integration verified: POST /auth/register with valid form data
        hashes the password, runs INSERT INTO users, and redirects.
        A direct DB query after the response confirms the row was committed to
        MySQL — not silently rolled back when the connection closed.
        This is the definitive check that cannot be replicated by a unit test
        that mocks the engine.
        """
        resp = self.client.post(
            "/auth/register",
            data={
                "user_id": _TEST_USER_ID,
                "password": _TEST_PASSWORD,
                "full_name": "Integration Test User",
            },
        )

        # Route must redirect to login page on success.
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login", resp.headers["Location"])

        # Direct DB verification: was the row actually committed?
        engine = get_db()
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT user_id, full_name FROM users WHERE user_id = :uid"),
                {"uid": _TEST_USER_ID},
            ).fetchone()

        self.assertIsNotNone(
            row,
            "POST /auth/register returned 302 but the user row was NOT found in "
            "the database — the INSERT was likely rolled back (engine.connect() "
            "without an explicit commit or engine.begin()).",
        )
        self.assertEqual(row._mapping["user_id"], _TEST_USER_ID)
        self.assertEqual(row._mapping["full_name"], "Integration Test User")

    # ------------------------------------------------------------------
    # POST /auth/login — correct credentials set session
    # ------------------------------------------------------------------
    def test_login_correct_credentials_sets_session(self):
        """
        Real integration verified: POST /auth/login fetches the password_hash
        from MySQL, runs check_password_hash against the submitted password,
        and writes session['user_id'] on success.
        The test user is inserted directly via engine.begin() (a committed
        transaction) so this test is independent of the register route.
        Asserts: HTTP 302 redirect and session['user_id'] equals the submitted
        user_id — confirming both the DB read and the session write succeeded.
        """
        from werkzeug.security import generate_password_hash

        # Insert via a committed transaction — independent of register route.
        engine = get_db()
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO users (user_id, full_name, password_hash)
                    VALUES (:uid, :name, :pw)
                """),
                {
                    "uid": _TEST_USER_ID,
                    "name": "Integration Test User",
                    "pw": generate_password_hash(_TEST_PASSWORD),
                },
            )

        with self.client as c:
            resp = c.post(
                "/auth/login",
                data={
                    "user_id": _TEST_USER_ID,
                    "password": _TEST_PASSWORD,
                },
            )

            self.assertEqual(resp.status_code, 302)

            with c.session_transaction() as sess:
                self.assertEqual(
                    sess.get("user_id"),
                    _TEST_USER_ID,
                    "session['user_id'] was not set after a successful login",
                )


if __name__ == "__main__":
    unittest.main()
