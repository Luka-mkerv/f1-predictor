from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

try:
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print("Database connection successful!")
except Exception as e:
    print(f"Connection failed: {e}")
