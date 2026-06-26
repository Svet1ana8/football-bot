from app.db import get_connection


def add_game_schedule(game_date, game_time, opponent_name, comment=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO game_schedule (game_date, game_time, opponent_name, comment, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (game_date, game_time, opponent_name, comment),
            )
            game_id = cur.fetchone()[0]
        conn.commit()
    return game_id


def get_upcoming_game_schedule():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    game_date,
                    game_time,
                    opponent_name,
                    comment
                FROM game_schedule
                WHERE is_active = TRUE
                  AND game_date >= (NOW() AT TIME ZONE 'Asia/Almaty')::date
                ORDER BY game_date, game_time
                """
            )
            return cur.fetchall()


def get_game_schedule_by_id(game_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, game_date, game_time, opponent_name, comment, is_active, created_at
                FROM game_schedule
                WHERE id = %s
                """,
                (game_id,),
            )
            return cur.fetchone()


def deactivate_game_schedule(game_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE game_schedule
                SET is_active = FALSE
                WHERE id = %s
                """,
                (game_id,),
            )
        conn.commit()