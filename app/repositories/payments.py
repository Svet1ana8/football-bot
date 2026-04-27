from datetime import date, timedelta

from app.db import get_connection


def create_subscription_for_user(user_id: int, payment_day: int = 24):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO player_subscriptions (
                    user_id,
                    payment_day,
                    subscription_end_date,
                    last_payment_date,
                    is_paid_current_period,
                    has_custom_schedule
                )
                VALUES (%s, %s, NULL, NULL, FALSE, FALSE)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, payment_day))
        conn.commit()


def get_subscription_by_user_id(user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, payment_day, subscription_end_date, last_payment_date,
                       is_paid_current_period, has_custom_schedule
                FROM player_subscriptions
                WHERE user_id = %s
            """, (user_id,))
            return cur.fetchone()


def get_all_subscriptions():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, payment_day, subscription_end_date, last_payment_date,
                       is_paid_current_period, has_custom_schedule
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


def set_payment_day(user_id: int, payment_day: int, has_custom_schedule: bool = True):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE player_subscriptions
                SET payment_day = %s,
                    has_custom_schedule = %s
                WHERE user_id = %s
            """, (payment_day, has_custom_schedule, user_id))
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
                SELECT user_id, payment_day, subscription_end_date, last_payment_date,
                       is_paid_current_period, has_custom_schedule
                FROM player_subscriptions
                WHERE subscription_end_date IS NOT NULL
                  AND subscription_end_date >= %s
                  AND subscription_end_date <= %s
                ORDER BY subscription_end_date
            """, (today, end_limit))
            return cur.fetchall()


def get_unpaid_subscriptions(today: date):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, payment_day, subscription_end_date, last_payment_date,
                       is_paid_current_period, has_custom_schedule
                FROM player_subscriptions
                WHERE payment_day <= %s
                  AND is_paid_current_period = FALSE
                ORDER BY payment_day, user_id
            """, (today.day,))
            return cur.fetchall()

from datetime import date


def confirm_payment(user_id: int, today: date, new_end_date: date):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE player_subscriptions
                SET is_paid_current_period = TRUE,
                    last_payment_date = %s,
                    subscription_end_date = %s
                WHERE user_id = %s
            """, (today, new_end_date, user_id))
        conn.commit()


def get_unpaid_subscriptions_with_users(today: date):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ps.user_id,
                    u.username,
                    u.first_name,
                    ps.payment_day,
                    ps.subscription_end_date,
                    ps.last_payment_date,
                    ps.is_paid_current_period,
                    ps.has_custom_schedule
                FROM player_subscriptions ps
                JOIN users u ON u.user_id = ps.user_id
                WHERE ps.payment_day <= %s
                  AND ps.is_paid_current_period = FALSE
                  AND u.status = 'approved'
                ORDER BY ps.payment_day, ps.user_id
            """, (today.day,))
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
                    ps.subscription_end_date,
                    ps.last_payment_date,
                    ps.is_paid_current_period,
                    ps.has_custom_schedule
                FROM player_subscriptions ps
                JOIN users u ON u.user_id = ps.user_id
                WHERE ps.subscription_end_date IS NOT NULL
                  AND ps.subscription_end_date >= %s
                  AND ps.subscription_end_date <= %s
                  AND u.status = 'approved'
                ORDER BY ps.subscription_end_date
            """, (today, end_limit))
            return cur.fetchall()