from datetime import datetime

from app.db import get_connection


def ensure_training_repository_schema():
    """
    Безопасные миграции для тренировок и ответов.

    Ничего не удаляет.
    Только добавляет недостающие поля, если их ещё нет.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE trainings
                ADD COLUMN IF NOT EXISTS last_confirmation_time TIMESTAMPTZ
            """)

            cur.execute("""
                ALTER TABLE training_responses
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """)

            cur.execute("""
                ALTER TABLE training_responses
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_responses_training_id
                ON training_responses(training_id)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_responses_user_id
                ON training_responses(user_id)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_trainings_active_start_time
                ON trainings(is_active, start_time DESC)
            """)

        conn.commit()


def create_training(message_text: str, start_time: datetime, stop_at: datetime):
    """
    Создаёт новую тренировку.

    Важно:
    - старая активная тренировка НЕ удаляется;
    - старая активная тренировка становится is_active = FALSE;
    - новая тренировка получает новый id;
    - ответы старых тренировок остаются в training_responses;
    - новые ответы будут писаться под новый training_id.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET is_active = FALSE
                WHERE is_active = TRUE
            """)

            cur.execute("""
                INSERT INTO trainings (
                    message_text,
                    start_time,
                    last_reminder_time,
                    stop_at,
                    is_active
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                message_text,
                start_time,
                None,
                stop_at,
                True
            ))

            training_id = cur.fetchone()[0]

        conn.commit()

    return training_id


def get_active_training():
    """
    Возвращает текущую активную тренировку.

    Поля:
    0 - id
    1 - message_text
    2 - start_time
    3 - last_reminder_time
    4 - stop_at
    5 - is_active
    6 - last_confirmation_time
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    id,
                    message_text,
                    start_time,
                    last_reminder_time,
                    stop_at,
                    is_active,
                    last_confirmation_time
                FROM trainings
                WHERE is_active = TRUE
                ORDER BY id DESC
                LIMIT 1
            """)
            return cur.fetchone()


def update_training_last_reminder(training_id: int, reminder_time: datetime):
    """
    Обновляет время последнего АВТО-напоминания за день до тренировки.

    Важно:
    - ручная кнопка тренера НЕ должна вызывать эту функцию;
    - контрольное подтверждение в день тренировки НЕ должно вызывать эту функцию.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET last_reminder_time = %s
                WHERE id = %s
            """, (
                reminder_time,
                training_id
            ))

        conn.commit()


def update_training_last_confirmation(training_id: int, confirmation_time: datetime):
    """
    Обновляет время контрольного подтверждения в день тренировки.

    Используется отдельно от last_reminder_time,
    чтобы контрольное подтверждение не конфликтовало с обычными напоминаниями.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET last_confirmation_time = %s
                WHERE id = %s
            """, (
                confirmation_time,
                training_id
            ))

        conn.commit()


def deactivate_training(training_id: int):
    """
    Завершает тренировку.

    Важно:
    - тренировку не удаляем;
    - ответы по ней не удаляем;
    - просто ставим is_active = FALSE.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET is_active = FALSE
                WHERE id = %s
            """, (
                training_id,
            ))

        conn.commit()


def save_training_response(
    training_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    response: str
):
    """
    Сохраняет ответ игрока на тренировку.

    Логика:
    - один игрок = одна строка на одну тренировку;
    - если игрок нажал повторно, его ответ обновляется;
    - ответы других игроков не затираются;
    - ответы прошлых тренировок не затираются, потому что другой training_id.
    """
    if response not in ("yes", "no"):
        raise ValueError(f"Invalid training response: {response}")

    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO training_responses (
                    training_id,
                    user_id,
                    username,
                    first_name,
                    response,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (training_id, user_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    response = EXCLUDED.response,
                    updated_at = NOW()
            """, (
                training_id,
                user_id,
                username,
                first_name,
                response
            ))

        conn.commit()


def save_player_training_response(
    training_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    response: str
):
    """
    Алиас под название, которое используется в callbacks.py / services.
    """
    return save_training_response(
        training_id=training_id,
        user_id=user_id,
        username=username,
        first_name=first_name,
        response=response
    )


def get_training_responses(training_id: int):
    """
    Возвращает все ответы по конкретной тренировке.

    Важно:
    - берём ответы только по переданному training_id;
    - голосовалки разных тренировок не пересекаются.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    user_id,
                    username,
                    first_name,
                    response
                FROM training_responses
                WHERE training_id = %s
                ORDER BY first_name NULLS LAST, user_id
            """, (
                training_id,
            ))

            return cur.fetchall()


def get_user_response_for_training(training_id: int, user_id: int):
    """
    Возвращает ответ конкретного игрока по конкретной тренировке.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT response
                FROM training_responses
                WHERE training_id = %s
                  AND user_id = %s
            """, (
                training_id,
                user_id
            ))

            return cur.fetchone()


def get_player_training_stats(user_id: int):
    """
    Общая статистика игрока по всем тренировкам.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE response = 'yes') AS yes_count,
                    COUNT(*) FILTER (WHERE response = 'no') AS no_count,
                    COUNT(*) AS total_count
                FROM training_responses
                WHERE user_id = %s
            """, (
                user_id,
            ))

            return cur.fetchone()


def get_month_attendance_stats(year: int, month: int):
    """
    Статистика посещаемости за месяц.

    Так как все ответы лежат в одной таблице training_responses,
    а тренировки разделены через training_id, можно нормально считать историю.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    tr.user_id,
                    tr.username,
                    tr.first_name,
                    COUNT(*) FILTER (WHERE tr.response = 'yes') AS yes_count,
                    COUNT(*) FILTER (WHERE tr.response = 'no') AS no_count,
                    COUNT(*) AS total_count
                FROM training_responses tr
                JOIN trainings t ON t.id = tr.training_id
                WHERE EXTRACT(YEAR FROM t.start_time) = %s
                  AND EXTRACT(MONTH FROM t.start_time) = %s
                GROUP BY tr.user_id, tr.username, tr.first_name
                ORDER BY yes_count DESC, tr.first_name NULLS LAST, tr.user_id
            """, (
                year,
                month
            ))

            return cur.fetchall()