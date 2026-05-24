from app.db import get_connection

USER_ID = 123456789  # сюда вставь id игрока

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id, payment_day, subscription_type,
                   full_attendance_bonus, referral_bonus
            FROM player_subscriptions
            WHERE user_id = %s
            """,
            (USER_ID,),
        )
        print(cur.fetchone())