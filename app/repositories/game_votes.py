from datetime import date, datetime

from app.db import get_connection


def save_game_vote_response(
    game_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    response: str,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO game_vote_responses (
                    game_id,
                    user_id,
                    username,
                    first_name,
                    response
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (game_id, user_id)
                DO UPDATE SET
                    username = COALESCE(EXCLUDED.username, game_vote_responses.username),
                    first_name = COALESCE(EXCLUDED.first_name, game_vote_responses.first_name),
                    response = EXCLUDED.response,
                    updated_at = NOW()
                """,
                (
                    game_id,
                    user_id,
                    username,
                    first_name,
                    response,
                ),
            )
        conn.commit()


def get_game_vote_response(game_id: int, user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT response
                FROM game_vote_responses
                WHERE game_id = %s
                  AND user_id = %s
                """,
                (
                    game_id,
                    user_id,
                ),
            )
            row = cur.fetchone()
            return row[0] if row else None


def get_game_vote_responses(game_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, username, first_name, response
                FROM game_vote_responses
                WHERE game_id = %s
                ORDER BY user_id
                """,
                (game_id,),
            )
            return cur.fetchall()


def get_game_vote_state(game_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    vote_date,
                    last_reminder_time,
                    report_sent_at
                FROM game_vote_state
                WHERE game_id = %s
                """,
                (game_id,),
            )
            return cur.fetchone()


def update_game_vote_last_reminder(
    game_id: int,
    vote_date: date,
    reminder_time: datetime,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO game_vote_state (
                    game_id,
                    vote_date,
                    last_reminder_time
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (game_id)
                DO UPDATE SET
                    vote_date = EXCLUDED.vote_date,
                    last_reminder_time = EXCLUDED.last_reminder_time,
                    updated_at = NOW()
                """,
                (
                    game_id,
                    vote_date,
                    reminder_time,
                ),
            )
        conn.commit()


def mark_game_vote_report_sent(
    game_id: int,
    vote_date: date,
    report_time: datetime,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO game_vote_state (
                    game_id,
                    vote_date,
                    report_sent_at
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (game_id)
                DO UPDATE SET
                    vote_date = EXCLUDED.vote_date,
                    report_sent_at = EXCLUDED.report_sent_at,
                    updated_at = NOW()
                """,
                (
                    game_id,
                    vote_date,
                    report_time,
                ),
            )
        conn.commit()
