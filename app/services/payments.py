from datetime import datetime, time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import (
    SUBSCRIPTION_END_REMINDER_DAYS,
    TIMEZONE,
)
from app.repositories.payments import (
    get_overdue_subscription_end_with_users,
    get_payment_due_today_with_users,
    get_subscriptions_ending_soon_with_users,
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
        f"Добрый вечер. Напоминаем об оплате абонемента в {month_name}. "
        "Пожалуйста, произведите оплату."
    )


def build_subscription_overdue_message(first_name: str | None, overdue_days: int) -> str:
    name = first_name or "игрок"
    days_word = plural_days(overdue_days)

    return (
        f"Добрый день, {name}. Напоминаем, что срок действия вашего абонемента уже истёк. "
        f"Просрочка: {overdue_days} {days_word}. Пожалуйста, оплатите продление."
    )


async def send_subscription_ending_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TIMEZONE)
    today = now.date()

    days_set = context.job.data["days"]
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
        if days_left not in days_set:
            continue

        message_text = build_subscription_ending_message(first_name, days_left)

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=get_payment_keyboard(),
            )
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить напоминание игроку {user_id}: {e}")

    print(
        f"Отправлено напоминаний о скором окончании абонемента: {sent_count}. "
        f"Дни: {sorted(days_set)}"
    )


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
                reply_markup=reply_markup,
            )
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить напоминание о просрочке абонемента игроку {user_id}: {e}")

    print(f"Отправлено напоминаний о просроченном окончании абонемента: {sent_count}")


async def send_manual_payment_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TIMEZONE).date()
    subscriptions = get_payment_due_today_with_users(today)

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
                reply_markup=reply_markup,
            )
            success_count += 1
        except Exception as e:
            print(f"Не удалось отправить ручное напоминание об оплате игроку {user_id}: {e}")
            fail_count += 1

    return success_count, fail_count


def schedule_daily_payment_jobs(application):
    reminder_schedule = [
        # За 5 и 4 дня — 2 раза в день
        ("subscription_end_reminders_5d_09", time(9, 0, tzinfo=TIMEZONE), {5}),
        ("subscription_end_reminders_5d_23", time(23, 0, tzinfo=TIMEZONE), {5}),
        ("subscription_end_reminders_4d_09", time(9, 0, tzinfo=TIMEZONE), {4}),
        ("subscription_end_reminders_4d_23", time(23, 0, tzinfo=TIMEZONE), {4}),

        # За 3 и 2 дня — 3 раза в день
        ("subscription_end_reminders_3d_09", time(9, 0, tzinfo=TIMEZONE), {3}),
        ("subscription_end_reminders_3d_14", time(14, 0, tzinfo=TIMEZONE), {3}),
        ("subscription_end_reminders_3d_20", time(20, 0, tzinfo=TIMEZONE), {3}),
        ("subscription_end_reminders_2d_09", time(9, 0, tzinfo=TIMEZONE), {2}),
        ("subscription_end_reminders_2d_14", time(14, 0, tzinfo=TIMEZONE), {2}),
        ("subscription_end_reminders_2d_20", time(20, 0, tzinfo=TIMEZONE), {2}),

        # За 1 день — 6 раз в день
        ("subscription_end_reminders_1d_09", time(9, 0, tzinfo=TIMEZONE), {1}),
        ("subscription_end_reminders_1d_11", time(11, 0, tzinfo=TIMEZONE), {1}),
        ("subscription_end_reminders_1d_14", time(14, 0, tzinfo=TIMEZONE), {1}),
        ("subscription_end_reminders_1d_18", time(18, 0, tzinfo=TIMEZONE), {1}),
        ("subscription_end_reminders_1d_20", time(20, 0, tzinfo=TIMEZONE), {1}),
        ("subscription_end_reminders_1d_23_30", time(23, 30, tzinfo=TIMEZONE), {1}),
    ]

    for job_name, job_time, job_days in reminder_schedule:
        existing_jobs = application.job_queue.get_jobs_by_name(job_name)
        if existing_jobs:
            continue

        application.job_queue.run_daily(
            send_subscription_ending_reminders,
            time=job_time,
            data={"days": job_days},
            name=job_name,
        )

    existing_overdue_jobs = application.job_queue.get_jobs_by_name("subscription_overdue_reminders")
    if not existing_overdue_jobs:
        application.job_queue.run_daily(
            send_subscription_overdue_reminders,
            time=time(12, 30, tzinfo=TIMEZONE),
            name="subscription_overdue_reminders",
        )

    for job_name, job_time, job_days in reminder_schedule:
        existing_jobs = application.job_queue.get_jobs_by_name(job_name)
        if existing_jobs:
            continue

        application.job_queue.run_daily(
            send_subscription_ending_reminders,
            time=job_time,
            data={"days": job_days},
            name=job_name,
        )

    # Просрочка — 1 раз в день
    existing_overdue_jobs = application.job_queue.get_jobs_by_name("subscription_overdue_reminders")
    if not existing_overdue_jobs:
        application.job_queue.run_daily(
            send_subscription_overdue_reminders,
            time=time(12, 30, tzinfo=TIMEZONE),
            name="subscription_overdue_reminders",
        )