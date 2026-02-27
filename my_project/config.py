import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    # General
    DEBUG = False
    TESTING = False




class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True


class ProductionConfig(Config):
    # Never hardcode secrets in production
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DEBUG = False