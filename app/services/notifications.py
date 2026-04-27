from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import COACH_IDS
from app.repositories.users import get_user_by_id


async def notify_coaches_about_request(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if not COACH_IDS:
        return

    existing_user = get_user_by_id(user_id)
    if not existing_user:
        return

    request_user_id, username, first_name, status = existing_user

    text = "Новая заявка\n\n"
    text += f"ID: {request_user_id}"
    if first_name:
        text += f"\nИмя: {first_name}"
    if username:
        text += f"\nusername: @{username}"
    text += f"\nСтатус: {status}"

    keyboard = [[
        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{request_user_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_user_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for coach_id in COACH_IDS:
        try:
            await context.bot.send_message(
                chat_id=int(coach_id),
                text=text,
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Не удалось отправить заявку тренеру {coach_id}: {e}")
