from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("LINGUAWALK_DB_PATH", str(DATA_DIR / "linguawalk.db")))
SCHEMA_PATH = BASE_DIR / "schema.sql"

API_KEY = os.getenv("LINGUAWALK_API_KEY", "change-me-before-public-use")
