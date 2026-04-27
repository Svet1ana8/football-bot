from datetime import datetime

from telegram.ext import ContextTypes

from app.config import TIMEZONE
from app.repositories.payments import get_subscriptions_ending_soon_with_users
from app.services.access import is_broadcast_recipient


def build_subscription_ending_message(first_name: str | None, days_left: int) -> str:
    name = first_name or "игрок"

    if days_left == 1:
        return (
            f"Добрый день, {name}. "
            f"Напоминаем вам, что действие вашего абонемента заканчивается через 1 день."
        )

    return (
        f"Добрый день, {name}. "
        f"Напоминаем вам, что действие вашего абонемента заканчивается через {days_left} дней."
    )


async def send_subscription_ending_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TIMEZONE).date()
    subscriptions = get_subscriptions_ending_soon_with_users(today, days=5)

    if not subscriptions:
        print("Нет игроков с абонементом, который скоро заканчивается.")
        return

    sent_count = 0

    for user_id, username, first_name, payment_day, subscription_end_date, last_payment_date, is_paid_current_period, has_custom_schedule in subscriptions:
        if not is_broadcast_recipient(user_id):
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


def schedule_daily_payment_jobs(application):
    existing_jobs = application.job_queue.get_jobs_by_name("subscription_ending_reminders")
    if existing_jobs:
        return

    application.job_queue.run_daily(
        send_subscription_ending_reminders,
        time=datetime.strptime("10:00", "%H:%M").time(),
        name="subscription_ending_reminders",
    )