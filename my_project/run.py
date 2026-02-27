
from config import DevelopmentConfig
from app import create_app

app = create_app(DevelopmentConfig)

if __name__ == "__main__":
    print(" service lunched！Please visit following address in browser: ")
    print(" Homepage: http://127.0.0.1:5000/")
    print(" Real time weather API: http://127.0.0.1:5000/api/weather")
    print(" History DB data: http://127.0.0.1:5000/db/stations")
    # print(" Login Management: http://127.0.0.1:5000/auth/login")

    # run
    app.run()