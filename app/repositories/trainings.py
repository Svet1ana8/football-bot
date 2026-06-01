from datetime import date, datetime

from app.db import get_connection


def ensure_training_repository_schema():
    """
    Безопасные миграции для тренировок и ответов.

    Важно:
    - ничего не удаляем;
    - старые ответы не трогаем;
    - старые тренировки не удаляем;
    - только добавляем недостающие поля/индексы.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE trainings
                ADD COLUMN IF NOT EXISTS last_confirmation_time TIMESTAMPTZ
            """)

            cur.execute("""
                ALTER TABLE trainings
                ADD COLUMN IF NOT EXISTS last_training_day_no_response_reminder_time TIMESTAMPTZ
            """)

            cur.execute("""
                ALTER TABLE trainings
                ADD COLUMN IF NOT EXISTS last_coach_report_time TIMESTAMPTZ
            """)

            cur.execute("""
                ALTER TABLE trainings
                ADD COLUMN IF NOT EXISTS is_custom BOOLEAN NOT NULL DEFAULT FALSE
            """)

            cur.execute("""
                ALTER TABLE trainings
                ADD COLUMN IF NOT EXISTS created_by_user_id BIGINT
            """)

            cur.execute("""
                ALTER TABLE trainings
                ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ
            """)

            cur.execute("""
                ALTER TABLE trainings
                ADD COLUMN IF NOT EXISTS cancelled_by_user_id BIGINT
            """)

            cur.execute("""
                ALTER TABLE trainings
                ADD COLUMN IF NOT EXISTS cancel_reason TEXT
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
                CREATE INDEX IF NOT EXISTS idx_trainings_active_start_time
                ON trainings(is_active, start_time DESC)
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
                CREATE TABLE IF NOT EXISTS training_reminder_logs (
                    id SERIAL PRIMARY KEY,
                    training_id INTEGER NOT NULL REFERENCES trainings(id) ON DELETE CASCADE,
                    reminder_type TEXT NOT NULL,
                    sent_by_user_id BIGINT,
                    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_reminder_logs_training_id
                ON training_reminder_logs(training_id)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_training_reminder_logs_type_sent_at
                ON training_reminder_logs(reminder_type, sent_at DESC)
            """)

        conn.commit()


def create_training(
    message_text: str,
    start_time: datetime,
    stop_at: datetime,
    created_by_user_id: int | None = None,
    is_custom: bool = False,
):
    """
    Создаёт новую тренировку.

    Важно:
    - старая активная тренировка НЕ удаляется;
    - старая активная тренировка становится is_active = FALSE;
    - новая тренировка получает новый id;
    - старые ответы остаются в training_responses;
    - новые ответы пишутся под новый training_id.

    Совместимо со старыми вызовами:
    create_training(message_text, start_time, stop_at)
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
                    is_active,
                    last_confirmation_time,
                    last_training_day_no_response_reminder_time,
                    last_coach_report_time,
                    is_custom,
                    created_by_user_id,
                    cancelled_at,
                    cancelled_by_user_id,
                    cancel_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL)
                RETURNING id
            """, (
                message_text,
                start_time,
                None,
                stop_at,
                True,
                None,
                None,
                None,
                is_custom,
                created_by_user_id,
            ))

            training_id = cur.fetchone()[0]

        conn.commit()

    return training_id


def get_active_training():
    """
    Возвращает текущую активную тренировку.

    Поля tuple:
    0 - id
    1 - message_text
    2 - start_time
    3 - last_reminder_time
    4 - stop_at
    5 - is_active
    6 - last_confirmation_time
    7 - is_custom
    8 - created_by_user_id
    9 - last_training_day_no_response_reminder_time
    10 - last_coach_report_time
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
                    last_confirmation_time,
                    is_custom,
                    created_by_user_id,
                    last_training_day_no_response_reminder_time,
                    last_coach_report_time
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
    - контрольное подтверждение НЕ должно вызывать эту функцию;
    - напоминание неответившим в день тренировки НЕ должно вызывать эту функцию;
    - авто-отчёт тренеру НЕ должен вызывать эту функцию.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET last_reminder_time = %s
                WHERE id = %s
            """, (
                reminder_time,
                training_id,
            ))

        conn.commit()


def update_training_last_confirmation(training_id: int, confirmation_time: datetime):
    """
    Обновляет время контрольного подтверждения в день тренировки.

    Это отдельное поле, чтобы контрольное подтверждение
    не конфликтовало с обычными авто-напоминаниями.
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
                training_id,
            ))

        conn.commit()


def update_training_day_no_response_reminder(training_id: int, reminder_time: datetime):
    """
    Обновляет время последнего напоминания в день тренировки
    для тех, кто не ответил на первичное голосование.

    Важно:
    - не трогает last_reminder_time;
    - не трогает last_confirmation_time;
    - не трогает last_coach_report_time;
    - не конфликтует с ручной кнопкой тренера;
    - не удаляет ответы.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET last_training_day_no_response_reminder_time = %s
                WHERE id = %s
            """, (
                reminder_time,
                training_id,
            ))

        conn.commit()


def update_training_coach_report_time(training_id: int, report_time: datetime):
    """
    Обновляет время последнего авто-отчёта тренеру.

    Нужно, чтобы в день тренировки отчёт в 19:00–19:59
    не отправлялся повторно при каждой проверке job.

    Важно:
    - не трогает last_reminder_time;
    - не трогает last_confirmation_time;
    - не трогает last_training_day_no_response_reminder_time;
    - не удаляет ответы игроков.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET last_coach_report_time = %s
                WHERE id = %s
            """, (
                report_time,
                training_id,
            ))

        conn.commit()


def deactivate_training(training_id: int):
    """
    Просто завершает тренировку.

    Важно:
    - тренировку не удаляем;
    - ответы по ней не удаляем;
    - только ставим is_active = FALSE.
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


def cancel_active_training(
    cancelled_by_user_id: int | None = None,
    reason: str | None = None,
):
    """
    Отменяет текущую активную тренировку.

    Важно:
    - тренировку не удаляем;
    - ответы не удаляем;
    - история остаётся;
    - просто закрываем active-флаг и записываем отмену.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET
                    is_active = FALSE,
                    cancelled_at = NOW(),
                    cancelled_by_user_id = %s,
                    cancel_reason = %s
                WHERE is_active = TRUE
                RETURNING id
            """, (
                cancelled_by_user_id,
                reason,
            ))

            row = cur.fetchone()

        conn.commit()

    return row[0] if row else None


def create_training_reminder_log(
    training_id: int,
    reminder_type: str,
    sent_by_user_id: int | None = None,
):
    """
    Логирует отправку/действие по тренировке.

    Типы:
    - auto_day_before
    - training_day_no_response
    - training_day_confirmation
    - coach_training_report
    - manual_coach
    - custom_training_created
    - training_cancelled
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO training_reminder_logs (
                    training_id,
                    reminder_type,
                    sent_by_user_id
                )
                VALUES (%s, %s, %s)
            """, (
                training_id,
                reminder_type,
                sent_by_user_id,
            ))

        conn.commit()


def save_training_response(
    training_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    response: str,
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
                response,
            ))

        conn.commit()


def save_player_training_response(
    training_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    response: str,
):
    """
    Алиас под название, которое используется в callbacks.py / services.
    """
    return save_training_response(
        training_id=training_id,
        user_id=user_id,
        username=username,
        first_name=first_name,
        response=response,
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
                user_id,
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
                month,
            ))

            return cur.fetchall()


def get_month_no_response_stats(year: int, month: int, until_date: date | None = None):
    """
    Статистика игроков, которые не отвечали на голосования за месяц.

    Считает approved-игроков и тренировки за выбранный месяц.

    Логика:
    - берём всех approved игроков;
    - берём все тренировки за месяц до until_date включительно;
    - если у игрока нет строки в training_responses по training_id,
      значит он не ответил;
    - отменённые тренировки не считаем.

    until_date нужен для отчёта 15 числа:
    например 15.06 считаем только тренировки с 01.06 по 15.06.
    Для отчёта в последний день месяца считаем весь месяц.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            if until_date:
                cur.execute("""
                    SELECT
                        u.user_id,
                        u.username,
                        u.first_name,
                        COUNT(*) FILTER (WHERE tr.user_id IS NULL) AS no_response_count,
                        COUNT(*) AS total_trainings
                    FROM users u
                    CROSS JOIN trainings t
                    LEFT JOIN training_responses tr
                        ON tr.training_id = t.id
                       AND tr.user_id = u.user_id
                    WHERE u.status = 'approved'
                      AND EXTRACT(YEAR FROM t.start_time) = %s
                      AND EXTRACT(MONTH FROM t.start_time) = %s
                      AND DATE(t.start_time) <= %s
                      AND t.cancelled_at IS NULL
                    GROUP BY u.user_id, u.username, u.first_name
                    HAVING COUNT(*) FILTER (WHERE tr.user_id IS NULL) > 0
                    ORDER BY no_response_count DESC, u.first_name NULLS LAST, u.user_id
                """, (
                    year,
                    month,
                    until_date,
                ))
            else:
                cur.execute("""
                    SELECT
                        u.user_id,
                        u.username,
                        u.first_name,
                        COUNT(*) FILTER (WHERE tr.user_id IS NULL) AS no_response_count,
                        COUNT(*) AS total_trainings
                    FROM users u
                    CROSS JOIN trainings t
                    LEFT JOIN training_responses tr
                        ON tr.training_id = t.id
                       AND tr.user_id = u.user_id
                    WHERE u.status = 'approved'
                      AND EXTRACT(YEAR FROM t.start_time) = %s
                      AND EXTRACT(MONTH FROM t.start_time) = %s
                      AND t.cancelled_at IS NULL
                    GROUP BY u.user_id, u.username, u.first_name
                    HAVING COUNT(*) FILTER (WHERE tr.user_id IS NULL) > 0
                    ORDER BY no_response_count DESC, u.first_name NULLS LAST, u.user_id
                """, (
                    year,
                    month,
                ))

            return cur.fetchall()


def get_period_no_response_stats(start_date: date, end_date: date):
    """
    Статистика неответивших за произвольный период.

    Нужна на будущее, если захочешь отчёты не только за месяц,
    а например за сезон или за последние 30 дней.

    Диапазон включительный:
    start_date <= training_date <= end_date
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    u.user_id,
                    u.username,
                    u.first_name,
                    COUNT(*) FILTER (WHERE tr.user_id IS NULL) AS no_response_count,
                    COUNT(*) AS total_trainings
                FROM users u
                CROSS JOIN trainings t
                LEFT JOIN training_responses tr
                    ON tr.training_id = t.id
                   AND tr.user_id = u.user_id
                WHERE u.status = 'approved'
                  AND DATE(t.start_time) >= %s
                  AND DATE(t.start_time) <= %s
                  AND t.cancelled_at IS NULL
                GROUP BY u.user_id, u.username, u.first_name
                HAVING COUNT(*) FILTER (WHERE tr.user_id IS NULL) > 0
                ORDER BY no_response_count DESC, u.first_name NULLS LAST, u.user_id
            """, (
                start_date,
                end_date,
            ))

            return cur.fetchall()


def get_month_total_trainings_count(year: int, month: int):
    """
    Считает количество тренировок за месяц.

    Отменённые тренировки не считаем.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM trainings
                WHERE EXTRACT(YEAR FROM start_time) = %s
                  AND EXTRACT(MONTH FROM start_time) = %s
                  AND cancelled_at IS NULL
            """, (
                year,
                month,
            ))

            row = cur.fetchone()
            return row[0] if row else 0


def get_month_attendance_rating_stats(year: int, month: int):
    """
    Рейтинг посещаемости за месяц.

    Логика:
    - берём всех approved игроков;
    - берём все тренировки за месяц;
    - yes_count = сколько раз игрок нажал 'Приду';
    - no_count = сколько раз игрок нажал 'Не приду';
    - no_response_count = сколько раз игрок не ответил;
    - total_trainings = сколько всего тренировок было в месяце;
    - если игрок не ответил, это НЕ считается как посещение.

    Возвращает:
    user_id, username, first_name, yes_count, no_count, no_response_count, total_trainings
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH month_trainings AS (
                    SELECT id
                    FROM trainings
                    WHERE EXTRACT(YEAR FROM start_time) = %s
                      AND EXTRACT(MONTH FROM start_time) = %s
                      AND cancelled_at IS NULL
                )
                SELECT
                    u.user_id,
                    u.username,
                    u.first_name,
                    COUNT(*) FILTER (WHERE tr.response = 'yes') AS yes_count,
                    COUNT(*) FILTER (WHERE tr.response = 'no') AS no_count,
                    COUNT(*) FILTER (WHERE tr.user_id IS NULL) AS no_response_count,
                    COUNT(mt.id) AS total_trainings
                FROM users u
                CROSS JOIN month_trainings mt
                LEFT JOIN training_responses tr
                    ON tr.training_id = mt.id
                   AND tr.user_id = u.user_id
                WHERE u.status = 'approved'
                GROUP BY u.user_id, u.username, u.first_name
                ORDER BY
                    COUNT(*) FILTER (WHERE tr.response = 'yes') DESC,
                    COUNT(*) FILTER (WHERE tr.user_id IS NULL) ASC,
                    u.first_name NULLS LAST,
                    u.user_id
            """, (
                year,
                month,
            ))

            return cur.fetchall()

def is_training_cancelled_for_date(training_date):
    """
    Проверяет, была ли тренировка на эту дату отменена.

    Зачем:
    - если тренер отменил тренировку за день до неё,
      бот не должен заново создавать голосование при следующей авто-проверке;
    - если тренер отменил тренировку в день тренировки,
      контрольные и дневные напоминания должны остановиться.

    Важно:
    - ничего не удаляем;
    - ответы игроков не трогаем;
    - смотрим только факт отмены по дате start_time.
    """
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1
                FROM trainings
                WHERE DATE(start_time) = %s
                  AND cancelled_at IS NOT NULL
                LIMIT 1
            """, (
                training_date,
            ))

            return cur.fetchone() is not None

def mark_training_date_cancelled(
    start_time: datetime,
    cancelled_by_user_id: int | None = None,
    reason: str | None = None,
):
    """
    Создаёт запись-метку об отмене тренировки на конкретную дату.

    Зачем:
    - если тренер удалил будущую тренировку из календаря,
      но активного голосования по ней ещё нет;
    - бот должен запомнить, что эта дата отменена;
    - потом авто-логика не должна создавать новое голосование на эту дату.

    Важно:
    - активные тренировки НЕ трогаем;
    - старые ответы НЕ удаляем;
    - создаём неактивную запись в trainings с cancelled_at.
    """
    ensure_training_repository_schema()

    training_date = start_time.date()

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Если отмена на эту дату уже есть — дубль не создаём.
            cur.execute("""
                SELECT id
                FROM trainings
                WHERE DATE(start_time) = %s
                  AND cancelled_at IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
            """, (
                training_date,
            ))

            existing = cur.fetchone()

            if existing:
                return existing[0]

            cur.execute("""
                INSERT INTO trainings (
                    message_text,
                    start_time,
                    last_reminder_time,
                    stop_at,
                    is_active,
                    last_confirmation_time,
                    last_training_day_no_response_reminder_time,
                    last_coach_report_time,
                    is_custom,
                    created_by_user_id,
                    cancelled_at,
                    cancelled_by_user_id,
                    cancel_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
                RETURNING id
            """, (
                "Тренировка отменена.",
                start_time,
                None,
                start_time,
                False,
                None,
                None,
                None,
                False,
                cancelled_by_user_id,
                cancelled_by_user_id,
                reason,
            ))

            row = cur.fetchone()

        conn.commit()

    return row[0] if row else None