import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

TEAM_NAME = os.getenv("TEAM_NAME", "Алматы Фениксы")

TRAINING_TIME = os.getenv("TRAINING_TIME", "21:00")
TRAINING_VOTE_CLOSE_TIME = os.getenv("TRAINING_VOTE_CLOSE_TIME", "19:00")
TRAINING_REMINDER_REPEAT_MINUTES = int(os.getenv("TRAINING_REMINDER_REPEAT_MINUTES", "60"))
TRAINING_CONFIRM_BEFORE_HOURS = int(os.getenv("TRAINING_CONFIRM_BEFORE_HOURS", "3"))
TRAINING_LOCATION_URL = os.getenv(
    "TRAINING_LOCATION_URL",
    "https://2gis.kz/almaty/geo/9430098963876822/76.921711,43.237997",
)

DEFAULT_PAYMENT_DAY = int(os.getenv("DEFAULT_PAYMENT_DAY", "28"))
TRAININGS_PER_MONTH = int(os.getenv("TRAININGS_PER_MONTH", "12"))
SUBSCRIPTION_DURATION_DAYS = int(os.getenv("SUBSCRIPTION_DURATION_DAYS", "30"))
PAYMENT_REMINDER_REPEAT_MINUTES = int(os.getenv("PAYMENT_REMINDER_REPEAT_MINUTES", "60"))

SUBSCRIPTION_END_REMINDER_DAYS = int(os.getenv("SUBSCRIPTION_END_REMINDER_DAYS", "5"))
SUBSCRIPTION_END_REMINDER_TIME = os.getenv("SUBSCRIPTION_END_REMINDER_TIME", "10:00")

PENDING_REMINDER_TIMES = [
    item.strip()
    for item in os.getenv("PENDING_REMINDER_TIMES", "09:00,12:00,15:00,18:00").split(",")
    if item.strip()
]

TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Asia/Almaty"))

COACH_IDS = [
    item.strip()
    for item in os.getenv("COACH_IDS", "").split(",")
    if item.strip()
]