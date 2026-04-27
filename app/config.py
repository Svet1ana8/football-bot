import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
COACH_IDS = {x.strip() for x in os.getenv("COACH_IDS", "").split(",") if x.strip()}
DATABASE_URL = os.getenv("DATABASE_URL")
TIMEZONE = ZoneInfo("Asia/Almaty")
