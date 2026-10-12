import os
from urllib.parse import quote_plus
import reflex as rx
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("REFLEX_DB_URL") or os.getenv("DATABASE_URL")
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
else:
    user = os.getenv("DB_USER")
    password = quote_plus(os.getenv("DB_PASSWORD"))
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    name = os.getenv("DB_NAME")
    db_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"

config = rx.Config(app_name="registration_site", db_url=db_url)