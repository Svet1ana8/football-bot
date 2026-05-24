from datetime import time

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import BOT_TOKEN, TIMEZONE
from app.db import init_db
from app.handlers.callbacks import button_handler
from app.handlers.coach import (
    approve,
    approved,
    coach,
    refresh_player_menus,
    reject,
    send_message_to_approved,
    test_subscription_reminders,
)
from app.handlers.common import my_id, start
from app.handlers.player import menu_handler
from app.services.notifications import remind_coaches_about_pending_requests
from app.services.payments import schedule_daily_payment_jobs
from app.services.trainings import schedule_training_repeat_job


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
    app.add_handler(CommandHandler("test_sub_reminders", test_subscription_reminders))
    app.add_handler(CommandHandler("refresh_menu", refresh_player_menus))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    schedule_training_repeat_job(app)
    schedule_daily_payment_jobs(app)

    app.job_queue.run_daily(
        remind_coaches_about_pending_requests,
        time=time(9, 0, tzinfo=TIMEZONE),
        name="pending_requests_reminder_09",
    )
    app.job_queue.run_daily(
        remind_coaches_about_pending_requests,
        time=time(12, 0, tzinfo=TIMEZONE),
        name="pending_requests_reminder_12",
    )
    app.job_queue.run_daily(
        remind_coaches_about_pending_requests,
        time=time(15, 0, tzinfo=TIMEZONE),
        name="pending_requests_reminder_15",
    )
    app.job_queue.run_daily(
        remind_coaches_about_pending_requests,
        time=time(18, 0, tzinfo=TIMEZONE),
        name="pending_requests_reminder_18",
    )

    print("Бот запущен...")
    app.run_polling()