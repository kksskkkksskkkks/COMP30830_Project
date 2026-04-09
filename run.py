from dotenv import load_dotenv
load_dotenv()

from app import create_app
from config import DevelopmentConfig

app = create_app(DevelopmentConfig)

if __name__ == "__main__":
    
    print(" Service launched! Please visit following address in browser: ")
    print(" Homepage: http://127.0.0.1:5000/")
    print(" Real time weather API: http://127.0.0.1:5000/api/weather")
    print(" History DB data: http://127.0.0.1:5000/db/stations")

    # run
    app.run()