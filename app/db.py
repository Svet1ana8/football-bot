import psycopg

from app.config import DATABASE_URL, DEFAULT_PAYMENT_DAY


def get_connection():
    if not DATABASE_URL:
        raise ValueError("Не найден DATABASE_URL в переменных окружения")
    return psycopg.connect(DATABASE_URL)


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    status TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS trainings (
                    id SERIAL PRIMARY KEY,
                    message_text TEXT NOT NULL,
                    start_time TIMESTAMPTZ NOT NULL,
                    last_reminder_time TIMESTAMPTZ,
                    stop_at TIMESTAMPTZ NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS training_schedule (
                    id SERIAL PRIMARY KEY,
                    training_date DATE NOT NULL,
                    training_time TIME NOT NULL,
                    comment TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                DROP TABLE IF EXISTS training_responses
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS training_responses (
                    training_id INTEGER NOT NULL REFERENCES trainings(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    response TEXT NOT NULL,
                    PRIMARY KEY (training_id, user_id)
                )
            """)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS player_subscriptions (
                    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                    payment_day INTEGER NOT NULL DEFAULT {DEFAULT_PAYMENT_DAY},
                    subscription_type TEXT NOT NULL DEFAULT 'monthly',
                    subscription_end_date DATE,
                    last_payment_date DATE,
                    is_paid_current_period BOOLEAN NOT NULL DEFAULT FALSE,
                    has_custom_schedule BOOLEAN NOT NULL DEFAULT FALSE,
                    payment_claimed BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)

            cur.execute("""
                ALTER TABLE player_subscriptions
                ADD COLUMN IF NOT EXISTS payment_claimed BOOLEAN NOT NULL DEFAULT FALSE
            """)

            cur.execute("""
                ALTER TABLE player_subscriptions
                ADD COLUMN IF NOT EXISTS subscription_type TEXT NOT NULL DEFAULT 'monthly'
            """)

            cur.execute(f"""
                ALTER TABLE player_subscriptions
                ALTER COLUMN payment_day SET DEFAULT {DEFAULT_PAYMENT_DAY}
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS payment_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    action TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    comment TEXT
                )
            """)

        conn.commit()