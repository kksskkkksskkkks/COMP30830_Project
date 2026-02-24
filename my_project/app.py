from flask import Flask

from blueprints.get_currrent_data_return_json import live_bp, cache
from blueprints.connection_to_db_return_json import db_bp

from blueprints.login import  login_bp


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



if __name__ == "__main__":
    print(" service lunched！Please visit following address in browser: ")
    print(" Homepage: http://127.0.0.1:5000/")
    print(" Real time weather API: http://127.0.0.1:5000/api/weather")
    print(" History DB data: http://127.0.0.1:5000/db/stations")
    # print(" Login Management: http://127.0.0.1:5000/auth/login")

    # run
    app.run(debug=True)
