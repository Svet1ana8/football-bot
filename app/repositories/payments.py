from datetime import date, timedelta

from app.config import DEFAULT_PAYMENT_DAY
from app.db import get_connection


def create_subscription_for_user(
    user_id: int,
    payment_day: int = DEFAULT_PAYMENT_DAY,
    subscription_type: str = "monthly"
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO player_subscriptions (
                    user_id,
                    payment_day,
                    subscription_type,
                    subscription_end_date,
                    last_payment_date,
                    is_paid_current_period,
                    has_custom_schedule,
                    payment_claimed,
                    full_attendance_bonus,
                    referral_bonus
                )
                VALUES (%s, %s, %s, NULL, NULL, FALSE, FALSE, FALSE, FALSE, FALSE)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, payment_day, subscription_type))
        conn.commit()


def get_subscription_by_user_id(user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    user_id,
                    payment_day,
                    subscription_type,
                    subscription_end_date,
                    last_payment_date,
                    is_paid_current_period,
                    has_custom_schedule,
                    payment_claimed
                FROM player_subscriptions
                WHERE user_id = %s
            """, (user_id,))
            return cur.fetchone()


def get_all_subscriptions():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    user_id,
                    payment_day,
                    subscription_type,
                    subscription_end_date,
                    last_payment_date,
                    is_paid_current_period,
                    has_custom_schedule,
                    payment_claimed
                FROM player_subscriptions
                ORDER BY user_id
            """)
            return cur.fetchall()


def update_subscription_dates(
    user_id: int,
    subscription_end_date: date,
    last_payment_date: date,
    is_paid_current_period: bool = True
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE player_subscriptions
                SET subscription_end_date = %s,
                    last_payment_date = %s,
                    is_paid_current_period = %s
                WHERE user_id = %s
            """, (subscription_end_date, last_payment_date, is_paid_current_period, user_id))
        conn.commit()


def set_payment_day(user_id: int, payment_day: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE player_subscriptions
                SET payment_day = %s,
                    has_custom_schedule = FALSE
                WHERE user_id = %s
            """, (payment_day, user_id))
        conn.commit()


def set_subscription_type(user_id: int, subscription_type: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE player_subscriptions
                SET subscription_type = %s
                WHERE user_id = %s
            """, (subscription_type, user_id))
        conn.commit()


def mark_paid_current_period(user_id: int, is_paid: bool):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE player_subscriptions
                SET is_paid_current_period = %s
                WHERE user_id = %s
            """, (is_paid, user_id))
        conn.commit()


def get_subscriptions_ending_soon(today: date, days: int = 5):
    end_limit = today + timedelta(days=days)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    user_id,
                    payment_day,
                    subscription_type,
                    subscription_end_date,
                    last_payment_date,
                    is_paid_current_period,
                    has_custom_schedule,
                    payment_claimed
                FROM player_subscriptions
                WHERE subscription_end_date IS NOT NULL
                  AND subscription_end_date >= %s
                  AND subscription_end_date <= %s
                ORDER BY subscription_end_date
            """, (today, end_limit))
            return cur.fetchall()


def get_unpaid_subscriptions(today: date, days_before: int = 5):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    user_id,
                    payment_day,
                    subscription_type,
                    subscription_end_date,
                    last_payment_date,
                    is_paid_current_period,
                    has_custom_schedule,
                    payment_claimed
                FROM player_subscriptions
                WHERE is_paid_current_period = FALSE
                  AND (payment_day - %s) BETWEEN 0 AND %s
                ORDER BY payment_day, user_id
            """, (today.day, days_before))
            return cur.fetchall()


from datetime import date


def _get_next_subscription_end_date(today: date, payment_day: int = 28) -> date:
    year = today.year
    month = today.month + 1

    if month == 13:
        month = 1
        year += 1

    return date(year, month, payment_day)


def confirm_payment(user_id: int, today: date):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT payment_day
                FROM player_subscriptions
                WHERE user_id = %s
            """, (user_id,))
            row = cur.fetchone()

            payment_day = row[0] if row and row[0] else 28
            new_end_date = _get_next_subscription_end_date(today, payment_day)

            cur.execute("""
                UPDATE player_subscriptions
                SET is_paid_current_period = TRUE,
                    last_payment_date = %s,
                    subscription_end_date = %s,
                    payment_claimed = FALSE
                WHERE user_id = %s
            """, (today, new_end_date, user_id))
        conn.commit()

    return new_end_date


def get_unpaid_subscriptions_with_users(today: date, days_before: int = 5):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ps.user_id,
                    u.username,
                    u.first_name,
                    ps.payment_day,
                    ps.subscription_type,
                    ps.subscription_end_date,
                    ps.last_payment_date,
                    ps.is_paid_current_period,
                    ps.has_custom_schedule,
                    ps.payment_claimed
                FROM player_subscriptions ps
                JOIN users u ON u.user_id = ps.user_id
                WHERE ps.is_paid_current_period = FALSE
                  AND (ps.payment_day - %s) BETWEEN 0 AND %s
                  AND u.status = 'approved'
                ORDER BY ps.payment_day, ps.user_id
            """, (today.day, days_before))
            return cur.fetchall()


def get_subscriptions_ending_soon_with_users(today: date, days: int = 5):
    end_limit = today + timedelta(days=days)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ps.user_id,
                    u.username,
                    u.first_name,
                    ps.payment_day,
                    ps.subscription_type,
                    ps.subscription_end_date,
                    ps.last_payment_date,
                    ps.is_paid_current_period,
                    ps.has_custom_schedule,
                    ps.payment_claimed
                FROM player_subscriptions ps
                JOIN users u ON u.user_id = ps.user_id
                WHERE ps.subscription_end_date IS NOT NULL
                  AND ps.subscription_end_date >= %s
                  AND ps.subscription_end_date <= %s
                  AND u.status = 'approved'
                ORDER BY ps.subscription_end_date
            """, (today, end_limit))
            return cur.fetchall()


def mark_payment_claimed(user_id: int, claimed: bool = True):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE player_subscriptions
                SET payment_claimed = %s
                WHERE user_id = %s
            """, (claimed, user_id))
        conn.commit()


def reject_claimed_payment(user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE player_subscriptions
                SET payment_claimed = FALSE
                WHERE user_id = %s
            """, (user_id,))
        conn.commit()


def add_payment_history(user_id: int, action: str, comment: str | None = None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO payment_history (user_id, action, comment)
                VALUES (%s, %s, %s)
            """, (user_id, action, comment))
        conn.commit()


def get_payment_history_by_user(user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, action, created_at, comment
                FROM payment_history
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
            return cur.fetchall()


def get_all_payment_history(limit: int = 50):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, action, created_at, comment
                FROM payment_history
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()


def get_player_bonuses(user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT full_attendance_bonus, referral_bonus
                FROM player_subscriptions
                WHERE user_id = %s
            """, (user_id,))
            return cur.fetchone()


def set_referral_bonus(user_id: int, value: bool):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE player_subscriptions
                SET referral_bonus = %s
                WHERE user_id = %s
            """, (value, user_id))
        conn.commit()


def set_full_attendance_bonus(user_id: int, value: bool):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE player_subscriptions
                SET full_attendance_bonus = %s
                WHERE user_id = %s
            """, (value, user_id))
        conn.commit()

def get_overdue_subscription_end_with_users(today: date):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ps.user_id,
                    u.username,
                    u.first_name,
                    ps.payment_day,
                    ps.subscription_type,
                    ps.subscription_end_date,
                    ps.last_payment_date,
                    ps.is_paid_current_period,
                    ps.has_custom_schedule,
                    ps.payment_claimed
                FROM player_subscriptions ps
                JOIN users u ON u.user_id = ps.user_id
                WHERE ps.is_paid_current_period = FALSE
                  AND ps.subscription_end_date IS NOT NULL
                  AND ps.subscription_end_date < %s
                  AND u.status = 'approved'
                ORDER BY ps.subscription_end_date, ps.user_id
            """, (today,))
            return cur.fetchall()