from app.db import get_connection


def add_or_update_user(user_id: int, username: str | None, first_name: str | None, status: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, username, first_name, status)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    status = excluded.status
            """, (user_id, username, first_name, status))
        conn.commit()


def get_users_by_status(status: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, first_name
                FROM users
                WHERE status = %s
                ORDER BY user_id
            """, (status,))
            return cur.fetchall()


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, first_name, status
                FROM users
                WHERE user_id = %s
            """, (user_id,))
            return cur.fetchone()


def delete_user(user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM users
                WHERE user_id = %s
            """, (user_id,))
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted
