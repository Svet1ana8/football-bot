from datetime import date, time

from app.db import get_connection


def get_active_training_schedule():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, training_date, training_time, comment, is_active, created_at
                FROM training_schedule
                WHERE is_active = TRUE
                ORDER BY training_date ASC, training_time ASC
            """)
            return cur.fetchall()


def get_upcoming_training_schedule(from_date: date | None = None):
    if from_date is None:
        from_date = date.today()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, training_date, training_time, comment, is_active, created_at
                FROM training_schedule
                WHERE is_active = TRUE
                  AND training_date >= %s
                ORDER BY training_date ASC, training_time ASC
            """, (from_date,))
            return cur.fetchall()


def add_training_schedule(training_date: date, training_time: time, comment: str | None = None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO training_schedule (training_date, training_time, comment, is_active)
                VALUES (%s, %s, %s, TRUE)
                RETURNING id
            """, (training_date, training_time, comment))
            schedule_id = cur.fetchone()[0]
        conn.commit()
    return schedule_id


def deactivate_training_schedule(schedule_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE training_schedule
                SET is_active = FALSE
                WHERE id = %s
            """, (schedule_id,))
        conn.commit()


def get_training_schedule_by_id(schedule_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, training_date, training_time, comment, is_active, created_at
                FROM training_schedule
                WHERE id = %s
            """, (schedule_id,))
            return cur.fetchone()