"""Local configuration and safe defaults for TalentIQ."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("TALENTIQ_DATA_DIR", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "talentiq.sqlite3"
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", 8 * 1024 * 1024))
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
