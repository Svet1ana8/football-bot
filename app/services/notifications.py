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

    player_name = first_name or str(request_user_id)
    username_text = f"@{username}" if username else "не указан"

    text = (
        "📩 Новая заявка\n\n"
        f"👤 Игрок: {player_name}\n"
        f"🆔 ID: {request_user_id}\n"
        f"🔗 Username: {username_text}\n"
        f"📌 Статус: {status}"
    )

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