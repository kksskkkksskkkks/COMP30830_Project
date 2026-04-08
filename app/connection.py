from config import Config
from sqlalchemy import create_engine

_engine = None


def get_db():
    global _engine
    if _engine is None:
        connection_string = "mysql+pymysql://{}:{}@{}:{}/{}".format(
            Config.DB_USER, Config.DB_PASSWORD, Config.DB_URI, Config.DB_PORT, Config.DB_NAME
        )
        _engine = create_engine(
            connection_string,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
        )
    return _engine
