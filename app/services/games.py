from datetime import date, datetime

from app.db import get_connection


def save_game_vote_response(
    game_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    response: str,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO game_vote_responses (
                    game_id,
                    user_id,
                    username,
                    first_name,
                    response
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (game_id, user_id)
                DO UPDATE SET
                    username = COALESCE(EXCLUDED.username, game_vote_responses.username),
                    first_name = COALESCE(EXCLUDED.first_name, game_vote_responses.first_name),
                    response = EXCLUDED.response,
                    updated_at = NOW()
                """,
                (
                    game_id,
                    user_id,
                    username,
                    first_name,
                    response,
                ),
            )
        conn.commit()


def get_game_vote_response(game_id: int, user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT response
                FROM game_vote_responses
                WHERE game_id = %s
                  AND user_id = %s
                """,
                (
                    game_id,
                    user_id,
                ),
            )
            row = cur.fetchone()
            return row[0] if row else None


def get_game_vote_responses(game_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, username, first_name, response
                FROM game_vote_responses
                WHERE game_id = %s
                ORDER BY user_id
                """,
                (game_id,),
            )
            return cur.fetchall()


def get_game_vote_state(game_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    vote_date,
                    last_reminder_time,
                    report_sent_at
                FROM game_vote_state
                WHERE game_id = %s
                """,
                (game_id,),
            )
            return cur.fetchone()


def update_game_vote_last_reminder(
    game_id: int,
    vote_date: date,
    reminder_time: datetime,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO game_vote_state (
                    game_id,
                    vote_date,
                    last_reminder_time
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (game_id)
                DO UPDATE SET
                    vote_date = EXCLUDED.vote_date,
                    last_reminder_time = EXCLUDED.last_reminder_time,
                    updated_at = NOW()
                """,
                (
                    game_id,
                    vote_date,
                    reminder_time,
                ),
            )
        conn.commit()


def mark_game_vote_report_sent(
    game_id: int,
    vote_date: date,
    report_time: datetime,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO game_vote_state (
                    game_id,
                    vote_date,
                    report_sent_at
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (game_id)
                DO UPDATE SET
                    vote_date = EXCLUDED.vote_date,
                    report_sent_at = EXCLUDED.report_sent_at,
                    updated_at = NOW()
                """,
                (
                    game_id,
                    vote_date,
                    report_time,
                ),
            )
        conn.commit()
from datetime import date, datetime, time, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import COACH_IDS, TIMEZONE
from app.repositories.game_schedule import get_upcoming_game_schedule
from app.repositories.game_votes import (
    get_game_vote_response,
    get_game_vote_responses,
    get_game_vote_state,
    mark_game_vote_report_sent,
    update_game_vote_last_reminder,
)
from app.repositories.users import get_user_by_id, get_users_by_status


GAME_VOTE_DAYS_BEFORE = 2
GAME_REMINDER_REPEAT_MINUTES = 60

GAME_REPORT_START_TIME = time(0, 0)
GAME_REPORT_END_TIME = time(0, 59, 59)


def get_coach_ids() -> list[int]:
    result = []

    for raw_id in COACH_IDS:
        try:
            result.append(int(str(raw_id).strip()))
        except (TypeError, ValueError):
            continue

    return result


def get_game_vote_recipients() -> list[tuple[int, str | None, str | None]]:
    """
    Возвращает единый список участников голосования:
    - approved-игроки;
    - тренеры из COACH_IDS.

    Повторы по user_id удаляются.
    """
    recipients: dict[int, tuple[str | None, str | None]] = {}

    for user_id, username, first_name in get_users_by_status("approved"):
        recipients[int(user_id)] = (username, first_name)

    for coach_id in get_coach_ids():
        existing_user = get_user_by_id(coach_id)

        if existing_user:
            recipients[coach_id] = (
                existing_user[1],
                existing_user[2],
            )
        else:
            recipients.setdefault(
                coach_id,
                (None, f"Тренер {coach_id}"),
            )

    return [
        (user_id, username, first_name)
        for user_id, (username, first_name) in recipients.items()
    ]


def get_games_for_vote_date(vote_date: date):
    target_game_date = vote_date + timedelta(days=GAME_VOTE_DAYS_BEFORE)

    return [
        row
        for row in get_upcoming_game_schedule()
        if row[5] and row[1] == target_game_date
    ]


def get_game_vote_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ Буду",
            callback_data=f"game_vote_yes_{game_id}",
        ),
        InlineKeyboardButton(
            "❌ Не буду",
            callback_data=f"game_vote_no_{game_id}",
        ),
    ]])


def build_game_vote_message(game) -> str:
    (
        game_id,
        game_date,
        game_time,
        opponent_name,
        comment,
        is_active,
        created_at,
    ) = game

    text = (
        "🏆 Голосование по матчу\n\n"
        f"Дата: {game_date.strftime('%d.%m.%Y')}\n"
        f"Время: {game_time.strftime('%H:%M')}\n"
        f"Соперник: {opponent_name}\n"
    )

    if comment:
        text += f"Место проведения: {comment}\n"

    text += "\nТы будешь на матче?"

    return text


def was_game_reminder_sent_recently(
    last_reminder_time: datetime | None,
    now: datetime,
) -> bool:
    if not last_reminder_time:
        return False

    last_local = last_reminder_time.astimezone(TIMEZONE)
    next_allowed = last_local + timedelta(
        minutes=GAME_REMINDER_REPEAT_MINUTES
    )

    return now < next_allowed


def is_game_report_window(now: datetime) -> bool:
    return GAME_REPORT_START_TIME <= now.time() <= GAME_REPORT_END_TIME


def format_participant_name(
    user_id: int,
    username: str | None,
    first_name: str | None,
) -> str:
    name = first_name or str(user_id)

    if username:
        name += f" (@{username})"

    return name


def build_game_vote_report_text(game) -> str:
    (
        game_id,
        game_date,
        game_time,
        opponent_name,
        comment,
        is_active,
        created_at,
    ) = game

    recipients = get_game_vote_recipients()
    responses = get_game_vote_responses(game_id)

    response_map = {
        user_id: response
        for user_id, username, first_name, response in responses
    }

    coming = []
    not_coming = []
    no_response = []

    for user_id, username, first_name in recipients:
        name = format_participant_name(
            user_id=user_id,
            username=username,
            first_name=first_name,
        )

        response = response_map.get(user_id)

        if response == "yes":
            coming.append(name)
        elif response == "no":
            not_coming.append(name)
        else:
            no_response.append(name)

    text = (
        "📊 Итог голосования по матчу\n\n"
        f"Дата: {game_date.strftime('%d.%m.%Y')}\n"
        f"Время: {game_time.strftime('%H:%M')}\n"
        f"Соперник: {opponent_name}\n\n"
        f"✅ Будут: {len(coming)}\n"
        f"❌ Не будут: {len(not_coming)}\n"
        f"⏳ Не ответили: {len(no_response)}\n"
    )

    if coming:
        text += "\n✅ Будут:\n"
        text += "\n".join(f"- {name}" for name in coming)

    if not_coming:
        text += "\n\n❌ Не будут:\n"
        text += "\n".join(f"- {name}" for name in not_coming)

    if no_response:
        text += "\n\n⏳ Не ответили:\n"
        text += "\n".join(f"- {name}" for name in no_response)
    else:
        text += "\n\nВсе участники проголосовали ✅"

    return text


async def send_game_vote_reminders(
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    За два дня до матча:
    - первая отправка происходит при ближайшей проверке после запуска;
    - повтор — не чаще одного раза в час;
    - сообщение получают approved-игроки и тренеры;
    - ответившие больше не получают напоминания.
    """
    now = datetime.now(TIMEZONE)
    vote_date = now.date()
    games = get_games_for_vote_date(vote_date)

    if not games:
        return None

    recipients = get_game_vote_recipients()
    results = []

    for game in games:
        game_id = game[0]
        state = get_game_vote_state(game_id)

        last_reminder_time = state[1] if state else None
        report_sent_at = state[2] if state else None

        if report_sent_at:
            continue

        if was_game_reminder_sent_recently(last_reminder_time, now):
            continue

        message_text = build_game_vote_message(game)
        keyboard = get_game_vote_keyboard(game_id)

        success_count = 0
        fail_count = 0
        skipped_answered_count = 0

        for user_id, username, first_name in recipients:
            existing_response = get_game_vote_response(
                game_id=game_id,
                user_id=user_id,
            )

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
                print(
                    f"Ошибка игрового напоминания пользователю "
                    f"{user_id}: {e}"
                )
                fail_count += 1

        update_game_vote_last_reminder(
            game_id=game_id,
            vote_date=vote_date,
            reminder_time=now,
        )

        print(
            f"Game #{game_id}: reminder sent to {success_count}, "
            f"skipped answered: {skipped_answered_count}, "
            f"failed: {fail_count}."
        )

        results.append({
            "game_id": game_id,
            "success_count": success_count,
            "fail_count": fail_count,
            "skipped_answered_count": skipped_answered_count,
        })

    return results or None


async def send_game_vote_reports(
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    В 00:00–00:59 после дня голосования отправляет тренерам итог.

    Например:
    - голосование: 12.06;
    - отчёт: 13.06 в 00:00;
    - матч: 14.06.
    """
    now = datetime.now(TIMEZONE)

    if not is_game_report_window(now):
        return None

    vote_date = now.date() - timedelta(days=1)
    games = get_games_for_vote_date(vote_date)
    coach_ids = get_coach_ids()

    if not games or not coach_ids:
        return None

    results = []

    for game in games:
        game_id = game[0]
        state = get_game_vote_state(game_id)
        report_sent_at = state[2] if state else None

        if report_sent_at:
            continue

        text = build_game_vote_report_text(game)

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
                print(
                    f"Ошибка отправки игрового отчёта тренеру "
                    f"{coach_id}: {e}"
                )
                fail_count += 1

        if success_count > 0:
            mark_game_vote_report_sent(
                game_id=game_id,
                vote_date=vote_date,
                report_time=now,
            )

        print(
            f"Game #{game_id}: report sent to {success_count} coaches, "
            f"failed: {fail_count}."
        )

        results.append({
            "game_id": game_id,
            "success_count": success_count,
            "fail_count": fail_count,
        })

    return results or None


async def game_vote_job(
    context: ContextTypes.DEFAULT_TYPE,
):
    await send_game_vote_reminders(context)
    await send_game_vote_reports(context)


def schedule_game_vote_jobs(application):
    existing_jobs = application.job_queue.get_jobs_by_name(
        "game_vote_job"
    )

    if existing_jobs:
        return

    application.job_queue.run_repeating(
        game_vote_job,
        interval=timedelta(minutes=5),
        first=timedelta(seconds=20),
        name="game_vote_job",
    )
