from datetime import datetime

from app.db import get_connection


def create_training(message_text: str, start_time: datetime, stop_at: datetime):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Перед созданием новой тренировки выключаем старые активные
            cur.execute("""
                UPDATE trainings
                SET is_active = FALSE
                WHERE is_active = TRUE
            """)

            cur.execute("""
                INSERT INTO trainings (
                    message_text,
                    start_time,
                    last_reminder_time,
                    stop_at,
                    is_active
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                message_text,
                start_time,
                start_time,
                stop_at,
                True
            ))

            training_id = cur.fetchone()[0]

        conn.commit()

    return training_id


def get_active_training():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, message_text, start_time, last_reminder_time, stop_at, is_active
                FROM trainings
                WHERE is_active = TRUE
                ORDER BY id DESC
                LIMIT 1
            """)
            return cur.fetchone()


def update_training_last_reminder(training_id: int, reminder_time: datetime):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET last_reminder_time = %s
                WHERE id = %s
            """, (reminder_time, training_id))

        conn.commit()


def deactivate_training(training_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET is_active = FALSE
                WHERE id = %s
            """, (training_id,))

        conn.commit()


def save_training_response(
    training_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    response: str
):
    if response not in ("yes", "no"):
        raise ValueError(f"Invalid training response: {response}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO training_responses (
                    training_id,
                    user_id,
                    username,
                    first_name,
                    response
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (training_id, user_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    response = EXCLUDED.response
            """, (
                training_id,
                user_id,
                username,
                first_name,
                response
            ))

        conn.commit()


# Алиас под название, которое используется в callbacks.py / services
def save_player_training_response(
    training_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    response: str
):
    return save_training_response(
        training_id=training_id,
        user_id=user_id,
        username=username,
        first_name=first_name,
        response=response
    )


def get_training_responses(training_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, first_name, response
                FROM training_responses
                WHERE training_id = %s
                ORDER BY first_name NULLS LAST, user_id
            """, (training_id,))

            return cur.fetchall()


def get_user_response_for_training(training_id: int, user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT response
                FROM training_responses
                WHERE training_id = %s
                  AND user_id = %s
            """, (training_id, user_id))

            return cur.fetchone()


def get_player_training_stats(user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE response = 'yes') AS yes_count,
                    COUNT(*) FILTER (WHERE response = 'no') AS no_count,
                    COUNT(*) AS total_count
                FROM training_responses
                WHERE user_id = %s
            """, (user_id,))

            return cur.fetchone()


def get_month_attendance_stats(year: int, month: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    tr.user_id,
                    tr.username,
                    tr.first_name,
                    COUNT(*) FILTER (WHERE tr.response = 'yes') AS yes_count,
                    COUNT(*) FILTER (WHERE tr.response = 'no') AS no_count,
                    COUNT(*) AS total_count
                FROM training_responses tr
                JOIN trainings t ON t.id = tr.training_id
                WHERE EXTRACT(YEAR FROM t.start_time) = %s
                  AND EXTRACT(MONTH FROM t.start_time) = %s
                GROUP BY tr.user_id, tr.username, tr.first_name
                ORDER BY yes_count DESC, tr.first_name NULLS LAST, tr.user_id
            """, (year, month))

            return cur.fetchall()