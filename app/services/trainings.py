import calendar
from datetime import date, datetime, time, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import (
    TRAINING_LOCATION_URL,
    TRAINING_TIME,
    TIMEZONE,
)
from app.db import get_connection
from app.repositories.trainings import (
    cancel_active_training,
    create_training,
    create_training_reminder_log,
    deactivate_training,
    get_active_training,
    get_month_attendance_rating_stats,
    get_month_no_response_stats,
    get_training_responses,
    get_user_response_for_training,
    is_training_active,
    is_training_cancelled_for_date,
    save_training_response,
    update_training_coach_report_time,
    update_training_day_no_response_reminder,
    update_training_last_confirmation,
    update_training_last_reminder,
)
from app.repositories.users import get_users_by_status
from app.services.access import is_broadcast_recipient
from app.utils.dates import get_month_name_prepositional


# День ДО стандартной тренировки:
# Воскресенье / Вторник / Четверг.
TRAINING_VOTE_WEEKDAYS = {6, 1, 3}

# Стандартные дни тренировок:
# Понедельник / Среда / Пятница.
TRAINING_DAYS = {0, 2, 4}

# Авто-напоминания за день до стандартной тренировки:
# с 09:00 до 23:00 каждый час.
TRAINING_AUTO_START_TIME = time(9, 0)
TRAINING_REPEAT_END_TIME = time(23, 0)
AUTO_REMINDER_REPEAT_MINUTES = 60

# В день тренировки:
# тем, кто не ответил на первичное голосование,
# напоминаем каждый час с 09:00 до 17:30.
TRAINING_DAY_NO_RESPONSE_START_TIME = time(9, 0)
TRAINING_DAY_NO_RESPONSE_END_TIME = time(17, 30)
TRAINING_DAY_NO_RESPONSE_REPEAT_MINUTES = 60

# Контрольное подтверждение в день тренировки:
# окно 18:00–18:59, чтобы не пропустить,
# если бот/сервер проснулся не ровно в 18:00.
TRAINING_CONFIRMATION_START_TIME = time(18, 0)
TRAINING_CONFIRMATION_END_TIME = time(18, 59)

# Авто-отчёт тренеру в день тренировки:
# окно 19:00–19:59, чтобы не пропустить,
# если бот/сервер проснулся не ровно в 19:00.
TRAINING_COACH_REPORT_START_TIME = time(19, 0)
TRAINING_COACH_REPORT_END_TIME = time(19, 59)

# Отчёт тренеру по игрокам, которые часто не отвечают.
# Проверка идёт каждые 5 минут через training_repeat_job,
# но фактическая отправка ограничена окном 12:00–12:59 и логом в БД.
NO_RESPONSE_STATS_REPORT_START_TIME = time(12, 0)
NO_RESPONSE_STATS_REPORT_END_TIME = time(12, 59)

# Чтобы отчёт не был слишком длинным в Telegram.
NO_RESPONSE_STATS_MAX_PLAYERS = 30

# Ежемесячный рейтинг посещаемости тренеру.
# Отправляется в последний день месяца в окне 13:00–13:59.
MONTH_ATTENDANCE_REPORT_START_TIME = time(13, 0)
MONTH_ATTENDANCE_REPORT_END_TIME = time(13, 59)

# Чтобы Telegram-сообщение не было слишком длинным.
MONTH_ATTENDANCE_MAX_PLAYERS = 40


def get_coach_ids_from_config() -> list[int]:
    """
    Берём список тренеров из app.config.COACH_IDS.

    Сделано через внутренний импорт, чтобы не сломать запуск,
    если в config.py переменная пока называется иначе или отсутствует.
    """
    try:
        from app.config import COACH_IDS
    except ImportError:
        return []

    if not COACH_IDS:
        return []

    if isinstance(COACH_IDS, str):
        raw_ids = COACH_IDS.replace(";", ",").split(",")
    else:
        raw_ids = COACH_IDS

    coach_ids = []

    for raw_id in raw_ids:
        try:
            coach_ids.append(int(str(raw_id).strip()))
        except (TypeError, ValueError):
            continue

    return coach_ids


def ensure_no_response_report_logs_schema():
    """
    Таблица логов для отчёта "кто часто не отвечает".

    Нужна, чтобы бот не отправлял один и тот же отчёт каждые 5 минут
    в течение окна 12:00–12:59.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS no_response_report_logs (
                    id SERIAL PRIMARY KEY,
                    report_date DATE NOT NULL,
                    report_type TEXT NOT NULL,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(report_date, report_type)
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_no_response_report_logs_date_type
                ON no_response_report_logs(report_date, report_type)
            """)

        conn.commit()


def was_no_response_report_sent(report_date: date, report_type: str) -> bool:
    """
    Проверяет, был ли уже отправлен отчёт за конкретную дату и тип.
    """
    ensure_no_response_report_logs_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1
                FROM no_response_report_logs
                WHERE report_date = %s
                  AND report_type = %s
                LIMIT 1
            """, (
                report_date,
                report_type,
            ))

            return cur.fetchone() is not None


def mark_no_response_report_sent(
    report_date: date,
    report_type: str,
    success_count: int,
    fail_count: int,
):
    """
    Фиксирует, что отчёт был отправлен.
    """
    ensure_no_response_report_logs_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO no_response_report_logs (
                    report_date,
                    report_type,
                    success_count,
                    fail_count
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (report_date, report_type)
                DO NOTHING
            """, (
                report_date,
                report_type,
                success_count,
                fail_count,
            ))

        conn.commit()


def ensure_month_attendance_report_logs_schema():
    """
    Таблица логов для ежемесячного отчёта посещаемости.

    Нужна, чтобы бот не отправлял один и тот же отчёт каждые 5 минут
    в последний день месяца.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS month_attendance_report_logs (
                    id SERIAL PRIMARY KEY,
                    report_date DATE NOT NULL,
                    report_type TEXT NOT NULL,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(report_date, report_type)
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_month_attendance_report_logs_date_type
                ON month_attendance_report_logs(report_date, report_type)
            """)

        conn.commit()


def was_month_attendance_report_sent(report_date: date, report_type: str) -> bool:
    """
    Проверяет, был ли уже отправлен отчёт посещаемости за этот месяц.
    """
    ensure_month_attendance_report_logs_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1
                FROM month_attendance_report_logs
                WHERE report_date = %s
                  AND report_type = %s
                LIMIT 1
            """, (
                report_date,
                report_type,
            ))

            return cur.fetchone() is not None


def mark_month_attendance_report_sent(
    report_date: date,
    report_type: str,
    success_count: int,
    fail_count: int,
):
    """
    Фиксирует отправку отчёта посещаемости.
    """
    ensure_month_attendance_report_logs_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO month_attendance_report_logs (
                    report_date,
                    report_type,
                    success_count,
                    fail_count
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (report_date, report_type)
                DO NOTHING
            """, (
                report_date,
                report_type,
                success_count,
                fail_count,
            ))

        conn.commit()


def get_no_response_report_type_for_today(now: datetime) -> str | None:
    """
    Отчёт отправляется:
    - 15 числа каждого месяца;
    - 30 числа каждого месяца;
    - если в месяце меньше 30 дней, то в последний день месяца.

    Пример:
    - январь: 15 и 30
    - февраль 2026: 15 и 28
    - февраль 2028: 15 и 29
    - апрель: 15 и 30
    """
    last_day = calendar.monthrange(now.year, now.month)[1]
    second_report_day = min(30, last_day)

    if now.day == 15:
        return "mid_month"

    if now.day == second_report_day:
        return "month_end"

    return None


def is_last_day_of_month(now: datetime) -> bool:
    """
    Проверяет последний день месяца.

    Работает умно:
    - февраль 28/29;
    - апрель 30;
    - май 31;
    - и так далее.
    """
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now.day == last_day


def is_within_no_response_stats_report_window(now: datetime) -> bool:
    """
    Отчёт по неответившим отправляем в окне 12:00–12:59.
    """
    return NO_RESPONSE_STATS_REPORT_START_TIME <= now.time() <= NO_RESPONSE_STATS_REPORT_END_TIME


def is_within_month_attendance_report_window(now: datetime) -> bool:
    """
    Отчёт посещаемости отправляем в последний день месяца
    в окне 13:00–13:59.
    """
    return MONTH_ATTENDANCE_REPORT_START_TIME <= now.time() <= MONTH_ATTENDANCE_REPORT_END_TIME


def unpack_training(active_training):
    """
    Поддерживает tuple из get_active_training().

    Поля:
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
    if not active_training:
        return None

    return {
        "id": active_training[0],
        "message_text": active_training[1],
        "start_time": active_training[2],
        "last_reminder_time": active_training[3],
        "stop_at": active_training[4],
        "is_active": active_training[5],
        "last_confirmation_time": active_training[6] if len(active_training) > 6 else None,
        "is_custom": active_training[7] if len(active_training) > 7 else False,
        "created_by_user_id": active_training[8] if len(active_training) > 8 else None,
        "last_training_day_no_response_reminder_time": active_training[9] if len(active_training) > 9 else None,
        "last_coach_report_time": active_training[10] if len(active_training) > 10 else None,
    }



def stop_cancelled_training_if_needed(training, source: str) -> bool:
    """
    Последняя защитная проверка перед любой рассылкой по тренировке.

    Если по локальной дате уже существует отмена, активная запись закрывается,
    а вызывающая функция прекращает отправку. Это защищает и от старых
    неконсистентных записей, оставшихся до исправления.
    """
    if not training:
        return True

    training_id = training.get("id")
    start_time = training.get("start_time")

    if not training_id or not start_time:
        return True

    training_date = start_time.astimezone(TIMEZONE).date()

    if not is_training_cancelled_for_date(training_date):
        return False

    deactivate_training(training_id)
    print(
        f"Training #{training_id} for {training_date} is cancelled. "
        f"{source} was skipped."
    )
    return True


def parse_training_time() -> time:
    """
    TRAINING_TIME обычно строка вида '21:00'.
    Поддерживаем также datetime.time.
    """
    if isinstance(TRAINING_TIME, time):
        return TRAINING_TIME

    value = str(TRAINING_TIME).strip()

    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue

    return time(21, 0)


def format_training_date_time(training_datetime: datetime | None) -> str:
    if not training_datetime:
        return f"сегодня в {TRAINING_TIME}"

    training_local = training_datetime.astimezone(TIMEZONE)
    return training_local.strftime("%d.%m.%Y в %H:%M")


def get_today_stop_at() -> datetime:
    """
    Конец окна авто-напоминаний за день до тренировки.
    """
    now = datetime.now(TIMEZONE)
    return datetime.combine(now.date(), TRAINING_REPEAT_END_TIME, tzinfo=TIMEZONE)


def get_next_training_datetime_from_vote_day(now: datetime) -> datetime:
    """
    Для стандартного расписания:
    Вс -> Пн
    Вт -> Ср
    Чт -> Пт
    """
    training_date = now.date() + timedelta(days=1)
    return datetime.combine(training_date, parse_training_time(), tzinfo=TIMEZONE)


def get_next_or_today_training_datetime(now: datetime) -> datetime:
    """
    Для ручной кнопки тренера, если активной тренировки нет:
    - если сегодня стандартный день тренировки, берём сегодня;
    - если сегодня день предварительного голосования, берём завтра;
    - иначе берём ближайший Пн/Ср/Пт.
    """
    training_time = parse_training_time()

    if now.weekday() in TRAINING_DAYS:
        return datetime.combine(now.date(), training_time, tzinfo=TIMEZONE)

    if now.weekday() in TRAINING_VOTE_WEEKDAYS:
        return get_next_training_datetime_from_vote_day(now)

    for offset in range(1, 8):
        candidate_date = now.date() + timedelta(days=offset)
        if candidate_date.weekday() in TRAINING_DAYS:
            return datetime.combine(candidate_date, training_time, tzinfo=TIMEZONE)

    return datetime.combine(now.date(), training_time, tzinfo=TIMEZONE)


def is_vote_day(now: datetime) -> bool:
    return now.weekday() in TRAINING_VOTE_WEEKDAYS


def is_training_day(now: datetime) -> bool:
    return now.weekday() in TRAINING_DAYS


def is_after_training_auto_start(now: datetime) -> bool:
    return now.time() >= TRAINING_AUTO_START_TIME


def is_within_auto_reminder_window(now: datetime) -> bool:
    """
    Авто-напоминания работают только для стандартного расписания:
    Вс / Вт / Чт, 09:00–23:00.
    """
    return (
        is_vote_day(now)
        and TRAINING_AUTO_START_TIME <= now.time() <= TRAINING_REPEAT_END_TIME
    )


def is_within_training_day_no_response_window(now: datetime) -> bool:
    """
    В день тренировки напоминаем тем, кто не ответил,
    с 09:00 до 17:30.

    Работает не по дню недели, а по start_time активной тренировки.
    Поэтому поддерживает и стандартные тренировки, и нестандартные.
    """
    return TRAINING_DAY_NO_RESPONSE_START_TIME <= now.time() <= TRAINING_DAY_NO_RESPONSE_END_TIME


def is_within_confirmation_window(now: datetime) -> bool:
    """
    Контрольное подтверждение работает каждый день,
    но реально отправится только если сегодня дата активной тренировки.
    """
    return TRAINING_CONFIRMATION_START_TIME <= now.time() <= TRAINING_CONFIRMATION_END_TIME


def is_within_coach_report_window(now: datetime) -> bool:
    """
    Авто-отчёт тренеру отправляется в день тренировки
    в окне 19:00–19:59.
    """
    return TRAINING_COACH_REPORT_START_TIME <= now.time() <= TRAINING_COACH_REPORT_END_TIME


def is_confirmation_day_for_active_training(start_time: datetime, now: datetime) -> bool:
    """
    Проверяет, что сегодня день активной тренировки.

    Работает:
    - для стандартных тренировок Пн/Ср/Пт;
    - для нестандартных тренировок, например воскресенье,
      если тренер вручную создал тренировку на воскресенье.
    """
    if not start_time:
        return False

    start_local = start_time.astimezone(TIMEZONE)
    return start_local.date() == now.date()


def is_today_training_active(active_training) -> bool:
    """
    Оставлено для совместимости со старым кодом.
    """
    data = unpack_training(active_training)

    if not data:
        return False

    return is_confirmation_day_for_active_training(
        data["start_time"],
        datetime.now(TIMEZONE),
    )


def is_active_training_for_vote_day(active_training, now: datetime) -> bool:
    """
    Проверяет, относится ли активная тренировка к текущему дню
    предварительного голосования по стандартному расписанию.
    """
    data = unpack_training(active_training)

    if not data:
        return False

    if data["is_custom"]:
        return False

    if not data["start_time"] or not data["is_active"]:
        return False

    start_local = data["start_time"].astimezone(TIMEZONE)
    expected_training_date = get_next_training_datetime_from_vote_day(now).date()

    return start_local.date() == expected_training_date


def was_auto_reminder_sent_recently(last_reminder_time: datetime | None, now: datetime) -> bool:
    """
    Авто-напоминание за день до тренировки должно уходить каждый час.

    Проверяем last_reminder_time только для auto_day_before.
    Ручная кнопка тренера, напоминание неответившим, контрольное подтверждение
    и авто-отчёт тренеру это поле не трогают.
    """
    if not last_reminder_time:
        return False

    last_local = last_reminder_time.astimezone(TIMEZONE)
    next_allowed = last_local + timedelta(minutes=AUTO_REMINDER_REPEAT_MINUTES)

    return now < next_allowed


def was_training_day_no_response_reminder_sent_recently(
    last_reminder_time: datetime | None,
    now: datetime,
) -> bool:
    """
    Напоминание в день тренировки для неответивших должно уходить каждый час.

    Это отдельное поле, чтобы не конфликтовать с:
    - last_reminder_time для авто-напоминаний за день до тренировки;
    - last_confirmation_time для контрольного подтверждения в 18:00;
    - last_coach_report_time для авто-отчёта тренеру;
    - ручной кнопкой тренера.
    """
    if not last_reminder_time:
        return False

    last_local = last_reminder_time.astimezone(TIMEZONE)
    next_allowed = last_local + timedelta(minutes=TRAINING_DAY_NO_RESPONSE_REPEAT_MINUTES)

    return now < next_allowed


def was_confirmation_sent_today(training, now: datetime) -> bool:
    """
    Контрольное подтверждение должно уходить один раз в день тренировки.
    """
    last_confirmation_time = training.get("last_confirmation_time")

    if not last_confirmation_time:
        return False

    last_local = last_confirmation_time.astimezone(TIMEZONE)
    return last_local.date() == now.date()


def was_coach_report_sent_today(training, now: datetime) -> bool:
    """
    Авто-отчёт тренеру должен уходить один раз в день тренировки.
    """
    last_report_time = training.get("last_coach_report_time")

    if not last_report_time:
        return False

    last_local = last_report_time.astimezone(TIMEZONE)
    return last_local.date() == now.date()


def build_training_message() -> str:
    return (
        f"Завтра тренировка в {TRAINING_TIME}.\n"
        f"Локация: {TRAINING_LOCATION_URL}\n"
        "Контрольный вопрос: ты придёшь на тренировку?"
    )


def build_today_training_message() -> str:
    return (
        f"Сегодня тренировка в {TRAINING_TIME}.\n"
        f"Локация: {TRAINING_LOCATION_URL}\n"
        "Контрольный вопрос: ты придёшь на тренировку?"
    )


def build_custom_training_message(training_datetime: datetime) -> str:
    training_local = training_datetime.astimezone(TIMEZONE)
    date_text = training_local.strftime("%d.%m.%Y")
    time_text = training_local.strftime("%H:%M")

    return (
        f"Тренировка {date_text} в {time_text}.\n"
        f"Локация: {TRAINING_LOCATION_URL}\n"
        "Контрольный вопрос: ты придёшь на тренировку?"
    )


def build_training_day_no_response_message(training_datetime: datetime | None = None) -> str:
    training_text = format_training_date_time(training_datetime)

    return (
        f"Напоминание о тренировке {training_text}.\n"
        f"Локация: {TRAINING_LOCATION_URL}\n\n"
        "Ты ещё не ответил на голосование.\n"
        "Подскажи, пожалуйста, ты будешь на тренировке?"
    )


def build_evening_training_message_for_player(
    previous_response: str | None,
    training_datetime: datetime | None = None,
) -> str:
    training_text = format_training_date_time(training_datetime)

    if previous_response == "yes":
        previous_text = "Ранее ты отметил, что придёшь."
    elif previous_response == "no":
        previous_text = "Ранее ты отметил, что не придёшь."
    else:
        previous_text = "Ты ещё не ответил по этой тренировке."

    return (
        f"Контрольное подтверждение по тренировке {training_text}.\n"
        f"Локация: {TRAINING_LOCATION_URL}\n\n"
        f"{previous_text}\n"
        "Подтверди, пожалуйста: ты точно будешь? 😅"
    )


def build_evening_training_message() -> str:
    """
    Оставлено для совместимости со старым кодом.
    """
    return (
        f"Сегодня тренировка в {TRAINING_TIME}.\n"
        f"Локация: {TRAINING_LOCATION_URL}\n\n"
        "Контрольное подтверждение:\n"
        "Ты сегодня точно будешь на тренировке? 😅"
    )


def build_coach_training_report_text(training) -> str:
    """
    Собирает авто-отчёт тренеру по активной тренировке.
    """
    training_id = training["id"]
    start_time = training["start_time"]

    approved_users = [
        row for row in get_users_by_status("approved")
        if is_broadcast_recipient(row[0])
    ]

    responses = get_training_responses(training_id)

    response_map = {
        user_id: response
        for user_id, username, first_name, response in responses
    }

    coming = []
    not_coming = []
    no_response = []

    for user_id, username, first_name in approved_users:
        name = first_name or str(user_id)

        if username:
            name += f" (@{username})"

        response = response_map.get(user_id)

        if response == "yes":
            coming.append(name)
        elif response == "no":
            not_coming.append(name)
        else:
            no_response.append(name)

    start_local = start_time.astimezone(TIMEZONE) if start_time else None

    if start_local:
        training_date_text = start_local.strftime("%d.%m.%Y")
        training_time_text = start_local.strftime("%H:%M")
    else:
        training_date_text = "сегодня"
        training_time_text = str(TRAINING_TIME)

    text = (
        f"📊 Итог по тренировке {training_date_text} в {training_time_text}\n\n"
        f"✅ Придут: {len(coming)}\n"
        f"❌ Не придут: {len(not_coming)}\n"
        f"⏳ Не ответили: {len(no_response)}\n"
    )

    if coming:
        text += "\n✅ Придут:\n"
        text += "\n".join(f"- {name}" for name in coming)

    if not_coming:
        text += "\n\n❌ Не придут:\n"
        text += "\n".join(f"- {name}" for name in not_coming)

    if no_response:
        text += "\n\n⏳ Не ответили:\n"
        text += "\n".join(f"- {name}" for name in no_response)
    else:
        text += "\n\nВсе игроки ответили ✅"

    return text


def build_month_no_response_report_text(
    report_date: date,
    report_type: str,
) -> str:
    """
    Формирует отчёт тренеру по игрокам, которые не отвечают на голосования.
    """
    stats = get_month_no_response_stats(
        year=report_date.year,
        month=report_date.month,
        until_date=report_date,
    )

    period_start = date(report_date.year, report_date.month, 1)
    period_text = f"{period_start.strftime('%d.%m.%Y')} — {report_date.strftime('%d.%m.%Y')}"

    if report_type == "mid_month":
        title = "⚠️ Промежуточный отчёт по неответившим"
    else:
        title = "⚠️ Итоговый отчёт по неответившим"

    if not stats:
        return (
            f"{title}\n\n"
            f"Период: {period_text}\n\n"
            "✅ Нет игроков, которые игнорировали голосования."
        )

    text = (
        f"{title}\n\n"
        f"Период: {period_text}\n\n"
        "Игроки, которые не отвечали на голосования:\n\n"
    )

    shown_count = 0

    for index, row in enumerate(stats, start=1):
        user_id, username, first_name, no_response_count, total_trainings = row

        name = first_name or str(user_id)

        if username:
            name += f" (@{username})"

        text += (
            f"{index}. {name} — "
            f"{no_response_count} из {total_trainings}\n"
        )

        shown_count += 1

        if shown_count >= NO_RESPONSE_STATS_MAX_PLAYERS:
            remaining = len(stats) - shown_count

            if remaining > 0:
                text += f"\nИ ещё игроков: {remaining}"
            break

    return text


def build_month_attendance_rating_report_text(report_date: date) -> str:
    """
    Формирует рейтинг посещаемости за месяц.

    Считаем:
    - Приду = посещение;
    - Не приду = не посещение;
    - Не ответил = не посещение;
    - отменённые тренировки не учитываются.
    """
    stats = get_month_attendance_rating_stats(
        year=report_date.year,
        month=report_date.month,
    )

    month_name = get_month_name_prepositional(
        datetime.combine(report_date, time(12, 0), tzinfo=TIMEZONE)
    )

    if not stats:
        return (
            f"📊 Посещаемость за {month_name} {report_date.year}\n\n"
            "За этот месяц нет данных по тренировкам."
        )

    total_trainings = stats[0][6] if stats else 0

    if total_trainings == 0:
        return (
            f"📊 Посещаемость за {month_name} {report_date.year}\n\n"
            "В этом месяце не было тренировок."
        )

    text = (
        f"📊 Посещаемость за {month_name} {report_date.year}\n\n"
        f"Всего тренировок за месяц: {total_trainings}\n\n"
    )

    shown_count = 0

    for index, row in enumerate(stats, start=1):
        (
            user_id,
            username,
            first_name,
            yes_count,
            no_count,
            no_response_count,
            total_count,
        ) = row

        yes_count = yes_count or 0
        no_count = no_count or 0
        no_response_count = no_response_count or 0
        total_count = total_count or total_trainings

        name = first_name or str(user_id)

        if username:
            name += f" (@{username})"

        text += f"{index}. {name} — {yes_count}/{total_count}"

        details = []

        if no_count:
            details.append(f"не придёт: {no_count}")

        if no_response_count:
            details.append(f"не ответил: {no_response_count}")

        if details:
            text += f" ({', '.join(details)})"

        text += "\n"

        shown_count += 1

        if shown_count >= MONTH_ATTENDANCE_MAX_PLAYERS:
            remaining = len(stats) - shown_count

            if remaining > 0:
                text += f"\nИ ещё игроков: {remaining}"
            break

    return text


def get_training_keyboard(training_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Приду", callback_data=f"training_yes_{training_id}"),
        InlineKeyboardButton("❌ Не приду", callback_data=f"training_no_{training_id}")
    ]])


def get_change_answer_keyboard(training_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔁 Изменить ответ", callback_data=f"change_training_answer_{training_id}")
    ]])


def get_change_answer_confirm_keyboard(training_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Да", callback_data=f"confirm_change_training_{training_id}"),
        InlineKeyboardButton("❌ Нет", callback_data=f"cancel_change_training_{training_id}")
    ]])


def get_or_create_training_for_vote_day(now: datetime):
    """
    Возвращает активную тренировку для текущего дня предварительного голосования.

    Если подходящей активной стандартной тренировки нет — создаёт новую.

    Важно:
    - если тренировка на эту дату была отменена тренером,
      новую голосовалку НЕ создаём;
    - если активная тренировка уже есть, но по этой дате есть отмена,
      активную тренировку закрываем;
    - ответы игроков не удаляем.
    """
    active_training = get_active_training()
    active_data = unpack_training(active_training)

    if active_data and active_data["is_custom"]:
        return None, False

    training_datetime = get_next_training_datetime_from_vote_day(now)
    training_date = training_datetime.date()

    if is_training_cancelled_for_date(training_date):
        if active_data and active_data.get("start_time"):
            active_start_local = active_data["start_time"].astimezone(TIMEZONE)

            if active_start_local.date() == training_date:
                deactivate_training(active_data["id"])

        print(
            f"Training for {training_date} is cancelled. "
            "Auto vote reminder will not be created."
        )
        return None, False

    if active_training and is_active_training_for_vote_day(active_training, now):
        return active_data, False

    if active_data and active_data["id"]:
        deactivate_training(active_data["id"])

    message_text = build_training_message()
    stop_at = get_today_stop_at()

    create_training(
        message_text=message_text,
        start_time=training_datetime,
        stop_at=stop_at,
        is_custom=False,
    )

    created_training = get_active_training()
    return unpack_training(created_training), True


def get_or_create_training_for_manual_reminder(now: datetime):
    """
    Ручная кнопка тренера работает в любое время.

    Важно:
    - если активная тренировка уже есть — используем её training_id;
    - если активной нет — создаём ближайшую стандартную тренировку;
    - если тренировка на эту дату отменена — НЕ создаём её заново;
    - training_responses не очищаем.
    """
    active_training = get_active_training()
    active_data = unpack_training(active_training)

    if active_data and active_data.get("start_time"):
        active_start_local = active_data["start_time"].astimezone(TIMEZONE)

        if is_training_cancelled_for_date(active_start_local.date()):
            deactivate_training(active_data["id"])
            print(
                f"Active training #{active_data['id']} is cancelled. "
                "Manual reminder will not be sent."
            )
            return None, False

        return active_data, False

    training_datetime = get_next_or_today_training_datetime(now)
    training_date = training_datetime.date()

    if is_training_cancelled_for_date(training_date):
        print(
            f"Training for {training_date} is cancelled. "
            "Manual reminder will not create a new vote."
        )
        return None, False

    if training_datetime.date() == now.date():
        message_text = build_today_training_message()
    else:
        message_text = build_training_message()

    stop_at = datetime.combine(
        now.date(),
        TRAINING_REPEAT_END_TIME,
        tzinfo=TIMEZONE,
    )

    create_training(
        message_text=message_text,
        start_time=training_datetime,
        stop_at=stop_at,
        is_custom=False,
    )

    created_training = get_active_training()
    return unpack_training(created_training), True


async def send_payment_reminder_by_month_text(context: ContextTypes.DEFAULT_TYPE):
    approved_users = get_users_by_status("approved")
    month_name = get_month_name_prepositional(datetime.now(TIMEZONE))
    message_text = (
        f"Добрый вечер, у вас настало время оплатить за тренировки в {month_name}. "
        f"Прошу сделать это."
    )

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except Exception:
            fail_count += 1

    return message_text, success_count, fail_count


async def send_auto_training_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Авто-напоминание за день до стандартной тренировки.

    Правило:
    - Воскресенье / Вторник / Четверг;
    - с 09:00 до 23:00;
    - каждый час;
    - только approved игрокам;
    - только тем, кто ещё НЕ ответил на голосование.

    Важно:
    - если игрок уже нажал "Приду" или "Не приду",
      повторное часовое напоминание ему не отправляется;
    - ответы в БД не удаляются;
    - training_id не меняется;
    - ручная кнопка тренера не ломается.
    """
    now = datetime.now(TIMEZONE)

    if not is_within_auto_reminder_window(now):
        return None

    training, created = get_or_create_training_for_vote_day(now)

    if not training:
        return None

    if stop_cancelled_training_if_needed(training, "Auto reminder"):
        return None

    training_id = training["id"]
    message_text = training["message_text"]
    last_reminder_time = training["last_reminder_time"]
    stop_at = training["stop_at"]

    if not created and was_auto_reminder_sent_recently(last_reminder_time, now):
        return None

    approved_users = get_users_by_status("approved")
    keyboard = get_training_keyboard(training_id)

    success_count = 0
    fail_count = 0
    skipped_answered_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        if not is_training_active(training_id):
            print(f"Training #{training_id} was cancelled during auto reminder; sending stopped.")
            break

        existing_response = get_user_response_for_training(training_id, user_id)

        if existing_response:
            skipped_answered_count += 1
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard,
            )
            success_count += 1
        except Exception as e:
            print(f"Ошибка авто-напоминания игроку {user_id}: {e}")
            fail_count += 1

    if not is_training_active(training_id):
        return None

    update_training_last_reminder(training_id, now)

    create_training_reminder_log(
        training_id=training_id,
        reminder_type="auto_day_before",
    )

    print(
        f"Training #{training_id}: auto reminder sent to "
        f"{success_count} players, skipped answered: {skipped_answered_count}, "
        f"failed: {fail_count}."
    )

    return {
        "training_id": training_id,
        "success_count": success_count,
        "fail_count": fail_count,
        "skipped_answered_count": skipped_answered_count,
        "stop_at": stop_at,
    }


async def send_training_day_no_response_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    В день тренировки напоминает тем, кто не ответил на первичное голосование.

    Правило:
    - только в день активной тренировки;
    - с 09:00 до 17:30;
    - каждый час;
    - только approved игрокам;
    - только тем, у кого нет ответа в training_responses;
    - не конфликтует с авто-напоминаниями за день до тренировки;
    - не конфликтует с контрольным подтверждением в 18:00;
    - не конфликтует с авто-отчётом тренеру в 19:00;
    - не трогает ручную кнопку тренера.
    """
    now = datetime.now(TIMEZONE)

    if not is_within_training_day_no_response_window(now):
        return None

    active_training = get_active_training()

    if not active_training:
        return None

    training = unpack_training(active_training)

    if not training:
        return None

    if stop_cancelled_training_if_needed(training, "Training-day reminder"):
        return None

    training_id = training["id"]
    start_time = training["start_time"]

    if not start_time:
        return None

    if not is_confirmation_day_for_active_training(start_time, now):
        return None

    last_no_response_reminder_time = training.get(
        "last_training_day_no_response_reminder_time"
    )

    if was_training_day_no_response_reminder_sent_recently(
        last_no_response_reminder_time,
        now,
    ):
        return None

    approved_users = get_users_by_status("approved")
    keyboard = get_training_keyboard(training_id)
    message_text = build_training_day_no_response_message(start_time)

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        if not is_training_active(training_id):
            print(f"Training #{training_id} was cancelled during training-day reminder; sending stopped.")
            break

        existing_response = get_user_response_for_training(training_id, user_id)

        if existing_response:
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard,
            )
            success_count += 1
        except Exception as e:
            print(f"Ошибка напоминания неответившему игроку {user_id}: {e}")
            fail_count += 1

    if not is_training_active(training_id):
        return None

    update_training_day_no_response_reminder(training_id, now)

    create_training_reminder_log(
        training_id=training_id,
        reminder_type="training_day_no_response",
    )

    print(
        f"Training #{training_id}: training day no-response reminder sent to "
        f"{success_count} players, failed: {fail_count}."
    )

    return {
        "training_id": training_id,
        "success_count": success_count,
        "fail_count": fail_count,
    }


async def send_coach_training_report(context: ContextTypes.DEFAULT_TYPE):
    """
    Авто-отчёт тренеру перед тренировкой.

    Правило:
    - только в день активной тренировки;
    - только в окне 19:00–19:59;
    - только один раз в день на конкретную тренировку;
    - игрокам ничего не отправляет;
    - старые голосования и ответы не трогает.
    """
    now = datetime.now(TIMEZONE)

    if not is_within_coach_report_window(now):
        return None

    active_training = get_active_training()

    if not active_training:
        return None

    training = unpack_training(active_training)

    if not training:
        return None

    if stop_cancelled_training_if_needed(training, "Coach report"):
        return None

    training_id = training["id"]
    start_time = training["start_time"]

    if not start_time:
        return None

    if not is_confirmation_day_for_active_training(start_time, now):
        return None

    if was_coach_report_sent_today(training, now):
        return None

    coach_ids = get_coach_ids_from_config()

    if not coach_ids:
        print("COACH_IDS is empty or not configured. Coach training report was not sent.")
        return None

    text = build_coach_training_report_text(training)

    success_count = 0
    fail_count = 0

    for coach_id in coach_ids:

        if not is_training_active(training_id):
            print(f"Training #{training_id} was cancelled during coach report; sending stopped.")
            break
        try:
            await context.bot.send_message(
                chat_id=coach_id,
                text=text,
            )
            success_count += 1
        except Exception as e:
            print(f"Ошибка отправки авто-отчёта тренеру {coach_id}: {e}")
            fail_count += 1

    if not is_training_active(training_id):
        return None

    if success_count > 0:
        update_training_coach_report_time(training_id, now)

        create_training_reminder_log(
            training_id=training_id,
            reminder_type="coach_training_report",
        )

    print(
        f"Training #{training_id}: coach report sent to "
        f"{success_count} coaches, failed: {fail_count}."
    )

    return {
        "training_id": training_id,
        "success_count": success_count,
        "fail_count": fail_count,
    }


async def send_monthly_no_response_report(context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет тренеру отчёт по игрокам, которые часто не отвечают.

    Правило:
    - 15 числа каждого месяца;
    - 30 числа каждого месяца;
    - если в месяце меньше 30 дней, то в последний день месяца;
    - отправка в окне 12:00–12:59;
    - только тренерам;
    - игрокам ничего не отправляется.
    """
    now = datetime.now(TIMEZONE)

    if not is_within_no_response_stats_report_window(now):
        return None

    report_type = get_no_response_report_type_for_today(now)

    if not report_type:
        return None

    report_date = now.date()

    if was_no_response_report_sent(report_date, report_type):
        return None

    coach_ids = get_coach_ids_from_config()

    if not coach_ids:
        print("COACH_IDS is empty or not configured. No-response report was not sent.")
        return None

    text = build_month_no_response_report_text(
        report_date=report_date,
        report_type=report_type,
    )

    success_count = 0
    fail_count = 0

    for coach_id in coach_ids:
        try:
            await context.bot.send_message(
                chat_id=coach_id,
                text=text,
            )
            success_count += 1
        except Exception as e:
            print(f"Ошибка отправки отчёта по неответившим тренеру {coach_id}: {e}")
            fail_count += 1

    if success_count > 0:
        mark_no_response_report_sent(
            report_date=report_date,
            report_type=report_type,
            success_count=success_count,
            fail_count=fail_count,
        )

    print(
        f"No-response report {report_date} / {report_type}: "
        f"sent to {success_count} coaches, failed: {fail_count}."
    )

    return {
        "report_date": report_date,
        "report_type": report_type,
        "success_count": success_count,
        "fail_count": fail_count,
    }


async def send_monthly_attendance_rating_report(context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет тренеру рейтинг посещаемости в последний день месяца.

    Правило:
    - только последний день месяца;
    - окно отправки 13:00–13:59;
    - только тренерам;
    - игрокам ничего не отправляется;
    - один раз в месяц.
    """
    now = datetime.now(TIMEZONE)

    if not is_last_day_of_month(now):
        return None

    if not is_within_month_attendance_report_window(now):
        return None

    report_date = now.date()
    report_type = "month_attendance_rating"

    if was_month_attendance_report_sent(report_date, report_type):
        return None

    coach_ids = get_coach_ids_from_config()

    if not coach_ids:
        print("COACH_IDS is empty or not configured. Month attendance report was not sent.")
        return None

    text = build_month_attendance_rating_report_text(report_date)

    success_count = 0
    fail_count = 0

    for coach_id in coach_ids:
        try:
            await context.bot.send_message(
                chat_id=coach_id,
                text=text,
            )
            success_count += 1
        except Exception as e:
            print(f"Ошибка отправки отчёта посещаемости тренеру {coach_id}: {e}")
            fail_count += 1

    if success_count > 0:
        mark_month_attendance_report_sent(
            report_date=report_date,
            report_type=report_type,
            success_count=success_count,
            fail_count=fail_count,
        )

    print(
        f"Month attendance report {report_date}: "
        f"sent to {success_count} coaches, failed: {fail_count}."
    )

    return {
        "report_date": report_date,
        "report_type": report_type,
        "success_count": success_count,
        "fail_count": fail_count,
    }


async def send_manual_training_reminder(
    context: ContextTypes.DEFAULT_TYPE,
    coach_user_id: int | None = None,
):
    """
    Ручная кнопка тренера "Напомнить о тренировке".

    Важно:
    - НЕ обновляет last_reminder_time;
    - НЕ обновляет last_confirmation_time;
    - НЕ обновляет last_training_day_no_response_reminder_time;
    - НЕ обновляет last_coach_report_time;
    - НЕ очищает training_responses;
    - НЕ мешает авто-напоминанию;
    - НЕ мешает контрольному подтверждению;
    - НЕ мешает авто-отчёту тренеру.
    """
    now = datetime.now(TIMEZONE)
    training, created = get_or_create_training_for_manual_reminder(now)

    if not training:
        return None

    if stop_cancelled_training_if_needed(training, "Manual reminder"):
        return None

    training_id = training["id"]
    message_text = training["message_text"]
    keyboard = get_training_keyboard(training_id)

    approved_users = get_users_by_status("approved")

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        if not is_training_active(training_id):
            print(f"Training #{training_id} was cancelled during manual reminder; sending stopped.")
            break

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard,
            )
            success_count += 1
        except Exception as e:
            print(f"Ошибка ручного напоминания игроку {user_id}: {e}")
            fail_count += 1

    if not is_training_active(training_id):
        return None

    create_training_reminder_log(
        training_id=training_id,
        reminder_type="manual_coach",
        sent_by_user_id=coach_user_id,
    )

    print(
        f"Training #{training_id}: manual coach reminder sent to "
        f"{success_count} players, failed: {fail_count}."
    )

    return {
        "training_id": training_id,
        "success_count": success_count,
        "fail_count": fail_count,
        "stop_at": training["stop_at"],
    }


async def create_custom_training_vote(
    context: ContextTypes.DEFAULT_TYPE,
    training_datetime: datetime,
    coach_user_id: int | None = None,
):
    """
    Создаёт голосование на нестандартную дату.

    Пример:
    тренер отменил пятницу и поставил тренировку на воскресенье.

    Что делает:
    - создаёт новую тренировку с новым training_id;
    - старая активная тренировка закрывается внутри create_training();
    - старые ответы не удаляет;
    - отправляет голосование всем approved игрокам.
    """
    training_datetime = training_datetime.astimezone(TIMEZONE)

    message_text = build_custom_training_message(training_datetime)

    stop_at = datetime.combine(
        training_datetime.date(),
        TRAINING_REPEAT_END_TIME,
        tzinfo=TIMEZONE,
    )

    training_id = create_training(
        message_text=message_text,
        start_time=training_datetime,
        stop_at=stop_at,
        created_by_user_id=coach_user_id,
        is_custom=True,
    )

    approved_users = get_users_by_status("approved")
    keyboard = get_training_keyboard(training_id)

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard,
            )
            success_count += 1
        except Exception as e:
            print(f"Ошибка отправки нестандартной тренировки игроку {user_id}: {e}")
            fail_count += 1

    create_training_reminder_log(
        training_id=training_id,
        reminder_type="custom_training_created",
        sent_by_user_id=coach_user_id,
    )

    return {
        "training_id": training_id,
        "success_count": success_count,
        "fail_count": fail_count,
        "start_time": training_datetime,
        "stop_at": stop_at,
    }


async def cancel_current_training_vote(
    coach_user_id: int | None = None,
    reason: str | None = None,
):
    """
    Отменяет текущую активную тренировку.

    Важно:
    - ответы не удаляются;
    - история остаётся;
    - активная тренировка просто закрывается.
    """
    cancelled_training_id = cancel_active_training(
        cancelled_by_user_id=coach_user_id,
        reason=reason,
    )

    if cancelled_training_id:
        create_training_reminder_log(
            training_id=cancelled_training_id,
            reminder_type="training_cancelled",
            sent_by_user_id=coach_user_id,
        )

    return cancelled_training_id


async def start_training_reminder(context: ContextTypes.DEFAULT_TYPE, force_send: bool = False):
    """
    Сохраняем старый интерфейс, чтобы coach.py/callbacks.py не сломались.

    force_send=True  -> ручное напоминание тренера.
    force_send=False -> авто-напоминание по расписанию.
    """
    if force_send:
        return await send_manual_training_reminder(context)

    return await send_auto_training_reminder(context)


async def ensure_training_started_if_needed(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TIMEZONE)

    if not is_within_auto_reminder_window(now):
        return

    await send_auto_training_reminder(context)


async def auto_start_training_job(context: ContextTypes.DEFAULT_TYPE):
    await send_auto_training_reminder(context)


async def repeat_training_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Единая периодическая проверка.

    1. За день до тренировки:
       авто-напоминание всем approved игрокам с 09:00 до 23:00 каждый час.

    2. В день тренировки:
       напоминание тем, кто не ответил, с 09:00 до 17:30 каждый час.

    3. В день тренировки:
       авто-отчёт тренеру с итогами в 19:00–19:59.

    4. 15 числа и 30 числа / последний день короткого месяца:
       отчёт тренеру по игрокам, которые часто не отвечают.

    5. В последний день месяца:
       рейтинг посещаемости тренеру.

    Эти логики используют разные поля/логи в БД и не конфликтуют.
    """
    await send_auto_training_reminder(context)
    await send_training_day_no_response_reminder(context)
    await send_coach_training_report(context)
    await send_monthly_no_response_report(context)
    await send_monthly_attendance_rating_report(context)


async def evening_training_confirmation_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Контрольное подтверждение в день тренировки.

    Работает для любой активной тренировки,
    у которой start_time.date() == today.

    Значит:
    - стандартные Пн/Ср/Пт работают;
    - нестандартное воскресенье тоже работает.
    """
    now = datetime.now(TIMEZONE)

    if not is_within_confirmation_window(now):
        return

    active_training = get_active_training()

    if not active_training:
        return

    training = unpack_training(active_training)

    if not training:
        return

    if stop_cancelled_training_if_needed(training, "Evening confirmation"):
        return

    training_id = training["id"]
    start_time = training["start_time"]

    if not start_time:
        return

    if not is_confirmation_day_for_active_training(start_time, now):
        return

    if was_confirmation_sent_today(training, now):
        return

    approved_users = get_users_by_status("approved")
    keyboard = get_training_keyboard(training_id)

    responses = get_training_responses(training_id)
    previous_response_map = {
        user_id: response
        for user_id, username, first_name, response in responses
    }

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if not is_broadcast_recipient(user_id):
            continue

        if not is_training_active(training_id):
            print(f"Training #{training_id} was cancelled during evening confirmation; sending stopped.")
            break

        previous_response = previous_response_map.get(user_id)
        text = build_evening_training_message_for_player(
            previous_response=previous_response,
            training_datetime=start_time,
        )

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard,
            )
            success_count += 1
        except Exception as e:
            print(f"Ошибка контрольного подтверждения игроку {user_id}: {e}")
            fail_count += 1

    if not is_training_active(training_id):
        return

    update_training_last_confirmation(training_id, now)

    create_training_reminder_log(
        training_id=training_id,
        reminder_type="training_day_confirmation",
    )

    print(
        f"Training #{training_id}: evening confirmation sent to "
        f"{success_count} players, failed: {fail_count}."
    )


def save_player_training_response(
    training_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    response: str,
):
    save_training_response(
        training_id=training_id,
        user_id=user_id,
        username=username,
        first_name=first_name,
        response=response,
    )


def build_training_responses_text():
    active_training = get_active_training()

    if not active_training:
        return "Сейчас нет активной тренировки."

    training = unpack_training(active_training)
    training_id = training["id"]

    approved_users = [
        row for row in get_users_by_status("approved")
        if is_broadcast_recipient(row[0])
    ]

    responses = get_training_responses(training_id)

    response_map = {
        user_id: response
        for user_id, username, first_name, response in responses
    }

    coming = []
    not_coming = []
    no_response = []

    for user_id, username, first_name in approved_users:
        name = first_name or str(user_id)

        if username:
            name += f" (@{username})"

        response = response_map.get(user_id)

        if response == "yes":
            coming.append(name)
        elif response == "no":
            not_coming.append(name)
        else:
            no_response.append(name)

    text = "Ответы на тренировку:\n\n"

    text += "✅ Придут:\n"
    text += "\n".join(coming) if coming else "Пока никто"
    text += "\n\n"

    text += "❌ Не придут:\n"
    text += "\n".join(not_coming) if not_coming else "Пока никто"
    text += "\n\n"

    text += "⏳ Не ответили:\n"
    text += "\n".join(no_response) if no_response else "Все ответили"

    return text


def schedule_training_repeat_job(application):
    existing_jobs = application.job_queue.get_jobs_by_name("training_repeat_job")

    if existing_jobs:
        return

    # Проверяем каждые 5 минут, чтобы не пропустить окно после рестарта.
    # Фактическая отправка авто-напоминаний, напоминаний неответившим,
    # авто-отчёта тренеру, отчёта по неответившим и рейтинга посещаемости
    # ограничена полями/логами в БД.
    application.job_queue.run_repeating(
        repeat_training_reminder_job,
        interval=timedelta(minutes=5),
        first=timedelta(seconds=30),
        name="training_repeat_job",
    )


def schedule_training_auto_start_job(application):
    existing_jobs = application.job_queue.get_jobs_by_name("training_auto_start_job")

    if existing_jobs:
        return

    application.job_queue.run_daily(
        auto_start_training_job,
        time=TRAINING_AUTO_START_TIME.replace(tzinfo=TIMEZONE),
        name="training_auto_start_job",
    )


def schedule_training_evening_confirmation_job(application):
    existing_jobs = application.job_queue.get_jobs_by_name("training_evening_confirmation_job")

    if existing_jobs:
        return

    # Не run_daily ровно в 18:00, а проверка каждые 5 минут.
    # Поэтому если бот проснулся в 18:13, контрольное всё равно уйдёт.
    application.job_queue.run_repeating(
        evening_training_confirmation_job,
        interval=timedelta(minutes=5),
        first=timedelta(seconds=45),
        name="training_evening_confirmation_job",
    )


def build_training_status_text(application) -> str:
    active_training = get_active_training()

    if not active_training:
        return (
            "📣 Статус напоминания о тренировке\n\n"
            "Статус: не запущено\n"
            "Следующий повтор: недоступен"
        )

    training = unpack_training(active_training)

    training_id = training["id"]
    start_time = training["start_time"]
    last_reminder_time = training["last_reminder_time"]
    stop_at = training["stop_at"]
    is_active = training["is_active"]
    last_confirmation_time = training["last_confirmation_time"]
    is_custom = training["is_custom"]
    last_no_response_reminder_time = training.get(
        "last_training_day_no_response_reminder_time"
    )
    last_coach_report_time = training.get("last_coach_report_time")

    approved_users = [
        row for row in get_users_by_status("approved")
        if is_broadcast_recipient(row[0])
    ]

    total_players = len(approved_users)

    responses = get_training_responses(training_id)

    approved_user_ids = {
        user_id
        for user_id, username, first_name in approved_users
    }

    answered_user_ids = {
        user_id
        for user_id, username, first_name, response in responses
        if user_id in approved_user_ids
    }

    answered_count = len(answered_user_ids)
    not_answered_count = max(total_players - answered_count, 0)

    now_local = datetime.now(TIMEZONE)

    start_time_local = start_time.astimezone(TIMEZONE) if start_time else None
    last_reminder_local = last_reminder_time.astimezone(TIMEZONE) if last_reminder_time else None
    stop_at_local = stop_at.astimezone(TIMEZONE) if stop_at else None
    last_confirmation_local = (
        last_confirmation_time.astimezone(TIMEZONE)
        if last_confirmation_time
        else None
    )
    last_no_response_reminder_local = (
        last_no_response_reminder_time.astimezone(TIMEZONE)
        if last_no_response_reminder_time
        else None
    )
    last_coach_report_local = (
        last_coach_report_time.astimezone(TIMEZONE)
        if last_coach_report_time
        else None
    )

    start_time_text = (
        start_time_local.strftime("%d.%m.%Y %H:%M")
        if start_time_local
        else "не указано"
    )

    last_reminder_text = (
        last_reminder_local.strftime("%d.%m.%Y %H:%M")
        if last_reminder_local
        else "не было"
    )

    stop_at_text = (
        stop_at_local.strftime("%d.%m.%Y %H:%M")
        if stop_at_local
        else "не указано"
    )

    last_confirmation_text = (
        last_confirmation_local.strftime("%d.%m.%Y %H:%M")
        if last_confirmation_local
        else "не было"
    )

    last_no_response_reminder_text = (
        last_no_response_reminder_local.strftime("%d.%m.%Y %H:%M")
        if last_no_response_reminder_local
        else "не было"
    )

    last_coach_report_text = (
        last_coach_report_local.strftime("%d.%m.%Y %H:%M")
        if last_coach_report_local
        else "не было"
    )

    status_text = "активно" if is_active else "завершено"
    training_type_text = "нестандартная" if is_custom else "стандартная"
    next_run_text = "недоступен"

    if is_active and is_vote_day(now_local) and now_local.time() <= TRAINING_REPEAT_END_TIME:
        if last_reminder_local:
            next_run = last_reminder_local + timedelta(minutes=AUTO_REMINDER_REPEAT_MINUTES)

            if next_run.time() <= TRAINING_REPEAT_END_TIME:
                next_run_text = next_run.strftime("%d.%m.%Y %H:%M")
        elif now_local.time() < TRAINING_AUTO_START_TIME:
            next_run = datetime.combine(
                now_local.date(),
                TRAINING_AUTO_START_TIME,
                tzinfo=TIMEZONE,
            )
            next_run_text = next_run.strftime("%d.%m.%Y %H:%M")
        else:
            next_run_text = "при ближайшей проверке"

    return (
        "📣 Статус напоминания о тренировке\n\n"
        f"Статус: {status_text}\n"
        f"Тип: {training_type_text}\n"
        f"Тренировка: {start_time_text}\n"
        f"Последнее авто-напоминание: {last_reminder_text}\n"
        f"Напоминание неответившим: {last_no_response_reminder_text}\n"
        f"Авто-напоминания до: {stop_at_text}\n"
        f"Контрольное подтверждение: {last_confirmation_text}\n"
        f"Авто-отчёт тренеру: {last_coach_report_text}\n"
        f"Следующий авто-повтор: {next_run_text}\n\n"
        f"Всего игроков: {total_players}\n"
        f"Ответили: {answered_count}\n"
        f"Не ответили: {not_answered_count}"
    )