import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASSWORD")
PORT = os.getenv("DB_PORT")
DB = os.getenv("DB_NAME")
URI = os.getenv("DB_URI")

connection_string = "mysql+pymysql://{}:{}@{}:{}/{}".format(USER, PASSWORD, URI, PORT, DB)
engine = create_engine(connection_string, echo=False)


def run_sql():
    try:
        with engine.begin() as conn:
            # 1. Create USERS table
            print("Creating users table...")
            sql_users = """
                        CREATE TABLE IF NOT EXISTS users \
                        ( \
                            user_id \
                            VARCHAR \
                        ( \
                            25 \
                        ) NOT NULL,
                            full_name VARCHAR \
                        ( \
                            100 \
                        ) NOT NULL,
                            password_hash VARCHAR \
                        ( \
                            255 \
                        ) NOT NULL,
                            preferred_language VARCHAR \
                        ( \
                            10 \
                        ) DEFAULT 'en',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY \
                        ( \
                            user_id \
                        )
                            ); \
                        """
            conn.execute(text(sql_users))
            print("Users table checked/created.")

            # 2. Check if station table exists (requirement for foreign key)
            print("Checking for station table...")
            check_station = conn.execute(text("SHOW TABLES LIKE 'station'")).fetchone()
            if not check_station:
                print(" ERROR: table 'station' does not exist. Please run bike_table_create.py first!")
                return

            # 3. Create USER_FAVORITES table
            print("Creating user_favorites table...")
            sql_favorites = """
                            CREATE TABLE IF NOT EXISTS user_favorites \
                            ( \
                                favorite_id \
                                INT \
                                AUTO_INCREMENT \
                                NOT \
                                NULL, \
                                user_id \
                                VARCHAR \
                            ( \
                                25 \
                            ) NOT NULL,
                                station_number INT NOT NULL,
                                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                PRIMARY KEY \
                            ( \
                                favorite_id \
                            ), \
                                CONSTRAINT fk_user
                                FOREIGN KEY \
                            ( \
                                user_id \
                            )
                                REFERENCES users \
                            ( \
                                user_id \
                            )
                                ON UPDATE CASCADE
                                ON DELETE CASCADE, \
                                CONSTRAINT fk_station
                                FOREIGN KEY \
                            ( \
                                station_number \
                            )
                                REFERENCES station \
                            ( \
                                `number` \
                            )
                                ON UPDATE CASCADE
                                ON DELETE CASCADE,
                                UNIQUE KEY unique_user_station \
                            ( \
                                user_id, \
                                station_number \
                            )
                                ); \
                            """
            conn.execute(text(sql_favorites))
            print("User_favorites table checked/created.")

            # Verify tables
            tables = conn.execute(text("SHOW TABLES")).fetchall()
            print("\nCurrent tables in database:")
            for t in tables:
                print(f" - {t[0]}")

    except SQLAlchemyError as e:
        print(f" Database error: {e}")
    except Exception as e:
        print(f" Error: {e}")


if __name__ == "__main__":
    run_sql()