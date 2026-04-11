import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""
    BIKE_KEY = os.getenv("BIKE_KEY")
    WEATHER_KEY = os.getenv("WEATHER_KEY")
    MAP_KEY = os.getenv("MAP_KEY")
    MAP_ID  = os.getenv("MAP_ID")

    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_URI = os.getenv("DB_URI")

    # i18n
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_TRANSLATION_DIRECTORIES = 'translations'
    LANGUAGES = ['en', 'fr', 'it', 'zh_TW', 'zh_CN', 'ja']

    # General
    DEBUG = False
    TESTING = False

    # Cookie
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True


class ProductionConfig(Config):

    SECRET_KEY = os.environ.get("SECRET_KEY")
    DEBUG = False