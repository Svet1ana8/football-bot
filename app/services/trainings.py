from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import TIMEZONE
from app.repositories.trainings import (
    clear_training_responses,
    get_all_training_responses,
)
from app.repositories.users import get_users_by_status
from app.services.access import is_broadcast_recipient
from app.utils.dates import get_month_name_prepositional


async def send_payment_reminder_by_month_text(context: ContextTypes.DEFAULT_TYPE):
    approved_users = get_users_by_status("approved")
    month_name = get_month_name_prepositional(datetime.now(TIMEZONE))
    message_text = f"Напоминаю об оплате за тренировку в {month_name}."

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


async def send_training_reminder_text(context: ContextTypes.DEFAULT_TYPE):
    approved_users = get_users_by_status("approved")

    clear_training_responses()

    message_text = (
        "Сегодня тренировка в 21:00.\n"
        "Локация: https://2gis.kz/almaty/geo/9430098963876822/76.921711,43.237997\n"
        "Пожалуйста, ответь, придёшь ли ты."
    )

    keyboard = [[
        InlineKeyboardButton("✅ Приду", callback_data="training_yes"),
        InlineKeyboardButton("❌ Не приду", callback_data="training_no")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup
            )
            success_count += 1
        except Exception:
            fail_count += 1

    return success_count, fail_count


def build_training_responses_text():
    responses = get_all_training_responses()

    if not responses:
        return "Пока нет ответов на тренировку."

    coming = []
    not_coming = []

    for user_id, username, first_name, response in responses:
        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"

        if response == "yes":
            coming.append(name)
        elif response == "no":
            not_coming.append(name)

    text = "Ответы на тренировку:\n\n"
    text += "✅ Придут:\n"
    text += "\n".join(coming) if coming else "Пока никто"
    text += "\n\n"
    text += "❌ Не придут:\n"
    text += "\n".join(not_coming) if not_coming else "Пока никто"
    return text
