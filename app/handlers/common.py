from telegram import Update
from telegram.ext import ContextTypes

from app.keyboards import get_coach_menu, get_player_menu
from app.services.access import is_coach


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if is_coach(update.effective_user.id):
        await update.message.reply_text(
            f"Привет, {user.first_name}!\n\n"
            "Ты вошел как тренер.\n"
            "Используй меню ниже для работы с заявками, игроками и рассылками.",
            reply_markup=get_coach_menu()
        )
        return

    await update.message.reply_text(
        f"Привет, {user.first_name}!\n\n"
        "Это бот команды по американскому футболу Алматы Фениксы.\n"
        "Через него ты будешь получать напоминания и уведомления от тренера.\n\n"
        "Чтобы начать, нажми кнопку «Подать заявку» ниже.",
        reply_markup=get_player_menu()
    )


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой chat_id: {update.effective_user.id}")


async def deny_access(update: Update):
    await update.message.reply_text("У тебя нет доступа к этой команде.")
