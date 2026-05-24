from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import (
    PAYMENT_REMINDER_REPEAT_MINUTES,
    SUBSCRIPTION_END_REMINDER_DAYS,
    TIMEZONE,
)
from app.repositories.payments import (
    get_overdue_subscription_end_with_users,
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
        f"Напоминаем вам, что действие вашего абонемента заканчивается через {days_left} {days_word}. "
        "Пожалуйста, не забудьте оплатить продление."
    )


def build_payment_reminder_message() -> str:
    month_name = get_month_name_prepositional(datetime.now(TIMEZONE))
    return (
        f"Добрый вечер. Напоминаем об оплате абонемента за {month_name}. "
        "Пожалуйста, произведите оплату."
    )


def build_subscription_overdue_message(first_name: str | None, overdue_days: int) -> str:
    name = first_name or "игрок"
    days_word = plural_days(overdue_days)

    return (
        f"Добрый день, {name}. Напоминаем, что срок действия вашего абонемента уже истёк. "
        f"Просрочка: {overdue_days} {days_word}. Пожалуйста, оплатите продление."
    )


def should_send_ending_reminder(days_left: int, now: datetime) -> bool:
    current_hm = now.strftime("%H:%M")

    schedule = {
        5: {"12:00"},
        4: {"12:00"},
        3: {"10:00", "15:00", "20:00"},
        2: {"09:00", "11:00", "13:00", "15:00", "18:00", "21:00"},
        1: {"09:00", "11:00", "13:00", "15:00", "18:00", "21:00"},
    }

    return current_hm in schedule.get(days_left, set())


async def send_subscription_ending_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TIMEZONE)
    today = now.date()

    subscriptions = get_subscriptions_ending_soon_with_users(
        today,
        days=SUBSCRIPTION_END_REMINDER_DAYS,
    )

    if not subscriptions:
        print("Нет игроков с абонементом, который скоро заканчивается.")
        return

    sent_count = 0

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        if not subscription_end_date:
            continue

        days_left = (subscription_end_date - today).days

        if days_left not in range(1, SUBSCRIPTION_END_REMINDER_DAYS + 1):
            continue

        if not should_send_ending_reminder(days_left, now):
            continue

        message_text = build_subscription_ending_message(first_name, days_left)

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=get_payment_keyboard()
            )
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить напоминание игроку {user_id}: {e}")

    print(f"Отправлено напоминаний о скором окончании абонемента: {sent_count}")


async def send_subscription_overdue_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TIMEZONE).date()
    subscriptions = get_overdue_subscription_end_with_users(today)

    if not subscriptions:
        print("Нет игроков с просроченным окончанием абонемента.")
        return

    sent_count = 0
    reply_markup = get_payment_keyboard()

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        if not subscription_end_date:
            continue

        overdue_days = (today - subscription_end_date).days

        if overdue_days <= 0:
            continue

        message_text = build_subscription_overdue_message(first_name, overdue_days)

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup
            )
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить напоминание о просрочке абонемента игроку {user_id}: {e}")

    print(f"Отправлено напоминаний о просроченном окончании абонемента: {sent_count}")


async def send_unpaid_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TIMEZONE).date()
    subscriptions = get_unpaid_subscriptions_with_users(today)

    if not subscriptions:
        print("Нет игроков с просроченной оплатой.")
        return

    sent_count = 0
    reply_markup = get_payment_keyboard()

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        overdue_days = today.day - payment_day

        if overdue_days <= 0:
            continue

        message_text = build_payment_reminder_message()

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

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
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
        application.job_queue.run_repeating(
            send_subscription_ending_reminders,
            interval=60 * 60,
            first=10,
            name="subscription_ending_reminders",
        )

    existing_overdue_jobs = application.job_queue.get_jobs_by_name("subscription_overdue_reminders")
    if not existing_overdue_jobs:
        application.job_queue.run_repeating(
            send_subscription_overdue_reminders,
            interval=PAYMENT_REMINDER_REPEAT_MINUTES * 60,
            first=10,
            name="subscription_overdue_reminders",
        )

    existing_unpaid_jobs = application.job_queue.get_jobs_by_name("unpaid_payment_reminders")
    if not existing_unpaid_jobs:
        application.job_queue.run_repeating(
            send_unpaid_reminders,
            interval=PAYMENT_REMINDER_REPEAT_MINUTES * 60,
            first=10,
            name="unpaid_payment_reminders",
        )