import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASSWORD")
PORT = os.getenv("DB_PORT")
DB = os.getenv("DB_NAME")
URI = os.getenv("DB_URI")

connection_string = "mysql+pymysql://{}:{}@{}:{}/{}".format(USER, PASSWORD, URI, PORT, DB)

engine = create_engine(connection_string, echo = True)

for res in engine.execute("SHOW VARIABLES;"):
    print(res)

# CREATE A USERS TABLE
sql = '''
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(25) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    preferred_language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id),

);
'''

# Execute the query
res = engine.execute(sql)

# Use the engine to execute the DESCRIBE command to inspect the table schema
tab_structure = engine.execute("SHOW COLUMNS FROM users;")

# Fetch and print the result to see the columns of the table
columns = tab_structure.fetchall()
print(columns)

# CREATE A USER_FAVORITE TABLE
sql = """
CREATE TABLE IF NOT EXISTS user_favorites (
    favorite_id INT AUTO_INCREMENT NOT NULL,
    user_id VARCHAR(25) NOT NULL,
    station_number INT NOT NULL, 
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (favorite_id),
    
    CONSTRAINT fk_user 
        FOREIGN KEY (user_id) 
        REFERENCES users(user_id) 
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    
    CONSTRAINT fk_station
        FOREIGN KEY (station_number)
        REFERENCES station(`number`)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    UNIQUE KEY unique_user_station (user_id, station_number)
);
"""

engine.execute(sql)