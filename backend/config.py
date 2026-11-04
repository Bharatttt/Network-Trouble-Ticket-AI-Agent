import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)
MODEL = os.getenv('GEMINI_MODEL') or 'gemini-2.5-flash'
DATA_FILE = os.getenv('NOC_DATA_FILE', '')
DATABASE = os.getenv('NOC_DATABASE') or str(ROOT / 'runtime' / 'incidents.sqlite3')
