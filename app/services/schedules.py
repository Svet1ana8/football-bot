from datetime import datetime

from telegram.ext import Application, ContextTypes

from app.config import TIMEZONE
from app.repositories.schedules import (
    get_all_scheduled_messages,
    get_scheduled_message,
    mark_scheduled_message_done,
)
from app.repositories.users import get_users_by_status
from app.services.access import is_broadcast_recipient


async def scheduled_send_job(context: ContextTypes.DEFAULT_TYPE):
    message_id = context.job.data["message_id"]
    scheduled_message = get_scheduled_message(message_id)

    if not scheduled_message:
        return

    _, send_at, message_text, status = scheduled_message

    if status != "scheduled":
        return

    approved_users = get_users_by_status("approved")

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except Exception as e:
            print(f"Ошибка отправки пользователю {user_id}: {e}")
            fail_count += 1

    mark_scheduled_message_done(message_id)

    print(
        f"Scheduled message #{message_id} sent. "
        f"Success: {success_count}, Failed: {fail_count}"
    )


def restore_jobs(application: Application):
    messages = get_all_scheduled_messages()

    for message_id, send_at, message_text, status in messages:
        if status != "scheduled":
            continue

        if isinstance(send_at, str):
            send_at_dt = datetime.fromisoformat(send_at)
        else:
            send_at_dt = send_at

        if send_at_dt.tzinfo is None:
            send_at_dt = send_at_dt.replace(tzinfo=TIMEZONE)

        if send_at_dt > datetime.now(TIMEZONE):
            application.job_queue.run_once(
                scheduled_send_job,
                when=send_at_dt,
                data={"message_id": message_id},
                name=f"scheduled_message_{message_id}"
            )
