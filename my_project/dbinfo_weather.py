import os

# for latitude & longitude, use another API call to get
CODE = "dublin, IE"
LIMIT = "1"
LAT_LON_API = "http://api.openweathermap.org/geo/1.0/direct"

# then get proper data
WEATHERKEY = os.getenv("OW_KEY")
UNITS = "metric"
LAT = "xxx"
LON = "yyy"
WEATHERAPI = "https://api.openweathermap.org/data/3.0/onecall"
EXCLUDE = "minutely,hourly,daily,alerts" # can be current, minutely, hourly, daily, alerts