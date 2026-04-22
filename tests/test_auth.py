"""
Tests for auth routes in app/routes/auth.py.

Covers: POST /auth/register, POST /auth/login, GET /auth/logout,
        POST /auth/favorites, GET /auth/favorites,
        DELETE /auth/favorites/<station_number>.

All DB calls are suppressed by patching app.routes.auth.get_db.

Key design decisions
---------------------
* before_request hook (load_logged_in_user):
    - Runs before EVERY auth route.
    - Calls get_db() ONLY when session['user_id'] is present.
    - Uses engine.connect(), so it shares connect_conn with read routes
      but is isolated from engine.begin() used by write/delete routes.
* engine.connect() vs engine.begin():
    - MagicMock gives these different return values automatically,
      so connect_conn and begin_conn are independent objects.
* Login hash:
    - generate_password_hash / check_password_hash are called for real
      so the authentication path is fully exercised, not stubbed.
* FakeRow:
    - get_my_favorites calls dict(row.items()); a plain MagicMock does
      not produce a usable dict, so FakeRow provides a real .items().
"""

import unittest
from unittest.mock import patch, MagicMock

from werkzeug.security import generate_password_hash

from app import create_app
from config import TestingConfig
from app.routes.main import cache

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
TEST_USER_ID = "testuser"
TEST_PASSWORD = "testpassword123"
TEST_PASSWORD_HASH = generate_password_hash(TEST_PASSWORD)

FAKE_USER_MAPPING = {
    "user_id": TEST_USER_ID,
    "full_name": "Test User",
    "created_at": "2024-01-01 00:00:00",
}


class FakeRow:
    """
    Minimal SQLAlchemy-row stand-in that supports dict(row.items()).
    Used by get_my_favorites which iterates fetchall() results this way.
    """
    def __init__(self, data: dict):
        self._data = data
        self._mapping = data

    def items(self):
        return self._data.items()


# ---------------------------------------------------------------------------
# Engine / row helpers
# ---------------------------------------------------------------------------

def _build_engine():
    """
    Return (engine, connect_conn, begin_conn).

    MagicMock automatically wires the context-manager protocol so that:
        with engine.connect() as conn: ...   → conn is connect_conn
        with engine.begin()   as conn: ...   → conn is begin_conn
    """
    engine = MagicMock()
    connect_conn = engine.connect.return_value.__enter__.return_value
    begin_conn   = engine.begin.return_value.__enter__.return_value
    return engine, connect_conn, begin_conn


def _user_row():
    """Mock DB row whose ._mapping matches FAKE_USER_MAPPING."""
    row = MagicMock()
    row._mapping = FAKE_USER_MAPPING
    return row


def _login_row(password: str = TEST_PASSWORD):
    """Mock DB row whose ._mapping holds a real bcrypt hash for password."""
    row = MagicMock()
    row._mapping = {"password_hash": generate_password_hash(password)}
    return row


# ===========================================================================
# POST /auth/register
# ===========================================================================
class TestRegister(unittest.TestCase):
    """Tests for POST /auth/register."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)

    def setUp(self):
        # Fresh client per test so session state never leaks.
        with self.app.app_context():
            cache.clear()
        self.client = self.app.test_client()

    # ------------------------------------------------------------------
    # Happy path — new user registered successfully
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")
    def test_register_valid_new_user(self, mock_get_db):
        """
        When valid form data is submitted for a username that does not yet
        exist, register() must hash the password, insert the row, and
        redirect to /auth/login (HTTP 302).
        connect_conn.fetchone returns None → duplicate check passes →
        INSERT executes → redirect issued.
        No session is active so before_request never calls get_db.
        """
        engine, connect_conn, _ = _build_engine()
        connect_conn.execute.return_value.fetchone.return_value = None  # no duplicate
        mock_get_db.return_value = engine

        response = self.client.post("/auth/register", data={
            "user_id": "newuser",
            "password": "securepassword",
            "full_name": "New User",
        })

        # Must redirect to the login page
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])

    # ------------------------------------------------------------------
    # Duplicate username
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")
    def test_register_duplicate_username(self, mock_get_db):
        """
        When the submitted user_id already exists in the DB, register()
        must re-render the registration form (HTTP 200) with an error that
        communicates the conflict.  The INSERT must NOT be executed.
        connect_conn.fetchone returns a truthy row → duplicate detected →
        form re-rendered with 'already exists' error.
        """
        engine, connect_conn, _ = _build_engine()
        connect_conn.execute.return_value.fetchone.return_value = MagicMock()  # duplicate
        mock_get_db.return_value = engine

        response = self.client.post("/auth/register", data={
            "user_id": "existinguser",
            "password": "somepassword",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already exists", response.data)

    # ------------------------------------------------------------------
    # Missing required fields — no DB mock needed
    # ------------------------------------------------------------------
    def test_register_missing_fields(self):
        """
        When user_id or password is absent, register() must return 200
        and re-render the form with a validation error before touching
        the database at all.  No get_db patch is needed: the guard fires
        before get_db() is called, and no session means before_request
        also skips the DB.
        Tested for both missing-password and missing-user_id cases.
        """
        # Case 1: password missing
        resp = self.client.post("/auth/register", data={"user_id": "someone"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"required", resp.data)

        # Case 2: user_id missing
        resp = self.client.post("/auth/register", data={"password": "pw123"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"required", resp.data)


# ===========================================================================
# POST /auth/login
# ===========================================================================
class TestLogin(unittest.TestCase):
    """Tests for POST /auth/login."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)

    def setUp(self):
        with self.app.app_context():
            cache.clear()
        self.client = self.app.test_client()

    # ------------------------------------------------------------------
    # Correct credentials — full hash round-trip
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")
    def test_login_correct_credentials(self, mock_get_db):
        """
        When a valid user_id and matching password are submitted, login()
        must redirect to the home page (302) and set session['user_id'].
        A real generate_password_hash / check_password_hash round-trip is
        used so the actual Werkzeug authentication path is exercised.
        No session exists before the request, so before_request is a no-op
        and only the route's own engine.connect() call needs mocking.
        """
        engine, connect_conn, _ = _build_engine()
        connect_conn.execute.return_value.fetchone.return_value = _login_row(TEST_PASSWORD)
        mock_get_db.return_value = engine

        with self.client as c:
            response = c.post("/auth/login", data={
                "user_id": TEST_USER_ID,
                "password": TEST_PASSWORD,
            })

            self.assertEqual(response.status_code, 302)
            with c.session_transaction() as sess:
                self.assertEqual(sess.get("user_id"), TEST_USER_ID)

    # ------------------------------------------------------------------
    # Wrong password
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")
    def test_login_wrong_password(self, mock_get_db):
        """
        When the user exists but the submitted password does not match the
        stored hash, login() must return 200 and render the login form with
        'Invalid credentials'.  session['user_id'] must NOT be set.
        The row mock holds a hash of a *different* password so
        check_password_hash returns False for the submitted value.
        """
        engine, connect_conn, _ = _build_engine()
        connect_conn.execute.return_value.fetchone.return_value = _login_row("different_password")
        mock_get_db.return_value = engine

        with self.client as c:
            response = c.post("/auth/login", data={
                "user_id": TEST_USER_ID,
                "password": "wrongpassword",
            })

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Invalid credentials", response.data)
            with c.session_transaction() as sess:
                self.assertNotIn("user_id", sess)

    # ------------------------------------------------------------------
    # Non-existent user
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")
    def test_login_nonexistent_user(self, mock_get_db):
        """
        When the submitted user_id is not found in the DB (fetchone → None),
        login() must return 200 with 'Invalid credentials'.
        The same error message is used for both wrong-password and unknown-
        user cases to prevent username enumeration attacks.
        """
        engine, connect_conn, _ = _build_engine()
        connect_conn.execute.return_value.fetchone.return_value = None  # user not found
        mock_get_db.return_value = engine

        response = self.client.post("/auth/login", data={
            "user_id": "nobody",
            "password": "anypassword",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid credentials", response.data)


# ===========================================================================
# GET /auth/logout
# ===========================================================================
class TestLogout(unittest.TestCase):
    """Tests for GET /auth/logout."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)

    def setUp(self):
        with self.app.app_context():
            cache.clear()
        self.client = self.app.test_client()

    @patch("app.routes.auth.get_db")
    def test_logout_clears_session(self, mock_get_db):
        """
        When a logged-in user hits /auth/logout, the route must pop
        'user_id' from the session and redirect to the home page (302).
        Because session['user_id'] is present, before_request fires and
        calls engine.connect() → connect_conn.fetchone() to load g.user,
        so the engine mock must return a valid user row for that query.
        After the redirect the session must contain no 'user_id'.
        """
        engine, connect_conn, _ = _build_engine()
        # before_request calls connect_conn to load the user into g.user
        connect_conn.execute.return_value.fetchone.return_value = _user_row()
        mock_get_db.return_value = engine

        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = TEST_USER_ID

            response = c.get("/auth/logout")

            self.assertEqual(response.status_code, 302)
            with c.session_transaction() as sess:
                self.assertNotIn("user_id", sess)


# ===========================================================================
# Favorites — POST, GET, DELETE /auth/favorites
# ===========================================================================
class TestFavorites(unittest.TestCase):
    """
    Tests for the favorites CRUD endpoints.  All tests inject a valid
    session so before_request populates g.user, which the route checks.

    Connect / begin split:
      before_request  → engine.connect() → connect_conn (fetchone for user row)
      add_favorite    → engine.begin()   → begin_conn   (fetchone for dup-check, then INSERT)
      get_favorites   → engine.connect() → connect_conn (fetchall for favorites list)
      delete_favorite → engine.begin()   → begin_conn   (rowcount for DELETE result)

    fetchone and fetchall are independent attributes on the same execute()
    return value, so both can be configured simultaneously on connect_conn.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestingConfig)

    def setUp(self):
        with self.app.app_context():
            cache.clear()
        self.client = self.app.test_client()

    def _set_session(self):
        """Inject a valid logged-in session into the test client."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = TEST_USER_ID

    # ------------------------------------------------------------------
    # POST /auth/favorites — add a new favorite
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")
    def test_add_favorite(self, mock_get_db):
        """
        When a logged-in user POSTs a valid station_number not yet in their
        favorites, add_favorite() must insert the record and return HTTP 201
        with a JSON success message.
        connect_conn.fetchone returns the user row for before_request.
        begin_conn.fetchone returns None for the duplicate-check, so the
        INSERT branch is taken and 201 is returned.
        """
        engine, connect_conn, begin_conn = _build_engine()
        connect_conn.execute.return_value.fetchone.return_value = _user_row()
        begin_conn.execute.return_value.fetchone.return_value = None  # not already favorited
        mock_get_db.return_value = engine

        self._set_session()
        response = self.client.post("/auth/favorites", data={"station_number": "42"})

        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIn("message", data)
        self.assertIn("Added", data["message"])

    # ------------------------------------------------------------------
    # POST /auth/favorites — station already in favorites
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")
    def test_add_favorite_already_exists(self, mock_get_db):
        """
        When the station is already in the user's favorites, add_favorite()
        must return HTTP 200 (not 201) with an informational message and
        must NOT attempt a second INSERT.
        begin_conn.fetchone returns a truthy row → duplicate detected.
        """
        engine, connect_conn, begin_conn = _build_engine()
        connect_conn.execute.return_value.fetchone.return_value = _user_row()
        begin_conn.execute.return_value.fetchone.return_value = MagicMock()  # already saved
        mock_get_db.return_value = engine

        self._set_session()
        response = self.client.post("/auth/favorites", data={"station_number": "42"})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("message", data)
        self.assertIn("already", data["message"])

    # ------------------------------------------------------------------
    # GET /auth/favorites — list favorites
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")
    def test_get_favorites(self, mock_get_db):
        """
        When a logged-in user GETs /auth/favorites, get_my_favorites() must
        return HTTP 200 with a JSON body containing 'user_id' and a
        'favorites' list.
        Both before_request (fetchone) and the route (fetchall) share
        connect_conn because both use engine.connect(); they call different
        methods so each is configured independently.
        FakeRow provides a real .items() so dict(row.items()) succeeds.
        """
        engine, connect_conn, _ = _build_engine()
        connect_conn.execute.return_value.fetchone.return_value = _user_row()
        connect_conn.execute.return_value.fetchall.return_value = [
            FakeRow({"favorite_id": 1, "station_number": 42, "added_at": "2024-01-10"}),
            FakeRow({"favorite_id": 2, "station_number": 7,  "added_at": "2024-01-11"}),
        ]
        mock_get_db.return_value = engine

        self._set_session()
        response = self.client.get("/auth/favorites")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("user_id", data)
        self.assertIn("favorites", data)
        self.assertEqual(data["user_id"], TEST_USER_ID)
        self.assertEqual(len(data["favorites"]), 2)
        self.assertEqual(data["favorites"][0]["station_number"], 42)
        self.assertEqual(data["favorites"][1]["station_number"], 7)

    # ------------------------------------------------------------------
    # DELETE /auth/favorites/<station_number> — valid station
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")
    def test_delete_favorite_valid(self, mock_get_db):
        """
        When a logged-in user deletes a station_number that exists in their
        favorites, delete_favorite() must execute the DELETE and return
        HTTP 200 with a JSON success message.
        begin_conn.execute().rowcount = 1 signals that a row was deleted.
        """
        engine, connect_conn, begin_conn = _build_engine()
        connect_conn.execute.return_value.fetchone.return_value = _user_row()
        begin_conn.execute.return_value.rowcount = 1  # one row matched and deleted
        mock_get_db.return_value = engine

        self._set_session()
        response = self.client.delete("/auth/favorites/42")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("message", data)

    # ------------------------------------------------------------------
    # DELETE /auth/favorites/<station_number> — station not in favorites
    # ------------------------------------------------------------------
    @patch("app.routes.auth.get_db")
    def test_delete_favorite_nonexistent(self, mock_get_db):
        """
        When the station_number is not in the user's favorites, the DELETE
        query matches zero rows (rowcount = 0) and delete_favorite() must
        return HTTP 404 with a JSON error message.
        This guards against silent no-ops masquerading as successful deletes.
        """
        engine, connect_conn, begin_conn = _build_engine()
        connect_conn.execute.return_value.fetchone.return_value = _user_row()
        begin_conn.execute.return_value.rowcount = 0  # nothing deleted → 404
        mock_get_db.return_value = engine

        self._set_session()
        response = self.client.delete("/auth/favorites/999")

        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn("error", data)

    # ------------------------------------------------------------------
    # Unauthenticated access — all favorites endpoints reject 401
    # ------------------------------------------------------------------
    def test_favorites_requires_login(self):
        """
        When no user is logged in (no session), all three favorites endpoints
        must return HTTP 401 and a JSON error.  No DB mock is needed because
        the g.user check fires before any get_db() call in the route, and
        before_request skips the DB entirely when there is no session.
        """
        # POST — add
        resp = self.client.post("/auth/favorites", data={"station_number": "1"})
        self.assertEqual(resp.status_code, 401)
        self.assertIn("error", resp.get_json())

        # GET — list
        resp = self.client.get("/auth/favorites")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("error", resp.get_json())

        # DELETE — remove
        resp = self.client.delete("/auth/favorites/1")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("error", resp.get_json())


if __name__ == "__main__":
    unittest.main()
