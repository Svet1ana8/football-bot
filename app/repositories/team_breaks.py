from datetime import datetime

from app.db import get_connection


def ensure_team_break_repository_schema():
    """
    Безопасная схема для одноразовых уведомлений о перерывах/отдыхе команды.

    Зачем нужна отдельная таблица:
    - Render может перезапуститься в момент рассылки;
    - уведомление не должно потеряться, если бот был выключен в точное время;
    - уведомление не должно отправляться повторно после успешной рассылки.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS team_breaks (
                    id SERIAL PRIMARY KEY,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    notify_at TIMESTAMPTZ NOT NULL,
                    message_text TEXT NOT NULL,
                    notified_at TIMESTAMPTZ,
                    notification_success_count INTEGER NOT NULL DEFAULT 0,
                    notification_fail_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_team_breaks_dates
                ON team_breaks(start_date, end_date)
            """)

            # Для уже существующей таблицы, если она когда-то была создана вручную.
            cur.execute("""
                ALTER TABLE team_breaks
                ADD COLUMN IF NOT EXISTS notification_success_count INTEGER NOT NULL DEFAULT 0
            """)

            cur.execute("""
                ALTER TABLE team_breaks
                ADD COLUMN IF NOT EXISTS notification_fail_count INTEGER NOT NULL DEFAULT 0
            """)

            cur.execute("""
                ALTER TABLE team_breaks
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_team_breaks_notify_pending
                ON team_breaks(notified_at, notify_at)
            """)

        conn.commit()


def get_pending_team_break_notifications(now: datetime):
    """
    Возвращает уведомления, время которых уже наступило,
    но которые ещё не были отмечены как отправленные.
    """
    ensure_team_break_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    id,
                    start_date,
                    end_date,
                    notify_at,
                    message_text,
                    notified_at
                FROM team_breaks
                WHERE notified_at IS NULL
                  AND notify_at <= %s
                ORDER BY notify_at, id
            """, (now,))
            return cur.fetchall()


def mark_team_break_notification_sent(
    break_id: int,
    sent_at: datetime,
    success_count: int,
    fail_count: int,
):
    """
    Отмечает, что уведомление по периоду отдыха уже обработано.

    Отмечаем даже если часть отправок не удалась, чтобы бот не спамил
    всех повторно на следующей проверке. Количество ошибок сохраняем.
    """
    ensure_team_break_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE team_breaks
                SET
                    notified_at = %s,
                    notification_success_count = %s,
                    notification_fail_count = %s
                WHERE id = %s
            """, (
                sent_at,
                success_count,
                fail_count,
                break_id,
            ))

        conn.commit()
