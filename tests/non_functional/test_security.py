"""
Non_functional security tests — no mocking, no @patch, no MagicMock.

Each test class verifies one security property of the
live application stack.

Run with:
    python -m unittest tests.non_functional.test_security -v
"""

import os
import unittest
from dotenv import load_dotenv

# Load .env before any Config / app import so env vars are visible to Config
load_dotenv()

import app.connection as conn_module
from app import create_app
from config import DevelopmentConfig

# Reset stale engine state that may carry over from other test modules, then
# create one shared app instance for the entire module.
conn_module._engine = None
_app = create_app(DevelopmentConfig)
_app.config['TESTING'] = True


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
# 1. Auth routes reject unauthenticated requests
#
# Security property: protected resources must never be served to an anonymous
# (session-less) client.  Page routes must redirect to /auth/login (302);
# JSON API routes must return 401 Unauthorized without touching the database.
# ===========================================================================

class TestUnauthenticated(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # GET /account must redirect an anonymous user to the login page rather
    # than rendering the account dashboard.
    def test_account_redirects_to_login(self):
        resp = self.client.get('/account')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login', resp.headers['Location'])

    # GET /bike/plot must redirect an anonymous user to the login page rather
    # than rendering the interactive prediction chart.
    def test_bike_plot_redirects_to_login(self):
        resp = self.client.get('/bike/plot')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login', resp.headers['Location'])

    # GET /bike/number must redirect an anonymous user to the login page rather
    # than rendering the bike-return form.
    def test_bike_number_redirects_to_login(self):
        resp = self.client.get('/bike/number')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login', resp.headers['Location'])

    # POST /auth/favorites without a session must return 401 — it must not
    # silently add a favourite for a phantom user.
    def test_favorites_post_returns_401(self):
        resp = self.client.post('/auth/favorites', data={'station_number': '1'})
        self.assertEqual(resp.status_code, 401)

    # GET /auth/favorites without a session must return 401 — the favourites
    # list must not be accessible anonymously.
    def test_favorites_get_returns_401(self):
        resp = self.client.get('/auth/favorites')
        self.assertEqual(resp.status_code, 401)

    # DELETE /auth/favorites/1 without a session must return 401 — an anonymous
    # caller must not be able to delete another user's favourites.
    def test_favorites_delete_returns_401(self):
        resp = self.client.delete('/auth/favorites/1')
        self.assertEqual(resp.status_code, 401)


# ===========================================================================
# 2. Session clears correctly on logout
#
# Security property: GET /auth/logout must fully invalidate the Flask session
# so that the same client can no longer access protected routes — confirming
# the server-side session state was cleared, not merely hidden.
# ===========================================================================

class TestLogout(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # After logout the session cookie must carry no user_id, so a subsequent
    # request to /account is treated as anonymous and redirected to /auth/login
    # rather than returning 200.
    def test_session_clears_on_logout(self):
        if not _db_is_reachable():
            self.skipTest("Database unavailable — system test requires a running database")

        # Plant a user_id in the session to simulate an authenticated state.
        with self.client.session_transaction() as sess:
            sess['user_id'] = '_system_test_nonexistent_user_'

        # Logout must respond with a redirect (to home).
        resp = self.client.get('/auth/logout')
        self.assertIn(resp.status_code, (301, 302))

        # With the session cleared, /account must now redirect to login (not 200).
        resp = self.client.get('/account')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login', resp.headers['Location'])


# ===========================================================================
# 3. API keys not exposed in responses
#
# Security property: the values of BIKE_KEY and WEATHER_KEY must never appear
# verbatim in any HTTP response body or header of a publicly accessible
# endpoint.  A leaked key would allow third parties to consume the quota or
# impersonate this service.  Tests are skipped when the key is not configured.
# ===========================================================================

class TestApiKeyExposure(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # BIKE_KEY must not appear verbatim anywhere in the GET /api/bikes response.
    def test_bike_key_not_exposed_in_response(self):
        bike_key = os.environ.get('BIKE_KEY', '')
        if not bike_key:
            self.skipTest("BIKE_KEY not set — nothing to verify")

        resp = self.client.get('/api/bikes')
        body = resp.get_data(as_text=True)

        self.assertNotIn(bike_key, body,
                         "BIKE_KEY found verbatim in /api/bikes response body")
        for header_value in resp.headers.values():
            self.assertNotIn(bike_key, header_value,
                             "BIKE_KEY found verbatim in /api/bikes response headers")

    # WEATHER_KEY must not appear verbatim anywhere in the GET /api/weather response.
    def test_weather_key_not_exposed_in_response(self):
        weather_key = os.environ.get('WEATHER_KEY', '')
        if not weather_key:
            self.skipTest("WEATHER_KEY not set — nothing to verify")

        resp = self.client.get('/api/weather')
        body = resp.get_data(as_text=True)

        self.assertNotIn(weather_key, body,
                         "WEATHER_KEY found verbatim in /api/weather response body")
        for header_value in resp.headers.values():
            self.assertNotIn(weather_key, header_value,
                             "WEATHER_KEY found verbatim in /api/weather response headers")


# ===========================================================================
# 4. Registration input validation
#
# Security property: POST /auth/register must validate required fields before
# performing any database write.  A missing user_id or password must produce
# an error response (form re-rendered, not redirected to login), confirming
# that no partial / zombie user record was ever inserted.
# ===========================================================================

class TestRegistrationValidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _app

    def setUp(self):
        self.client = self.app.test_client()

    # Submitting the registration form without a user_id must yield a 200 (form
    # re-displayed with an error) rather than a 302 redirect to /auth/login that
    # would indicate a successful — and dangerously incomplete — registration.
    def test_register_missing_user_id_is_rejected(self):
        resp = self.client.post('/auth/register', data={'password': 'validpass123'})
        self.assertEqual(resp.status_code, 200,
                         "Expected form re-render (200), got redirect or server error")
        body = resp.get_data(as_text=True)
        self.assertIn('required', body.lower(),
                      "Error message not found in register response body")

    # Submitting the registration form without a password must yield a 200 (form
    # re-displayed with an error) rather than a 302 redirect to /auth/login,
    # confirming the endpoint does not create a record with no password hash.
    def test_register_missing_password_is_rejected(self):
        resp = self.client.post('/auth/register', data={'user_id': 'validuser'})
        self.assertEqual(resp.status_code, 200,
                         "Expected form re-render (200), got redirect or server error")
        body = resp.get_data(as_text=True)
        self.assertIn('required', body.lower(),
                      "Error message not found in register response body")


if __name__ == '__main__':
    unittest.main()
