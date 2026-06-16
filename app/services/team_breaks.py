from datetime import datetime, timedelta

from telegram.ext import ContextTypes

from app.config import COACH_IDS, TIMEZONE
from app.repositories.team_breaks import (
    ensure_team_break_repository_schema,
    get_pending_team_break_notifications,
    mark_team_break_notification_sent,
)
from app.repositories.users import get_users_by_status
from app.services.access import is_broadcast_recipient


TEAM_BREAK_NOTIFICATION_JOB_NAME = "team_break_notifications"
TEAM_BREAK_NOTIFICATION_INTERVAL_MINUTES = 5


def get_team_break_notification_recipients() -> list[int]:
    """
    Получатели уведомления о перерыве команды.

    Отправляем:
    - всем approved игрокам, кроме служебных/тренерских ID из обычной рассылки;
    - всем тренерам из COACH_IDS;
    - дубли убираем.
    """
    recipients: set[int] = set()

    approved_users = get_users_by_status("approved")
    for user_id, _username, _first_name in approved_users:
        if is_broadcast_recipient(user_id):
            recipients.add(int(user_id))

    for coach_id in COACH_IDS:
        try:
            recipients.add(int(coach_id))
        except (TypeError, ValueError):
            print(f"Некорректный coach_id в COACH_IDS: {coach_id}")

    return sorted(recipients)


async def send_pending_team_break_notifications(context: ContextTypes.DEFAULT_TYPE):
    """
    Каждые 5 минут проверяет таблицу team_breaks.

    Если notify_at уже наступил и notified_at ещё пустой — отправляет
    сообщение всем получателям и отмечает рассылку как обработанную.
    """
    now = datetime.now(TIMEZONE)
    pending_breaks = get_pending_team_break_notifications(now)

    if not pending_breaks:
        return

    recipients = get_team_break_notification_recipients()

    if not recipients:
        print("Нет получателей для уведомления об отдыхе команды.")

    for (
        break_id,
        start_date,
        end_date,
        notify_at,
        message_text,
        _notified_at,
    ) in pending_breaks:
        success_count = 0
        fail_count = 0

        for chat_id in recipients:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                )
                success_count += 1
            except Exception as e:
                print(
                    "Не удалось отправить уведомление об отдыхе команды "
                    f"получателю {chat_id}: {e}"
                )
                fail_count += 1

        mark_team_break_notification_sent(
            break_id=break_id,
            sent_at=datetime.now(TIMEZONE),
            success_count=success_count,
            fail_count=fail_count,
        )

        print(
            "Уведомление об отдыхе команды обработано. "
            f"break_id={break_id}, "
            f"period={start_date}..{end_date}, "
            f"success={success_count}, fail={fail_count}"
        )


def schedule_team_break_notification_jobs(application):
    """
    Планировщик одноразовых уведомлений о перерывах команды.

    Проверка каждые 5 минут делает рассылку устойчивой к перезапуску Render:
    если бот был выключен в точное время notify_at, он отправит сообщение
    при следующем запуске/проверке и больше не повторит его.
    """
    ensure_team_break_repository_schema()

    existing_jobs = application.job_queue.get_jobs_by_name(
        TEAM_BREAK_NOTIFICATION_JOB_NAME
    )
    if existing_jobs:
        return

    application.job_queue.run_repeating(
        send_pending_team_break_notifications,
        interval=timedelta(minutes=TEAM_BREAK_NOTIFICATION_INTERVAL_MINUTES),
        first=20,
        name=TEAM_BREAK_NOTIFICATION_JOB_NAME,
    )
