from flask import Flask

from my_project.app.main import cache
from my_project.app.main.routes import live_bp, db_bp
# from my_project.app.main.get_currrent_data_return_json import live_bp, cache
# from my_project.app.main.connection_to_db_return_json import db_bp
from my_project.config import Config


def create_app(config_class=Config):
    app = Flask(__name__, static_url_path='')

    # cache
    cache.init_app(app, config={'CACHE_TYPE': 'SimpleCache'})

    # app.secret_key = 'your_super_secret_key'

    # register blueprint
    #  http://127.0.0.1:5000/  index.html

    app.register_blueprint(live_bp)

    app.register_blueprint(db_bp, url_prefix='/db')

    # app.register_blueprint(login_bp, url_prefix='/auth')
    # http://127.0.0.1:5000/auth/login

    return app
