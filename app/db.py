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
                CREATE INDEX IF NOT EXISTS idx_trainings_active_start_time
                ON trainings (is_active, start_time DESC)
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
                CREATE TABLE IF NOT EXISTS game_schedule (
                    id SERIAL PRIMARY KEY,
                    game_date DATE NOT NULL,
                    game_time TIME NOT NULL,
                    opponent_name TEXT NOT NULL,
                    comment TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_vote_responses (
                    game_id INTEGER NOT NULL REFERENCES game_schedule(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    response TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (game_id, user_id)
                )
            """)

            cur.execute("""
                ALTER TABLE game_vote_responses
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """)

            cur.execute("""
                ALTER TABLE game_vote_responses
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """)

            cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE table_schema = 'public'
                      AND table_name = 'game_vote_responses'
                      AND constraint_name = 'game_vote_responses_response_check'
                ) THEN
                    ALTER TABLE game_vote_responses
                    ADD CONSTRAINT game_vote_responses_response_check
                    CHECK (response IN ('yes', 'no')) NOT VALID;
                END IF;
            END
            $$;
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_vote_responses_game_id
                ON game_vote_responses (game_id)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_vote_responses_user_id
                ON game_vote_responses (user_id)
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_vote_state (
                    game_id INTEGER PRIMARY KEY REFERENCES game_schedule(id) ON DELETE CASCADE,
                    vote_date DATE NOT NULL,
                    last_reminder_time TIMESTAMPTZ,
                    report_sent_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_game_vote_state_vote_date
                ON game_vote_state (vote_date)
            """)

            # ВАЖНО:
            # Нельзя делать DROP/TRUNCATE training_responses в production.
            # Иначе ответы игроков будут удаляться при запуске/рестарте бота.

            cur.execute("""
                CREATE TABLE IF NOT EXISTS training_responses (
                    training_id INTEGER NOT NULL REFERENCES trainings(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    response TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (training_id, user_id)
                )
            """)

            # Миграции для уже существующей таблицы training_responses.
            # Если таблица уже была создана раньше без этих колонок — они добавятся безопасно.
            cur.execute("""
                ALTER TABLE training_responses
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """)

            cur.execute("""
                ALTER TABLE training_responses
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """)

            # Защита от случайных значений response.
            # NOT VALID не ломает старт, если в старой базе уже есть мусорные значения,
            # но новые/обновляемые строки всё равно будут проверяться.
            cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE table_schema = 'public'
                      AND table_name = 'training_responses'
                      AND constraint_name = 'training_responses_response_check'
                ) THEN
                    ALTER TABLE training_responses
                    ADD CONSTRAINT training_responses_response_check
                    CHECK (response IN ('yes', 'no')) NOT VALID;
                END IF;
            END
            $$;
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_responses_training_id
                ON training_responses (training_id)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_responses_user_id
                ON training_responses (user_id)
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
                ALTER TABLE player_subscriptions
                ADD COLUMN IF NOT EXISTS full_attendance_bonus BOOLEAN NOT NULL DEFAULT FALSE
            """)

            cur.execute("""
                ALTER TABLE player_subscriptions
                ADD COLUMN IF NOT EXISTS referral_bonus BOOLEAN NOT NULL DEFAULT FALSE
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
                CREATE INDEX IF NOT EXISTS idx_trainings_active_start_time
                ON trainings (is_active, start_time DESC)
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

            # ВАЖНО:
            # Нельзя делать DROP/TRUNCATE training_responses в production.
            # Иначе ответы игроков будут удаляться при запуске/рестарте бота.

            cur.execute("""
                CREATE TABLE IF NOT EXISTS training_responses (
                    training_id INTEGER NOT NULL REFERENCES trainings(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    response TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (training_id, user_id)
                )
            """)

            # Миграции для уже существующей таблицы training_responses.
            # Если таблица уже была создана раньше без этих колонок — они добавятся безопасно.
            cur.execute("""
                ALTER TABLE training_responses
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """)

            cur.execute("""
                ALTER TABLE training_responses
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """)

            # Защита от случайных значений response.
            # NOT VALID не ломает старт, если в старой базе уже есть мусорные значения,
            # но новые/обновляемые строки всё равно будут проверяться.
            cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE table_schema = 'public'
                      AND table_name = 'training_responses'
                      AND constraint_name = 'training_responses_response_check'
                ) THEN
                    ALTER TABLE training_responses
                    ADD CONSTRAINT training_responses_response_check
                    CHECK (response IN ('yes', 'no')) NOT VALID;
                END IF;
            END
            $$;
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_responses_training_id
                ON training_responses (training_id)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_responses_user_id
                ON training_responses (user_id)
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
                ALTER TABLE player_subscriptions
                ADD COLUMN IF NOT EXISTS full_attendance_bonus BOOLEAN NOT NULL DEFAULT FALSE
            """)

            cur.execute("""
                ALTER TABLE player_subscriptions
                ADD COLUMN IF NOT EXISTS referral_bonus BOOLEAN NOT NULL DEFAULT FALSE
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
