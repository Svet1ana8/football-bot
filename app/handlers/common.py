from telegram import Update
from telegram.ext import ContextTypes

from app.keyboards import get_approved_player_menu, get_coach_menu, get_player_menu
from app.repositories.users import get_user_by_id
from app.services.access import is_coach


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing_user = get_user_by_id(user.id)

    display_name = user.first_name
    if existing_user and existing_user[2]:
        display_name = existing_user[2]

    if is_coach(user.id):
        await update.message.reply_text(
            f"Привет, {display_name}!\n\n"
            "Ты вошел как тренер.\n"
            "Используй меню ниже для работы с заявками, игроками и уведомлениями.",
            reply_markup=get_coach_menu()
        )
        return

    if existing_user and existing_user[3] == "approved":
        await update.message.reply_text(
            f"Привет, {display_name}!\n\n"
            "Ты уже одобрен тренером и получаешь уведомления.",
            reply_markup=get_approved_player_menu()
        )
        return

    if existing_user and existing_user[3] == "awaiting_name":
        await update.message.reply_text(
            "Напиши своё имя и фамилию.\n\n"
            "Например: Иванов Иван",
            reply_markup=get_player_menu()
        )
        return

    await update.message.reply_text(
        f"Привет, {display_name}!\n\n"
        "Это бот команды по американскому футболу Алматы Фениксы.\n"
        "Через него ты будешь получать напоминания и уведомления от тренера.\n\n"
        "Чтобы начать, нажми кнопку «Подать заявку» ниже.",
        reply_markup=get_player_menu()
    )


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой chat_id: {update.effective_user.id}")


async def deny_access(update: Update):
    await update.message.reply_text("У тебя нет доступа к этой команде.")