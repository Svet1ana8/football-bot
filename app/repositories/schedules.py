from datetime import datetime

from app.db import get_connection


def create_scheduled_message(send_at: datetime, message_text: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO scheduled_messages (send_at, message_text, status)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (send_at, message_text, "scheduled"))
            message_id = cur.fetchone()[0]
        conn.commit()
    return message_id


def get_scheduled_message(message_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, send_at, message_text, status
                FROM scheduled_messages
                WHERE id = %s
            """, (message_id,))
            return cur.fetchone()


def get_all_scheduled_messages():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, send_at, message_text, status
                FROM scheduled_messages
                ORDER BY send_at
            """)
            return cur.fetchall()


def mark_scheduled_message_done(message_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE scheduled_messages
                SET status = 'done'
                WHERE id = %s
            """, (message_id,))
        conn.commit()


def delete_scheduled_message(message_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM scheduled_messages
                WHERE id = %s
            """, (message_id,))
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted
