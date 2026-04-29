from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import TIMEZONE
from app.repositories.payments import (
    get_subscriptions_ending_soon_with_users,
    get_unpaid_subscriptions_with_users,
)
from app.services.access import is_broadcast_recipient
from app.utils.dates import get_month_name_prepositional


def get_payment_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💸 Оплатил", callback_data="payment_claimed")
    ]])


def plural_days(days: int) -> str:
    if days % 10 == 1 and days % 100 != 11:
        return "день"
    if days % 10 in [2, 3, 4] and days % 100 not in [12, 13, 14]:
        return "дня"
    return "дней"


def build_subscription_ending_message(first_name: str | None, days_left: int) -> str:
    name = first_name or "игрок"
    days_word = plural_days(days_left)

    return (
        f"Добрый день, {name}. "
        f"Напоминаем вам, что действие вашего абонемента заканчивается через {days_left} {days_word}."
    )


def build_payment_reminder_message() -> str:
    month_name = get_month_name_prepositional(datetime.now(TIMEZONE))
    return (
        f"Добрый вечер, у вас настало время оплатить за тренировки в {month_name}. "
        f"Прошу сделать это."
    )


async def send_subscription_ending_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TIMEZONE).date()
    subscriptions = get_subscriptions_ending_soon_with_users(today, days=5)

    if not subscriptions:
        print("Нет игроков с абонементом, который скоро заканчивается.")
        return

    sent_count = 0

    for user_id, username, first_name, payment_day, subscription_end_date, last_payment_date, is_paid_current_period, has_custom_schedule, payment_claimed in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        if not subscription_end_date:
            continue

        days_left = (subscription_end_date - today).days

        if days_left not in [1, 2, 3, 4, 5]:
            continue

        message_text = build_subscription_ending_message(first_name, days_left)

        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить напоминание игроку {user_id}: {e}")

    print(f"Отправлено напоминаний о скором окончании абонемента: {sent_count}")


async def send_unpaid_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TIMEZONE).date()
    subscriptions = get_unpaid_subscriptions_with_users(today)

    if not subscriptions:
        print("Нет игроков, которым нужно напоминание об оплате.")
        return

    sent_count = 0
    message_text = build_payment_reminder_message()
    reply_markup = get_payment_keyboard()

    for user_id, username, first_name, payment_day, subscription_end_date, last_payment_date, is_paid_current_period, has_custom_schedule, payment_claimed in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup
            )
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить напоминание об оплате игроку {user_id}: {e}")

    print(f"Отправлено напоминаний об оплате: {sent_count}")


async def send_manual_payment_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TIMEZONE).date()
    subscriptions = get_unpaid_subscriptions_with_users(today)

    if not subscriptions:
        return 0, 0

    success_count = 0
    fail_count = 0
    message_text = build_payment_reminder_message()
    reply_markup = get_payment_keyboard()

    for user_id, username, first_name, payment_day, subscription_end_date, last_payment_date, is_paid_current_period, has_custom_schedule, payment_claimed in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup
            )
            success_count += 1
        except Exception as e:
            print(f"Не удалось отправить ручное напоминание об оплате игроку {user_id}: {e}")
            fail_count += 1

    return success_count, fail_count


def schedule_daily_payment_jobs(application):
    existing_ending_jobs = application.job_queue.get_jobs_by_name("subscription_ending_reminders")
    if not existing_ending_jobs:
        application.job_queue.run_daily(
            send_subscription_ending_reminders,
            time=datetime.strptime("10:00", "%H:%M").time(),
            name="subscription_ending_reminders",
        )

    existing_unpaid_jobs = application.job_queue.get_jobs_by_name("unpaid_payment_reminders")
    if not existing_unpaid_jobs:
        application.job_queue.run_repeating(
            send_unpaid_reminders,
            interval=3600,  # 1 час
            first=3600,
            name="unpaid_payment_reminders",
        )