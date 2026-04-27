from datetime import datetime, time, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import TIMEZONE
from app.repositories.trainings import (
    create_training,
    deactivate_training,
    get_active_training,
    get_training_responses,
    get_user_response_for_training,
    save_training_response,
    update_training_last_reminder,
)
from app.repositories.users import get_users_by_status
from app.services.access import is_broadcast_recipient
from app.utils.dates import get_month_name_prepositional


def build_training_message() -> str:
    return (
        "Сегодня тренировка в 21:00.\n"
        "Локация: https://2gis.kz/almaty/geo/9430098963876822/76.921711,43.237997\n"
        "Пожалуйста, ответь, придёшь ли ты."
    )


def get_training_keyboard(training_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Приду", callback_data=f"training_yes_{training_id}"),
        InlineKeyboardButton("❌ Не приду", callback_data=f"training_no_{training_id}")
    ]])


def get_today_stop_at() -> datetime:
    now = datetime.now(TIMEZONE)
    return datetime.combine(now.date(), time(19, 0), tzinfo=TIMEZONE)


async def send_payment_reminder_by_month_text(context: ContextTypes.DEFAULT_TYPE):
    approved_users = get_users_by_status("approved")
    month_name = get_month_name_prepositional(datetime.now(TIMEZONE))
    message_text = (
        f"Добрый вечер, у вас настало время оплатить за тренировки в {month_name}. "
        f"Прошу сделать это."
    )

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except Exception:
            fail_count += 1

    return message_text, success_count, fail_count


async def start_training_reminder(context: ContextTypes.DEFAULT_TYPE):
    active_training = get_active_training()
    now = datetime.now(TIMEZONE)

    if active_training:
        training_id, message_text, start_time, last_reminder_time, stop_at, is_active = active_training
        if stop_at > now:
            return None

    message_text = build_training_message()
    stop_at = get_today_stop_at()

    training_id = create_training(
        message_text=message_text,
        start_time=now,
        stop_at=stop_at,
    )

    approved_users = get_users_by_status("approved")
    keyboard = get_training_keyboard(training_id)

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard,
            )
            success_count += 1
        except Exception:
            fail_count += 1

    return {
        "training_id": training_id,
        "success_count": success_count,
        "fail_count": fail_count,
        "stop_at": stop_at,
    }


async def repeat_training_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    active_training = get_active_training()
    if not active_training:
        return

    training_id, message_text, start_time, last_reminder_time, stop_at, is_active = active_training
    now = datetime.now(TIMEZONE)

    if now >= stop_at:
        deactivate_training(training_id)
        print(f"Training #{training_id} stopped: reached stop time.")
        return

    approved_users = get_users_by_status("approved")
    keyboard = get_training_keyboard(training_id)

    sent_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        existing_response = get_user_response_for_training(training_id, user_id)
        if existing_response:
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard,
            )
            sent_count += 1
        except Exception as e:
            print(f"Ошибка повторной отправки игроку {user_id}: {e}")

    update_training_last_reminder(training_id, now)
    print(f"Training #{training_id}: repeated reminder sent to {sent_count} players.")


def save_player_training_response(training_id: int, user_id: int, username: str | None, first_name: str | None, response: str):
    save_training_response(
        training_id=training_id,
        user_id=user_id,
        username=username,
        first_name=first_name,
        response=response,
    )


def build_training_responses_text():
    active_training = get_active_training()
    if not active_training:
        return "Сейчас нет активной тренировки."

    training_id, message_text, start_time, last_reminder_time, stop_at, is_active = active_training

    approved_users = [
        row for row in get_users_by_status("approved")
        if is_broadcast_recipient(row[0])
    ]
    responses = get_training_responses(training_id)

    response_map = {user_id: response for user_id, username, first_name, response in responses}

    coming = []
    not_coming = []
    no_response = []

    for user_id, username, first_name in approved_users:
        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"

        response = response_map.get(user_id)
        if response == "yes":
            coming.append(name)
        elif response == "no":
            not_coming.append(name)
        else:
            no_response.append(name)

    text = "Ответы на тренировку:\n\n"

    text += "✅ Придут:\n"
    text += "\n".join(coming) if coming else "Пока никто"
    text += "\n\n"

    text += "❌ Не придут:\n"
    text += "\n".join(not_coming) if not_coming else "Пока никто"
    text += "\n\n"

    text += "⏳ Не ответили:\n"
    text += "\n".join(no_response) if no_response else "Все ответили"

    return text


def schedule_training_repeat_job(application):
    existing_jobs = application.job_queue.get_jobs_by_name("training_repeat_job")
    if existing_jobs:
        return

    application.job_queue.run_repeating(
        repeat_training_reminder_job,
        interval=timedelta(hours=1),
        first=timedelta(hours=1),
        name="training_repeat_job",
    )