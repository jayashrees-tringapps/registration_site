import os 
from urllib.parse import quote_plus
import reflex as rx 
from dotenv import load_dotenv
load_dotenv()

user = os.getenv("DB_USER")
password = quote_plus(os.getenv("DB_PASSWORD"))
host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT")
name = os.getenv("DB_NAME")
config = rx.Config(app_name="registration_site",db_url=f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}")