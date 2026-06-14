from datetime import date, datetime, time, timedelta

from app.config import TIMEZONE
from app.db import get_connection


def _get_local_day_bounds(training_date: date) -> tuple[datetime, datetime]:
    """Возвращает границы локального дня в TIMEZONE для безопасного поиска TIMESTAMPTZ."""
    day_start = datetime.combine(training_date, time.min, tzinfo=TIMEZONE)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


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
                  AND cancelled_at IS NULL
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



def is_training_active(training_id: int) -> bool:
    """Проверяет, что конкретная тренировка всё ещё активна и не отменена."""
    ensure_training_repository_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1
                FROM trainings
                WHERE id = %s
                  AND is_active = TRUE
                  AND cancelled_at IS NULL
                LIMIT 1
            """, (training_id,))
            return cur.fetchone() is not None


def cancel_trainings_for_date(
    training_date: date,
    cancelled_by_user_id: int | None = None,
    reason: str | None = None,
) -> list[int]:
    """
    Отменяет ВСЕ записи trainings за указанную локальную дату.

    Это основной предохранитель: даже если из-за старой ошибки или гонки
    в базе осталось несколько активных записей, все они становятся
    неактивными, а фоновые напоминания прекращаются.
    """
    ensure_training_repository_schema()
    day_start, day_end = _get_local_day_bounds(training_date)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trainings
                SET
                    is_active = FALSE,
                    cancelled_at = COALESCE(cancelled_at, NOW()),
                    cancelled_by_user_id = COALESCE(cancelled_by_user_id, %s),
                    cancel_reason = COALESCE(cancel_reason, %s)
                WHERE start_time >= %s
                  AND start_time < %s
                RETURNING id
            """, (
                cancelled_by_user_id,
                reason,
                day_start,
                day_end,
            ))
            rows = cur.fetchall()

        conn.commit()

    return [row[0] for row in rows]

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

def is_training_cancelled_for_date(training_date: date) -> bool:
    """
    Проверяет наличие отмены по локальной дате TIMEZONE.

    Используются границы локального дня, поэтому результат не зависит
    от timezone PostgreSQL/Render.
    """
    ensure_training_repository_schema()
    day_start, day_end = _get_local_day_bounds(training_date)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH cancellation_marker AS (
                    SELECT EXISTS (
                        SELECT 1
                        FROM trainings
                        WHERE start_time >= %s
                          AND start_time < %s
                          AND cancelled_at IS NOT NULL
                    ) AS exists_marker
                ),
                schedule_state AS (
                    SELECT
                        COUNT(*) AS total_rows,
                        COUNT(*) FILTER (WHERE is_active = TRUE) AS active_rows
                    FROM training_schedule
                    WHERE training_date = %s
                )
                SELECT
                    cancellation_marker.exists_marker
                    OR (schedule_state.total_rows > 0 AND schedule_state.active_rows = 0)
                FROM cancellation_marker, schedule_state
            """, (day_start, day_end, training_date))

            row = cur.fetchone()
            return bool(row and row[0])


def mark_training_date_cancelled(
    start_time: datetime,
    cancelled_by_user_id: int | None = None,
    reason: str | None = None,
):
    """
    Надёжно отменяет тренировку на конкретную дату.

    1. Закрывает ВСЕ существующие записи trainings за эту локальную дату.
    2. Если записей ещё нет, создаёт неактивную метку отмены.
    3. Ответы игроков и история не удаляются.
    """
    ensure_training_repository_schema()

    if start_time.tzinfo is None:
        local_start_time = start_time.replace(tzinfo=TIMEZONE)
    else:
        local_start_time = start_time.astimezone(TIMEZONE)

    training_date = local_start_time.date()
    cancelled_ids = cancel_trainings_for_date(
        training_date=training_date,
        cancelled_by_user_id=cancelled_by_user_id,
        reason=reason,
    )

    if cancelled_ids:
        return max(cancelled_ids)

    with get_connection() as conn:
        with conn.cursor() as cur:
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
                VALUES (%s, %s, NULL, %s, FALSE, NULL, NULL, NULL, FALSE, %s, NOW(), %s, %s)
                RETURNING id
            """, (
                "Тренировка отменена.",
                local_start_time,
                local_start_time,
                cancelled_by_user_id,
                cancelled_by_user_id,
                reason,
            ))
            row = cur.fetchone()

        conn.commit()

    return row[0] if row else None
