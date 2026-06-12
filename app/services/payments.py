import calendar
from datetime import datetime, time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import (
    COACH_IDS,
    SUBSCRIPTION_END_REMINDER_DAYS,
    TIMEZONE,
)
from app.repositories.payments import (
    add_payment_history,
    get_overdue_subscription_end_with_users,
    get_payment_due_today_with_users,
    get_subscriptions_ending_soon_with_users,
    get_unpaid_subscriptions_with_users,
    open_monthly_payment_periods,
)
from app.repositories.users import add_or_update_user, get_user_by_id
from app.services.access import is_broadcast_recipient
from app.utils.dates import get_month_name_prepositional


def get_payment_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💸 Оплатил", callback_data="payment_claimed")
    ]])


def plural_days(days: int) -> str:
    if days % 10 == 1 and days % 100 != 11:
        return "день"
    if days % 10 in [2, 3, 4] and days % 100 not in [12, 13, 14]:
        return "дня"
    return "дней"


def build_subscription_ending_message(first_name: str | None, days_left: int) -> str:
    name = first_name or "игрок"
    days_word = plural_days(days_left)

    return (
        f"Добрый день, {name}. "
        f"Напоминаем вам, что действие вашего абонемента заканчивается через {days_left} {days_word}. "
        "Пожалуйста, не забудьте оплатить продление."
    )


def build_payment_reminder_message() -> str:
    month_name = get_month_name_prepositional(datetime.now(TIMEZONE))
    return (
        f"Добрый вечер. Напоминаем об оплате абонемента в {month_name}. "
        "Пожалуйста, произведите оплату."
    )


def build_new_player_payment_message(first_name: str | None) -> str:
    name = first_name or "игрок"
    return (
        "💳 Оплата абонемента\n\n"
        f"{name}, после одобрения заявки необходимо оплатить абонемент "
        "за текущий месяц.\n\n"
        "После оплаты нажми кнопку «💸 Оплатил»."
    )


def ensure_monthly_payment_periods_open(today) -> int:
    """
    Открывает новый месячный платёжный период за 5 дней до окончания.

    Функция безопасна для повторных запусков: уже открытый период повторно
    не меняется, а после подтверждения оплаты дата окончания переносится
    на следующий месяц.
    """
    opened_count = open_monthly_payment_periods(
        today=today,
        days_before=SUBSCRIPTION_END_REMINDER_DAYS,
    )

    if opened_count:
        print(f"Открыто новых платёжных периодов: {opened_count}")

    return opened_count


def is_last_day_of_month(today) -> bool:
    last_day = calendar.monthrange(today.year, today.month)[1]
    return today.day == last_day


def is_payment_collection_period(today) -> bool:
    """
    Период жёстких напоминаний:
    с 28 числа до последнего дня месяца включительно.
    """
    last_day = calendar.monthrange(today.year, today.month)[1]
    return 28 <= today.day <= last_day


def build_final_payment_warning_message() -> str:
    return (
        "Вы не оплатили месячный абонемент в команду по Американскому футболу "
        "«ФЕНИКСЫ». Сегодня вы будете удалены из команды."
    )


def build_removed_from_team_message() -> str:
    return "Вы были удалены из команды."

def get_unpaid_monthly_players(today):
    """
    Возвращает approved-игроков, которые не оплатили месячный абонемент.

    Берём из get_unpaid_subscriptions_with_users(today):
    - payment_day <= today.day
    - is_paid_current_period = FALSE
    - status = approved

    Дополнительно фильтруем только monthly.
    """
    subscriptions = get_unpaid_subscriptions_with_users(today)

    result = []

    for row in subscriptions:
        (
            user_id,
            username,
            first_name,
            payment_day,
            subscription_type,
            subscription_end_date,
            last_payment_date,
            is_paid_current_period,
            _has_custom_schedule,
            payment_claimed,
        ) = row

        if subscription_type != "monthly":
            continue

        if is_paid_current_period:
            continue

        result.append(row)

    return result

def build_removed_players_coach_report(removed_players: list[str]) -> str:
    if not removed_players:
        return (
            "✅ Автоудаление за неоплату выполнено.\n\n"
            "Удалённых игроков нет."
        )

    text = (
        "⚠️ Автоудаление игроков за неоплату\n\n"
        "Следующие игроки были удалены из команды:\n\n"
    )

    for index, player_name in enumerate(removed_players, start=1):
        text += f"{index}. {player_name}\n"

    return text

async def notify_coaches_about_removed_players(
    context: ContextTypes.DEFAULT_TYPE,
    removed_players: list[str],
):
    """
    Отправляет тренерам отчёт о том, кого бот удалил за неоплату.
    """
    if not COACH_IDS:
        print("COACH_IDS is empty. Removed players report was not sent.")
        return 0, 0

    message_text = build_removed_players_coach_report(removed_players)

    success_count = 0
    fail_count = 0

    for coach_id in COACH_IDS:
        try:
            await context.bot.send_message(
                chat_id=int(coach_id),
                text=message_text,
            )
            success_count += 1
        except Exception as e:
            print(f"Не удалось отправить отчёт об удалённых игроках тренеру {coach_id}: {e}")
            fail_count += 1

    return success_count, fail_count


def build_subscription_overdue_message(first_name: str | None, overdue_days: int) -> str:
    name = first_name or "игрок"
    days_word = plural_days(overdue_days)

    return (
        f"Добрый день, {name}. Напоминаем, что срок действия вашего абонемента уже истёк. "
        f"Просрочка: {overdue_days} {days_word}. Пожалуйста, оплатите продление."
    )


async def send_subscription_ending_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TIMEZONE)
    today = now.date()

    ensure_monthly_payment_periods_open(today)

    days_set = context.job.data["days"]
    subscriptions = get_subscriptions_ending_soon_with_users(
        today,
        days=SUBSCRIPTION_END_REMINDER_DAYS,
    )

    if not subscriptions:
        print("Нет игроков с абонементом, который скоро заканчивается.")
        return

    sent_count = 0

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        if not subscription_end_date:
            continue

        days_left = (subscription_end_date - today).days
        if days_left not in days_set:
            continue

        message_text = build_subscription_ending_message(first_name, days_left)

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=get_payment_keyboard(),
            )
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить напоминание игроку {user_id}: {e}")

    print(
        f"Отправлено напоминаний о скором окончании абонемента: {sent_count}. "
        f"Дни: {sorted(days_set)}"
    )


async def send_subscription_overdue_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TIMEZONE).date()
    ensure_monthly_payment_periods_open(today)
    subscriptions = get_overdue_subscription_end_with_users(today)

    if not subscriptions:
        print("Нет игроков с просроченным окончанием абонемента.")
        return

    sent_count = 0
    reply_markup = get_payment_keyboard()

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        if not subscription_end_date:
            continue

        overdue_days = (today - subscription_end_date).days
        if overdue_days <= 0:
            continue

        message_text = build_subscription_overdue_message(first_name, overdue_days)

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup,
            )
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить напоминание о просрочке абонемента игроку {user_id}: {e}")

    print(f"Отправлено напоминаний о просроченном окончании абонемента: {sent_count}")


async def send_manual_payment_reminders(context: ContextTypes.DEFAULT_TYPE):
    """
    Ручная кнопка тренера "Напомнить об оплате".

    Использует ту же выборку, что и автоматическое напоминание в день оплаты:
    - только approved игроки;
    - только payment_day = сегодняшний день;
    - только is_paid_current_period = FALSE.
    """
    today = datetime.now(TIMEZONE).date()
    ensure_monthly_payment_periods_open(today)
    subscriptions = get_payment_due_today_with_users(today)

    if not subscriptions:
        return 0, 0

    success_count = 0
    fail_count = 0
    message_text = build_payment_reminder_message()
    reply_markup = get_payment_keyboard()

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup,
            )
            success_count += 1
        except Exception as e:
            print(f"Не удалось отправить ручное напоминание об оплате игроку {user_id}: {e}")
            fail_count += 1

    return success_count, fail_count


async def send_payment_due_today_reminders(context: ContextTypes.DEFAULT_TYPE):
    """
    Автоматическое напоминание в день оплаты.

    Отправляется только approved-игрокам, у которых:
    - payment_day = сегодняшний день месяца;
    - is_paid_current_period = FALSE.

    Уже оплатившим игрокам сообщение не уйдёт.
    """
    today = datetime.now(TIMEZONE).date()
    ensure_monthly_payment_periods_open(today)
    subscriptions = get_payment_due_today_with_users(today)

    if not subscriptions:
        print("Нет игроков, у которых сегодня день оплаты.")
        return

    success_count = 0
    fail_count = 0
    message_text = build_payment_reminder_message()
    reply_markup = get_payment_keyboard()

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup,
            )
            success_count += 1
        except Exception as e:
            print(f"Не удалось отправить напоминание в день оплаты игроку {user_id}: {e}")
            fail_count += 1

    print(
        f"Отправлено напоминаний в день оплаты: {success_count}. "
        f"Ошибок: {fail_count}"
    )

async def send_payment_collection_hourly_reminders(context: ContextTypes.DEFAULT_TYPE):
    """
    С 28 числа до последнего дня месяца каждый час отправляет напоминание
    тем, кто не оплатил месячный абонемент.

    Логика текста:
    - если абонемент ещё не истёк — обычное напоминание об оплате;
    - если абонемент уже истёк — сообщение о просрочке;
    - в последний день месяца с 18:00 до 21:00 обычную/просроченную
      напоминалку не шлём, потому что в это время уходит финальное предупреждение.
    """
    now = datetime.now(TIMEZONE)
    today = now.date()

    if not is_payment_collection_period(today):
        return

    ensure_monthly_payment_periods_open(today)

    if is_last_day_of_month(today) and 18 <= now.hour <= 21:
        return

    subscriptions = get_unpaid_monthly_players(today)

    if not subscriptions:
        print("Нет игроков для часового напоминания об оплате.")
        return

    success_count = 0
    fail_count = 0
    reply_markup = get_payment_keyboard()

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        if subscription_end_date and subscription_end_date < today:
            overdue_days = (today - subscription_end_date).days
            message_text = build_subscription_overdue_message(
                first_name=first_name,
                overdue_days=overdue_days,
            )
        else:
            message_text = build_payment_reminder_message()

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup,
            )
            success_count += 1
        except Exception as e:
            print(f"Не удалось отправить часовое напоминание об оплате игроку {user_id}: {e}")
            fail_count += 1

    print(
        f"Часовых напоминаний об оплате отправлено: {success_count}. "
        f"Ошибок: {fail_count}"
    )

async def send_final_payment_warning_reminders(context: ContextTypes.DEFAULT_TYPE):
    """
    В последний день месяца с 18:00 до 21:00 каждый час отправляет
    финальное предупреждение только тем, кто не оплатил месячный абонемент.
    """
    today = datetime.now(TIMEZONE).date()

    if not is_last_day_of_month(today):
        return

    ensure_monthly_payment_periods_open(today)
    subscriptions = get_unpaid_monthly_players(today)

    if not subscriptions:
        print("Нет игроков для финального предупреждения об оплате.")
        return

    success_count = 0
    fail_count = 0
    message_text = build_final_payment_warning_message()
    reply_markup = get_payment_keyboard()

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
        if not is_broadcast_recipient(user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup,
            )
            success_count += 1
        except Exception as e:
            print(f"Не удалось отправить финальное предупреждение игроку {user_id}: {e}")
            fail_count += 1

    print(
        f"Финальных предупреждений отправлено: {success_count}. "
        f"Ошибок: {fail_count}"
    )

async def remove_unpaid_players_from_team(context: ContextTypes.DEFAULT_TYPE):
    """
    В последний день месяца удаляет из команды тех, кто не оплатил месячный абонемент.

    Важно:
    - физически из базы НЕ удаляем;
    - меняем status на removed_payment;
    - история ответов, оплат и тренировок остаётся;
    - игрок больше не считается approved и не получает командные рассылки;
    - тренеру отправляется отчёт со списком удалённых игроков.
    """
    today = datetime.now(TIMEZONE).date()

    if not is_last_day_of_month(today):
        return

    ensure_monthly_payment_periods_open(today)
    subscriptions = get_unpaid_monthly_players(today)

    if not subscriptions:
        print("Нет игроков для удаления из команды за неоплату.")
        await notify_coaches_about_removed_players(
            context=context,
            removed_players=[],
        )
        return

    success_count = 0
    fail_count = 0
    removed_players = []

    for (
        user_id,
        username,
        first_name,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) in subscriptions:
        existing_user = get_user_by_id(user_id)

        if not existing_user:
            continue

        saved_username = existing_user[1]
        saved_first_name = existing_user[2]

        player_name = saved_first_name or str(user_id)
        if saved_username:
            player_name += f" (@{saved_username})"

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=build_removed_from_team_message(),
            )
        except Exception as e:
            print(f"Не удалось отправить сообщение об удалении игроку {user_id}: {e}")

        try:
            add_or_update_user(
                user_id=user_id,
                username=saved_username,
                first_name=saved_first_name,
                status="removed_payment",
            )

            add_payment_history(
                user_id=user_id,
                action="removed_due_to_non_payment",
                comment="Игрок удалён из команды за неоплату месячного абонемента",
            )

            removed_players.append(player_name)
            success_count += 1
        except Exception as e:
            print(f"Не удалось удалить игрока {user_id} из команды за неоплату: {e}")
            fail_count += 1

    coach_success_count, coach_fail_count = await notify_coaches_about_removed_players(
        context=context,
        removed_players=removed_players,
    )

    print(
        f"Удалено из команды за неоплату: {success_count}. "
        f"Ошибок удаления: {fail_count}. "
        f"Отчёт тренерам отправлен: {coach_success_count}. "
        f"Ошибок отправки тренерам: {coach_fail_count}."
    )


def schedule_daily_payment_jobs(application):
    """
    Планировщик напоминаний по оплате.

    Старая логика сохранена:
    - за 5 и 4 дня до конца абонемента — 2 раза в день;
    - за 3 и 2 дня — 3 раза в день;
    - за 1 день — 6 раз в день;
    - просрочка — 1 раз в день.

    Новая логика:
    - в сам день оплаты в 10:00 отправляется отдельное напоминание
      только тем, кто ещё не оплатил текущий период.
    """
    reminder_schedule = [
        # За 5 и 4 дня — 2 раза в день
        ("subscription_end_reminders_5d_09", time(9, 0, tzinfo=TIMEZONE), {5}),
        ("subscription_end_reminders_5d_23", time(23, 0, tzinfo=TIMEZONE), {5}),
        ("subscription_end_reminders_4d_09", time(9, 0, tzinfo=TIMEZONE), {4}),
        ("subscription_end_reminders_4d_23", time(23, 0, tzinfo=TIMEZONE), {4}),

        # За 3 и 2 дня — 3 раза в день
        ("subscription_end_reminders_3d_09", time(9, 0, tzinfo=TIMEZONE), {3}),
        ("subscription_end_reminders_3d_14", time(14, 0, tzinfo=TIMEZONE), {3}),
        ("subscription_end_reminders_3d_20", time(20, 0, tzinfo=TIMEZONE), {3}),
        ("subscription_end_reminders_2d_09", time(9, 0, tzinfo=TIMEZONE), {2}),
        ("subscription_end_reminders_2d_14", time(14, 0, tzinfo=TIMEZONE), {2}),
        ("subscription_end_reminders_2d_20", time(20, 0, tzinfo=TIMEZONE), {2}),

        # За 1 день — 6 раз в день
        ("subscription_end_reminders_1d_09", time(9, 0, tzinfo=TIMEZONE), {1}),
        ("subscription_end_reminders_1d_11", time(11, 0, tzinfo=TIMEZONE), {1}),
        ("subscription_end_reminders_1d_14", time(14, 0, tzinfo=TIMEZONE), {1}),
        ("subscription_end_reminders_1d_18", time(18, 0, tzinfo=TIMEZONE), {1}),
        ("subscription_end_reminders_1d_20", time(20, 0, tzinfo=TIMEZONE), {1}),
        ("subscription_end_reminders_1d_23_30", time(23, 30, tzinfo=TIMEZONE), {1}),
    ]

    payment_collection_hourly_schedule = [
        ("payment_collection_hourly_10", time(10, 0, tzinfo=TIMEZONE)),
        ("payment_collection_hourly_11", time(11, 0, tzinfo=TIMEZONE)),
        ("payment_collection_hourly_12", time(12, 0, tzinfo=TIMEZONE)),
        ("payment_collection_hourly_13", time(13, 0, tzinfo=TIMEZONE)),
        ("payment_collection_hourly_14", time(14, 0, tzinfo=TIMEZONE)),
        ("payment_collection_hourly_15", time(15, 0, tzinfo=TIMEZONE)),
        ("payment_collection_hourly_16", time(16, 0, tzinfo=TIMEZONE)),
        ("payment_collection_hourly_17", time(17, 0, tzinfo=TIMEZONE)),
        ("payment_collection_hourly_18", time(18, 0, tzinfo=TIMEZONE)),
        ("payment_collection_hourly_19", time(19, 0, tzinfo=TIMEZONE)),
        ("payment_collection_hourly_20", time(20, 0, tzinfo=TIMEZONE)),
    ]

    for job_name, job_time in payment_collection_hourly_schedule:
        existing_jobs = application.job_queue.get_jobs_by_name(job_name)
        if existing_jobs:
            continue

        application.job_queue.run_daily(
            send_payment_collection_hourly_reminders,
            time=job_time,
            name=job_name,
        )

    final_payment_warning_schedule = [
        ("final_payment_warning_18", time(18, 0, tzinfo=TIMEZONE)),
        ("final_payment_warning_19", time(19, 0, tzinfo=TIMEZONE)),
        ("final_payment_warning_20", time(20, 0, tzinfo=TIMEZONE)),
        ("final_payment_warning_21", time(21, 0, tzinfo=TIMEZONE)),
    ]

    for job_name, job_time in final_payment_warning_schedule:
        existing_jobs = application.job_queue.get_jobs_by_name(job_name)
        if existing_jobs:
            continue

        application.job_queue.run_daily(
            send_final_payment_warning_reminders,
            time=job_time,
            name=job_name,
        )

    existing_remove_unpaid_jobs = application.job_queue.get_jobs_by_name("remove_unpaid_players_from_team")
    if not existing_remove_unpaid_jobs:
        application.job_queue.run_daily(
            remove_unpaid_players_from_team,
            time=time(21, 30, tzinfo=TIMEZONE),
            name="remove_unpaid_players_from_team",
        )

    for job_name, job_time, job_days in reminder_schedule:
        existing_jobs = application.job_queue.get_jobs_by_name(job_name)
        if existing_jobs:
            continue

        application.job_queue.run_daily(
            send_subscription_ending_reminders,
            time=job_time,
            data={"days": job_days},
            name=job_name,
        )

    existing_overdue_jobs = application.job_queue.get_jobs_by_name("subscription_overdue_reminders")
    if not existing_overdue_jobs:
        application.job_queue.run_daily(
            send_subscription_overdue_reminders,
            time=time(12, 30, tzinfo=TIMEZONE),
            name="subscription_overdue_reminders",
        )