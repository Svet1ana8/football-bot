from datetime import datetime, date, time
import calendar

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import TIMEZONE, TRAINING_VOTE_CLOSE_TIME, TRAINING_REMINDER_REPEAT_MINUTES
from app.handlers.common import deny_access
from app.keyboards import (
    get_approved_player_menu,
    get_coach_menu,
    get_payments_menu,
    get_training_schedule_menu,
)
from app.repositories.payments import (
    get_all_payment_history,
    get_all_subscriptions,
    get_subscriptions_ending_soon,
    get_unpaid_subscriptions,
    get_unpaid_subscriptions_with_users,
    set_subscription_type,
)
from app.repositories.training_schedule import (
    add_training_schedule,
    deactivate_training_schedule,
    get_training_schedule_by_id,
    get_upcoming_training_schedule,
)
from app.repositories.trainings import get_month_attendance_stats
from app.repositories.users import (
    add_or_update_user,
    get_user_by_id,
    get_users_by_status,
)
from app.services.access import is_broadcast_recipient, is_coach
from app.services.payments import (
    send_manual_payment_reminders,
    send_subscription_ending_reminders,
)
from app.services.trainings import (
    build_training_responses_text,
    build_training_status_text,
    schedule_training_repeat_job,
    start_training_reminder,
)


def get_weekday_name(dt: date) -> str:
    weekdays = {
        0: "Понедельник",
        1: "Вторник",
        2: "Среда",
        3: "Четверг",
        4: "Пятница",
        5: "Суббота",
        6: "Воскресенье",
    }
    return weekdays[dt.weekday()]


def format_training_schedule_row(training_date, training_time, comment=None) -> str:
    text = f"{get_weekday_name(training_date)} — {training_date.strftime('%d.%m.%Y')}, {training_time.strftime('%H:%M')}"
    if comment:
        text += f"\nКомментарий: {comment}"
    return text


def build_training_action_keyboard(schedule_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🗑 Удалить", callback_data=f"training_delete_{schedule_id}"),
            InlineKeyboardButton("📅 Перенести", callback_data=f"training_transfer_{schedule_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_month_dates_keyboard(year: int, month: int, prefix: str) -> InlineKeyboardMarkup:
    _, last_day = calendar.monthrange(year, month)

    rows = []
    current_row = []

    for day in range(1, last_day + 1):
        dt = date(year, month, day)
        current_row.append(
            InlineKeyboardButton(
                str(day),
                callback_data=f"{prefix}_{dt.isoformat()}",
            )
        )

        if len(current_row) == 4:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    rows.append([InlineKeyboardButton("✍️ Выбрать дату", callback_data=f"{prefix}_manual")])
    return InlineKeyboardMarkup(rows)


def build_existing_trainings_keyboard(schedule, callback_prefix: str) -> list[tuple[str, InlineKeyboardMarkup]]:
    months = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }

    grouped = {}
    for schedule_id, training_date, training_time, comment, is_active, created_at in schedule:
        key = (training_date.year, training_date.month)
        grouped.setdefault(key, []).append((schedule_id, training_date, training_time, comment))

    result = []

    for (year, month), items in grouped.items():
        rows = []
        current_row = []

        for schedule_id, training_date, training_time, comment in items:
            current_row.append(
                InlineKeyboardButton(
                    str(training_date.day),
                    callback_data=f"{callback_prefix}_{schedule_id}",
                )
            )

            if len(current_row) == 4:
                rows.append(current_row)
                current_row = []

        if current_row:
            rows.append(current_row)

        title = f"{months[month]} {year}"
        result.append((title, InlineKeyboardMarkup(rows)))

    return result


def build_existing_trainings_text(schedule) -> str:
    if not schedule:
        return "📅 Тренировок пока нет."

    months = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }

    grouped = {}
    for schedule_id, training_date, training_time, comment, is_active, created_at in schedule:
        key = (training_date.year, training_date.month)
        grouped.setdefault(key, []).append((training_date, training_time, comment))

    parts = ["📅 Календарь тренировок\n"]

    for (year, month), items in grouped.items():
        parts.append(f"\n{months[month]} {year}\n")

        for training_date, training_time, comment in items:
            parts.append(format_training_schedule_row(training_date, training_time, comment))
            parts.append("")

    return "\n".join(parts).strip()


async def test_subscription_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    await send_subscription_ending_reminders(context)
    await update.message.reply_text("Тестовое напоминание о скором окончании абонемента отправлено.")


async def coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    pending_users = get_users_by_status("pending")

    if not pending_users:
        await update.message.reply_text("Новых заявок пока нет.")
        return

    for user_id, username, first_name in pending_users:
        text = f"ID: {user_id}"
        if first_name:
            text += f" | Имя: {first_name}"
        if username:
            text += f" | username: @{username}"

        keyboard = [[
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup)


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    if not context.args:
        await update.message.reply_text("Используй команду так: /approve ID")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    existing_user = get_user_by_id(user_id)

    if not existing_user:
        await update.message.reply_text("Такой заявки нет.")
        return

    add_or_update_user(
        user_id=existing_user[0],
        username=existing_user[1],
        first_name=existing_user[2],
        status="approved"
    )

    await update.message.reply_text(f"Пользователь {user_id} одобрен.")

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="Тренер одобрил твою заявку. Теперь ты будешь получать уведомления.",
            reply_markup=get_approved_player_menu()
        )
    except Exception:
        await update.message.reply_text(
            "Пользователь одобрен, но сообщение ему отправить не удалось."
        )


async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    if not context.args:
        await update.message.reply_text("Используй команду так: /reject ID")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    existing_user = get_user_by_id(user_id)

    if not existing_user:
        await update.message.reply_text("Такой заявки нет.")
        return

    add_or_update_user(
        user_id=existing_user[0],
        username=existing_user[1],
        first_name=existing_user[2],
        status="rejected"
    )

    await update.message.reply_text(f"Пользователь {user_id} отклонён.")

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="Твоя заявка была отклонена тренером."
        )
    except Exception:
        await update.message.reply_text(
            "Пользователь отклонён, но сообщение ему отправить не удалось."
        )


async def approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    approved_users = [
        row for row in get_users_by_status("approved")
        if is_broadcast_recipient(row[0])
    ]

    if not approved_users:
        await update.message.reply_text("Одобренных игроков пока нет.")
        return

    for user_id, username, first_name in approved_users:
        name_text = first_name or "Без имени"
        username_text = f"@{username}" if username else "не указан"

        text = (
            f"👤 Игрок: {name_text}\n"
            f"🆔 ID: {user_id}\n"
            f"🔗 Username: {username_text}"
        )

        keyboard = [[
            InlineKeyboardButton("🗑 Удалить игрока", callback_data=f"delete_player_{user_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup)


async def send_message_to_approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    message_text = " ".join(context.args).strip()

    if not message_text:
        await update.message.reply_text("Используй команду так:\n/send Текст сообщения")
        return

    approved_users = get_users_by_status("approved")

    if not approved_users:
        await update.message.reply_text("Нет одобренных игроков для рассылки.")
        return

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

    await update.message.reply_text(
        f"Рассылка завершена.\n"
        f"Успешно отправлено: {success_count}\n"
        f"Ошибок: {fail_count}"
    )


async def send_payment_reminder_by_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    try:
        success_count, fail_count = await send_manual_payment_reminders(context)

        await update.message.reply_text(
            f"Рассылка отправлена.\n"
            f"Успешно: {success_count}\n"
            f"Ошибок: {fail_count}"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка при рассылке оплаты: {e}")


async def send_training_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    now_local = datetime.now(TIMEZONE)

    close_hour, close_minute = map(int, TRAINING_VOTE_CLOSE_TIME.split(":"))
    vote_close_time = time(close_hour, close_minute)

    if now_local.time() >= vote_close_time:
        await update.message.reply_text(
            f"После {TRAINING_VOTE_CLOSE_TIME} напоминание о тренировке запускать нельзя. "
            "Если нужно, запусти его заранее до начала тренировки."
        )
        return

    result = await start_training_reminder(context)

    if result is None:
        await update.message.reply_text("Напоминание уже запущено.")
        return

    schedule_training_repeat_job(context.application)

    await update.message.reply_text(
        f"Напоминание о тренировке отправлено.\n"
        f"Успешно: {result['success_count']}\n"
        f"Ошибок: {result['fail_count']}\n"
        f"Повторы будут отправляться каждые {TRAINING_REMINDER_REPEAT_MINUTES} мин до {result['stop_at'].strftime('%H:%M')}."
    )


async def show_training_responses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    await update.message.reply_text(build_training_responses_text())


async def open_payments_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    await update.message.reply_text(
        "Раздел оплат. Выбери действие:",
        reply_markup=get_payments_menu()
    )


async def open_subscription_type_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    await update.message.reply_text("Выбери игрока, чтобы изменить тип абонемента:")
    await show_subscription_type_players(update, context)


async def show_subscription_type_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    subscriptions = get_all_subscriptions()

    if not subscriptions:
        await update.message.reply_text("Игроков с абонементами пока нет.")
        return

    players_map = {
        user_id: (username, first_name)
        for user_id, username, first_name in get_users_by_status("approved")
    }

    for user_id, payment_day, subscription_type, subscription_end_date, last_payment_date, is_paid_current_period, _has_custom_schedule, payment_claimed in subscriptions:
        username, first_name = players_map.get(user_id, (None, None))

        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"

        subscription_type_text = "месячный" if subscription_type == "monthly" else "игровой"

        text = (
            f"👤 Игрок: {name}\n"
            f"🆔 ID: {user_id}\n"
            f"🎫 Тип абонемента: {subscription_type_text}"
        )

        keyboard = [[
            InlineKeyboardButton("Месячный", callback_data=f"set_subscription_type_monthly_{user_id}"),
            InlineKeyboardButton("Игровой", callback_data=f"set_subscription_type_game_{user_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup)


async def open_training_schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    context.user_data["awaiting_training_schedule_add"] = False
    context.user_data["awaiting_training_schedule_delete"] = False
    context.user_data["awaiting_training_schedule_manual_date"] = False
    context.user_data.pop("transfer_training_schedule_id", None)

    await update.message.reply_text(
        "Календарь тренировок. Выбери действие:",
        reply_markup=get_training_schedule_menu()
    )


async def show_training_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    schedule = get_upcoming_training_schedule()

    if not schedule:
        await update.message.reply_text("📅 Календарь тренировок пока пуст.")
        return

    await update.message.reply_text(build_existing_trainings_text(schedule))

    month_keyboards = build_existing_trainings_keyboard(schedule, "training_view")

    for title, reply_markup in month_keyboards:
        await update.message.reply_text(title, reply_markup=reply_markup)


async def start_add_training_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    context.user_data["awaiting_training_schedule_add"] = False
    context.user_data["awaiting_training_schedule_delete"] = False
    context.user_data["awaiting_training_schedule_manual_date"] = False
    context.user_data.pop("transfer_training_schedule_id", None)

    today = date.today()
    keyboard = build_month_dates_keyboard(today.year, today.month, "training_add_date")

    await update.message.reply_text(
        "Выбери дату новой тренировки:",
        reply_markup=keyboard
    )


async def start_delete_training_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    context.user_data["awaiting_training_schedule_add"] = False
    context.user_data["awaiting_training_schedule_delete"] = False
    context.user_data["awaiting_training_schedule_manual_date"] = False
    context.user_data.pop("transfer_training_schedule_id", None)

    schedule = get_upcoming_training_schedule()

    if not schedule:
        await update.message.reply_text("Нет тренировок для удаления.")
        return

    await update.message.reply_text("Выбери тренировку для удаления:")

    month_keyboards = build_existing_trainings_keyboard(schedule, "training_delete_direct")

    for title, reply_markup in month_keyboards:
        await update.message.reply_text(title, reply_markup=reply_markup)


async def handle_training_schedule_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()

    try:
        parsed_dt = datetime.strptime(raw_text, "%d.%m.%Y %H:%M")
    except ValueError:
        await update.message.reply_text(
            "Неверный формат.\n\n"
            "Используй:\n"
            "ДД.ММ.ГГГГ ЧЧ:ММ\n\n"
            "Например:\n"
            "25.05.2026 21:00"
        )
        return

    transfer_id = context.user_data.get("transfer_training_schedule_id")

    if transfer_id:
        old_row = get_training_schedule_by_id(transfer_id)

        if not old_row:
            context.user_data.pop("transfer_training_schedule_id", None)
            context.user_data["awaiting_training_schedule_manual_date"] = False
            await update.message.reply_text("Не удалось найти тренировку для переноса.")
            return

        _, old_date, old_time, old_comment, _, _ = old_row

        deactivate_training_schedule(transfer_id)
        add_training_schedule(
            training_date=parsed_dt.date(),
            training_time=parsed_dt.time(),
            comment=old_comment,
        )

        context.user_data.pop("transfer_training_schedule_id", None)
        context.user_data["awaiting_training_schedule_manual_date"] = False

        await update.message.reply_text(
            "📅 Тренировка перенесена.\n\n"
            f"Было: {format_training_schedule_row(old_date, old_time, old_comment)}\n"
            f"Стало: {format_training_schedule_row(parsed_dt.date(), parsed_dt.time(), old_comment)}"
        )
        return

    add_training_schedule(
        training_date=parsed_dt.date(),
        training_time=parsed_dt.time(),
        comment=None,
    )

    context.user_data["awaiting_training_schedule_manual_date"] = False

    await update.message.reply_text(
        "✅ Тренировка добавлена.\n\n"
        f"{format_training_schedule_row(parsed_dt.date(), parsed_dt.time())}"
    )


async def handle_training_schedule_delete_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()

    try:
        schedule_id = int(raw_text)
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    schedule_row = get_training_schedule_by_id(schedule_id)

    if not schedule_row:
        await update.message.reply_text("Тренировка с таким ID не найдена.")
        return

    deactivate_training_schedule(schedule_id)
    context.user_data["awaiting_training_schedule_delete"] = False

    _, training_date, training_time, comment, is_active, created_at = schedule_row

    await update.message.reply_text(
        "🗑 Тренировка удалена из календаря.\n\n"
        f"{format_training_schedule_row(training_date, training_time, comment)}"
    )


async def show_ending_soon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    today = date.today()
    subscriptions = get_subscriptions_ending_soon(today, days=5)

    if not subscriptions:
        await update.message.reply_text("Нет игроков, у которых скоро заканчивается абонемент.")
        return

    players_map = {
        user_id: (username, first_name)
        for user_id, username, first_name in get_users_by_status("approved")
    }

    text = "У кого скоро заканчивается абонемент:\n\n"

    for user_id, payment_day, subscription_type, subscription_end_date, last_payment_date, is_paid_current_period, _has_custom_schedule, payment_claimed in subscriptions:
        username, first_name = players_map.get(user_id, (None, None))

        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"

        days_left = (subscription_end_date - today).days
        subscription_type_text = "месячный" if subscription_type == "monthly" else "игровой"

        text += (
            f"⏰ Скоро срок оплаты\n"
            f"👤 Игрок: {name}\n"
            f"🆔 ID: {user_id}\n"
            f"🎫 Абонемент: {subscription_type_text}\n"
            f"💳 Абонемент до: {subscription_end_date.strftime('%d.%m.%Y')}\n"
            f"📅 Осталось дней: {days_left}\n"
            f"📌 Последняя оплата: {last_payment_date.strftime('%d.%m.%Y') if last_payment_date else 'Не указана'}\n\n"
        )

    await update.message.reply_text(text)


async def show_unpaid_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    today = date.today()
    subscriptions = get_unpaid_subscriptions(today)

    if not subscriptions:
        await update.message.reply_text("Нет игроков, которые не оплатили.")
        return

    players_map = {
        user_id: (username, first_name)
        for user_id, username, first_name in get_users_by_status("approved")
    }

    text = "Кто не оплатил:\n\n"

    for user_id, payment_day, subscription_type, subscription_end_date, last_payment_date, is_paid_current_period, _has_custom_schedule, payment_claimed in subscriptions:
        username, first_name = players_map.get(user_id, (None, None))

        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"

        end_date_text = subscription_end_date.strftime('%d.%m.%Y') if subscription_end_date else "Не указана"
        last_payment_text = last_payment_date.strftime('%d.%m.%Y') if last_payment_date else "Не указана"
        subscription_type_text = "месячный" if subscription_type == "monthly" else "игровой"

        text += (
            f"⚠️ Игрок не оплатил\n"
            f"👤 Игрок: {name}\n"
            f"🆔 ID: {user_id}\n"
            f"🎫 Абонемент: {subscription_type_text}\n"
            f"📅 Плановая дата оплаты: {payment_day}\n"
            f"💳 Абонемент до: {end_date_text}\n"
            f"📌 Последняя оплата: {last_payment_text}\n"
            f"💸 Нажал «Оплатил»: {'Да' if payment_claimed else 'Нет'}\n\n"
        )

    await update.message.reply_text(text)


async def open_mark_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    today = date.today()
    subscriptions = get_unpaid_subscriptions_with_users(today)

    if not subscriptions:
        await update.message.reply_text("Нет игроков для отметки оплаты.")
        return

    for user_id, username, first_name, payment_day, subscription_type, subscription_end_date, last_payment_date, is_paid_current_period, _has_custom_schedule, payment_claimed in subscriptions:
        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"

        end_date_text = subscription_end_date.strftime('%d.%m.%Y') if subscription_end_date else "Не указана"
        last_payment_text = last_payment_date.strftime('%d.%m.%Y') if last_payment_date else "Не указана"
        claimed_text = "Да" if payment_claimed else "Нет"
        subscription_type_text = "месячный" if subscription_type == "monthly" else "игровой"

        text = (
            f"💰 Подтверждение оплаты\n"
            f"👤 Игрок: {name}\n"
            f"🆔 ID: {user_id}\n"
            f"🎫 Абонемент: {subscription_type_text}\n"
            f"📅 Плановая дата оплаты: {payment_day}\n"
            f"💳 Абонемент до: {end_date_text}\n"
            f"📌 Последняя оплата: {last_payment_text}\n"
            f"💸 Нажал «Оплатил»: {claimed_text}"
        )

        keyboard = [[
            InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_payment_{user_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup)


async def back_to_coach_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    context.user_data["awaiting_training_schedule_add"] = False
    context.user_data["awaiting_training_schedule_delete"] = False
    context.user_data["awaiting_training_schedule_manual_date"] = False
    context.user_data.pop("transfer_training_schedule_id", None)

    await update.message.reply_text(
        "Возвращаю в главное меню тренера.",
        reply_markup=get_coach_menu()
    )


async def show_all_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    subscriptions = get_all_subscriptions()

    if not subscriptions:
        await update.message.reply_text("Абонементов пока нет.")
        return

    players_map = {
        user_id: (username, first_name)
        for user_id, username, first_name in get_users_by_status("approved")
    }

    text = "Все абонементы:\n\n"

    for user_id, payment_day, subscription_type, subscription_end_date, last_payment_date, is_paid_current_period, _has_custom_schedule, payment_claimed in subscriptions:
        username, first_name = players_map.get(user_id, (None, None))

        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"

        end_date_text = subscription_end_date.strftime('%d.%m.%Y') if subscription_end_date else "Не указана"
        last_payment_text = last_payment_date.strftime('%d.%m.%Y') if last_payment_date else "Не указана"
        paid_text = "Да" if is_paid_current_period else "Нет"
        claimed_text = "Да" if payment_claimed else "Нет"
        subscription_type_text = "месячный" if subscription_type == "monthly" else "игровой"

        text += (
            f"👤 Игрок: {name}\n"
            f"🆔 ID: {user_id}\n"
            f"🎫 Абонемент: {subscription_type_text}\n"
            f"💳 Абонемент до: {end_date_text}\n"
            f"📅 Плановая дата оплаты: {payment_day}\n"
            f"📌 Последняя оплата: {last_payment_text}\n"
            f"✅ Оплата подтверждена: {paid_text}\n"
            f"💸 Нажал «Оплатил»: {claimed_text}\n\n"
        )

    await update.message.reply_text(text)


async def show_training_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    text = build_training_status_text(context.application)
    await update.message.reply_text(text)


async def show_payment_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    history = get_all_payment_history(limit=30)

    if not history:
        await update.message.reply_text("История оплат пока пуста.")
        return

    players_map = {
        user_id: (username, first_name)
        for user_id, username, first_name in get_users_by_status("approved")
    }

    text = "🧾 История оплат:\n\n"

    action_map = {
        "claimed": "Игрок нажал «Оплатил»",
        "confirmed": "Тренер подтвердил оплату",
        "rejected": "Тренер не подтвердил оплату",
    }

    for history_id, user_id, action, created_at, comment in history:
        username, first_name = players_map.get(user_id, (None, None))
        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"

        action_text = action_map.get(action, action)
        created_at_text = created_at.strftime("%d.%m.%Y %H:%M")

        text += (
            f"👤 Игрок: {name}\n"
            f"🆔 ID: {user_id}\n"
            f"🕒 Когда: {created_at_text}\n"
            f"📌 Действие: {action_text}\n"
        )

        if comment:
            text += f"💬 Комментарий: {comment}\n"

        text += "\n"

    await update.message.reply_text(text)


async def show_month_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    now = datetime.now(TIMEZONE)
    stats = get_month_attendance_stats(now.year, now.month)

    if not stats:
        await update.message.reply_text("За этот месяц данных по посещаемости пока нет.")
        return

    text = f"📊 Посещаемость за {now.strftime('%m.%Y')}\n\n"

    for user_id, username, first_name, yes_count, no_count, total_count in stats:
        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"

        yes_count = yes_count or 0
        no_count = no_count or 0
        total_count = total_count or 0

        text += (
            f"👤 {name}\n"
            f"✅ Был / ответил «Приду»: {yes_count}\n"
            f"❌ Ответил «Не приду»: {no_count}\n"
            f"📌 Всего ответов: {total_count}\n\n"
        )

    await update.message.reply_text(text)