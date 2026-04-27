from app.db import get_connection


def save_training_response(user_id: int, username: str | None, first_name: str | None, response: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO training_responses (user_id, username, first_name, response)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    response = excluded.response
            """, (user_id, username, first_name, response))
        conn.commit()


def get_all_training_responses():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, first_name, response
                FROM training_responses
                ORDER BY first_name NULLS LAST, user_id
            """)
            return cur.fetchall()


def clear_training_responses():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM training_responses")
        conn.commit()
