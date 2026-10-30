import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("NEBIUS_API_KEY")
BASE_URL = os.getenv("NEBIUS_BASE_URL")
TARGET_MODEL = os.getenv("NEBIUS_MODEL")

SELF_HOSTED_BASE_URL = os.getenv("SELF_HOSTED_BASE_URL", "")
SELF_HOSTED_MODEL = os.getenv("SELF_HOSTED_MODEL", "")

MAX_TOKENS = 256
NUM_REQUESTS = 20

if not API_KEY:
    raise RuntimeError("NEBIUS_API_KEY missing in .env")
if not BASE_URL:
    raise RuntimeError("NEBIUS_BASE_URL missing in .env")
if not TARGET_MODEL:
    raise RuntimeError("NEBIUS_MODEL missing in .env")