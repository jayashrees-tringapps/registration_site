import os
import psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"), dbname=os.getenv("DB_NAME"))
cur = conn.cursor()
cur.execute("SELECT id, file_name, file_data FROM media")
os.makedirs("exported_files", exist_ok=True)
for file_id, file_name, file_data in cur.fetchall():
    path = os.path.join("exported_files", str(file_id) + "_" + os.path.basename(file_name))
    with open(path, "wb") as f:
        f.write(file_data)
    print("saved", path)
conn.close()