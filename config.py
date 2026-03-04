import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""
    JCKEY = os.getenv("JCKEY")
    OWKEY = os.getenv("OWKEY")
    CURRENT_URI = os.getenv("CURRENT_URI")
    GMKEY = os.getenv("GMKEY")

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