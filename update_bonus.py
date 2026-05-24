from app.db import get_connection

USER_ID = 556109902
FULL_ATTENDANCE_BONUS = True
REFERRAL_BONUS = False

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE player_subscriptions
            SET full_attendance_bonus = %s,
                referral_bonus = %s
            WHERE user_id = %s
            """,
            (FULL_ATTENDANCE_BONUS, REFERRAL_BONUS, USER_ID),
        )
    conn.commit()

print("Бонусы обновлены.")