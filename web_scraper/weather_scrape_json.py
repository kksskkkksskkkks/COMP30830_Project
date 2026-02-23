
import requests
import traceback
import datetime
import time
import os

from dotenv import load_dotenv

load_dotenv()

KEY = os.getenv("OWKEY")
CURRENT_URI = os.getenv("CURRENT_URI")


# Will be used to store text in a file
def write_to_file(text):
   
    # I first need to create a folder data where the files will be stored.
    if not os.path.exists('data'):
        os.mkdir('data')
        print("Folder 'data' created!")
    else:
        print("Folder 'data' already exists.")

    # now is a variable from datetime, which will go in {}.
    # replace is replacing white spaces with underscores in the file names
    now = datetime.datetime.now()
    with open("helpers/data/weather_{}".format(now).replace(" ", "_"), "w") as f:
        f.write(text)

# Empty for now
def write_to_db(text):
    return 0

def main():
    try:
        r = requests.get(CURRENT_URI, params={"appid": KEY, "q": "dublin, ie"})
        print(r)
        write_to_file(r.text)
    except:
        print(traceback.format_exc())

main() 