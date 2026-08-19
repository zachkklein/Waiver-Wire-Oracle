import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "db.sqlite")
CHROMA_PATH = os.path.join(BASE_DIR, "data", "chroma")

ESPN_LEAGUE_ID = os.getenv("ESPN_LEAGUE_ID")
ESPN_SEASON = os.getenv("ESPN_SEASON")
ESPN_SWID = os.getenv("ESPN_SWID")
ESPN_S2 = os.getenv("ESPN_S2")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.7-flash")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

RSS_FEED_URLS = [
    url.strip()
    for url in os.getenv("RSS_FEED_URLS", "").split(",")
    if url.strip()
]
