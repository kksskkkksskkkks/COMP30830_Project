"""
This file should ONLY contain "create_app" function
"""
from flask import Flask

## from my_project.app.main import cache
## from my_project.app.main.routes import live_bp, db_bp
# from my_project.app.main.get_currrent_data_return_json import live_bp, cache
# from my_project.app.main.connection_to_db_return_json import db_bp
from config import Config


def create_app(config_class=Config):
    ## app = Flask(__name__, static_url_path='')
    app = Flask(__name__)

    # Import blueprints and cache AFTER creating app but BEFORE using them
    from .routes.main import main_bp, cache
    from .routes.auth import auth_bp

    # cache
    cache.init_app(app, config={'CACHE_TYPE': 'SimpleCache'})

    # app.secret_key = 'your_super_secret_key'

    app.config.from_object(config_class)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    # http://127.0.0.1:5000/auth/login

    return app
