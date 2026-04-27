from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import BOT_TOKEN
from app.db import init_db
from app.handlers.callbacks import button_handler
from app.handlers.coach import (
    approve,
    approved,
    coach,
    delete_schedule,
    list_scheduled,
    reject,
    schedule_message,
    send_message_to_approved,
)
from app.handlers.common import my_id, start
from app.handlers.player import menu_handler
from app.services.schedules import restore_jobs


def main():
    if not BOT_TOKEN:
        raise ValueError("Не найден BOT_TOKEN в переменных окружения")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", my_id))
    app.add_handler(CommandHandler("coach", coach))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("reject", reject))
    app.add_handler(CommandHandler("approved", approved))
    app.add_handler(CommandHandler("send", send_message_to_approved))
    app.add_handler(CommandHandler("schedule", schedule_message))
    app.add_handler(CommandHandler("scheduled", list_scheduled))
    app.add_handler(CommandHandler("delete_schedule", delete_schedule))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    restore_jobs(app)

    print("Бот запущен...")
    app.run_polling()
