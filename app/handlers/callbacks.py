from datetime import date, datetime, timedelta
import calendar

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import COACH_IDS, TIMEZONE
from app.keyboards import get_approved_player_menu, get_player_menu
from app.repositories.payments import (
    add_payment_history,
    confirm_payment,
    create_subscription_for_user,
    mark_payment_claimed,
    reject_claimed_payment,
    set_subscription_type,
)
from app.repositories.training_schedule import (
    add_training_schedule,
    deactivate_training_schedule,
    get_training_schedule_by_id,
    get_upcoming_training_schedule,
)
from app.repositories.users import (
    add_or_update_user,
    delete_user,
    get_user_by_id,
    get_users_by_status,
)
from app.services.access import is_broadcast_recipient, is_coach
from app.services.notifications import notify_coaches_about_request
from app.repositories.trainings import get_active_training
from app.services.trainings import (
    build_training_message,
    cancel_current_training_vote,
    get_change_answer_confirm_keyboard,
    get_change_answer_keyboard,
    get_training_keyboard,
    save_player_training_response,
)
from app.repositories.game_schedule import (
    add_game_schedule,
    deactivate_game_schedule,
    get_game_schedule_by_id,
    get_upcoming_game_schedule,
)


def get_display_name(
    user_id: int,
    fallback_first_name: str | None = None,
    fallback_username: str | None = None,
) -> str:
    existing_user = get_user_by_id(user_id)

    if existing_user:
        saved_name = existing_user[2]
        saved_username = existing_user[1]

        name = saved_name or fallback_first_name or str(user_id)
        if saved_username:
            name += f" (@{saved_username})"
        elif fallback_username:
            name += f" (@{fallback_username})"
        return name

    name = fallback_first_name or str(user_id)
    if fallback_username:
        name += f" (@{fallback_username})"
    return name


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

    if prefix != "training_add_date":
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

def format_game_schedule_row(game_date, game_time, opponent_name, comment=None) -> str:
    text = f"{get_weekday_name(game_date)} — {game_date.strftime('%d.%m.%Y')}, {game_time.strftime('%H:%M')}\nСоперник: {opponent_name}"
    if comment:
        text += f"\nКомментарий: {comment}"
    return text


def build_existing_games_keyboard(schedule, callback_prefix: str) -> list[tuple[str, InlineKeyboardMarkup]]:
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
    for game_id, game_date, game_time, opponent_name, comment, is_active, created_at in schedule:
        key = (game_date.year, game_date.month)
        grouped.setdefault(key, []).append((game_id, game_date, game_time, opponent_name, comment))

    result = []

    for (year, month), items in grouped.items():
        rows = []
        current_row = []

        for game_id, game_date, game_time, opponent_name, comment in items:
            current_row.append(
                InlineKeyboardButton(
                    str(game_date.day),
                    callback_data=f"{callback_prefix}_{game_id}",
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

def is_deleted_schedule_active_training(training_date: date, training_time) -> bool:
    """
    Проверяет, совпадает ли удаляемая тренировка из календаря
    с текущей активной тренировкой в trainings.

    Работает для двух случаев:
    - тренер отменяет тренировку за день до неё;
    - тренер отменяет тренировку в день тренировки.
    """
    active_training = get_active_training()

    if not active_training:
        return False

    active_start_time = active_training[2]

    if not active_start_time:
        return False

    active_local = active_start_time.astimezone(TIMEZONE)

    return (
        active_local.date() == training_date
        and active_local.time().replace(second=0, microsecond=0)
        == training_time.replace(second=0, microsecond=0)
    )


def build_training_cancelled_message(training_date: date, training_time) -> str:
    """
    Простое уведомление игрокам без причины.
    """
    return (
        "❌ Тренировка отменена\n\n"
        f"Тренировка {training_date.strftime('%d.%m.%Y')} "
        f"в {training_time.strftime('%H:%M')} отменена."
    )


async def notify_players_training_cancelled(
    context: ContextTypes.DEFAULT_TYPE,
    training_date: date,
    training_time,
):
    """
    Отправляет approved-игрокам уведомление об отмене тренировки.

    Важно:
    - данные в БД не удаляем;
    - ответы игроков не трогаем;
    - если кому-то не отправилось — бот не падает.
    """
    approved_users = get_users_by_status("approved")
    message_text = build_training_cancelled_message(training_date, training_time)

    success_count = 0
    fail_count = 0

    for player_id, username, first_name in approved_users:
        if not is_broadcast_recipient(player_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=message_text,
            )
            success_count += 1
        except Exception as e:
            print(f"Не удалось отправить уведомление об отмене игроку {player_id}: {e}")
            fail_count += 1

    return success_count, fail_count


async def cancel_active_training_if_needed(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    training_date: date,
    training_time,
) -> tuple[bool, int, int]:
    """
    Если удаляемая тренировка совпадает с активной тренировкой,
    отменяем активную тренировку и уведомляем игроков.

    Возвращает:
    cancelled, success_count, fail_count
    """
    if not is_deleted_schedule_active_training(training_date, training_time):
        return False, 0, 0

    cancelled_training_id = await cancel_current_training_vote(
        coach_user_id=query.from_user.id,
        reason=None,
    )

    if not cancelled_training_id:
        return False, 0, 0

    success_count, fail_count = await notify_players_training_cancelled(
        context=context,
        training_date=training_date,
        training_time=training_time,
    )

    return True, success_count, fail_count


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id
    data = query.data

    if data == "send_request":
        existing_user = get_user_by_id(user_id)

        if existing_user and existing_user[3] == "approved":
            await query.edit_message_text("Ты уже одобрен тренером и получаешь уведомления.")
            return

        add_or_update_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            status="pending"
        )

        await query.edit_message_text("Твоя заявка отправлена тренеру. Ожидай подтверждения.")
        await notify_coaches_about_request(context, user.id)
        return

    if data.startswith("training_yes_"):
        training_id = int(data.split("_")[2])

        existing_user = get_user_by_id(query.from_user.id)
        player_name = existing_user[2] if existing_user and existing_user[2] else query.from_user.first_name

        save_player_training_response(
            training_id=training_id,
            user_id=query.from_user.id,
            username=query.from_user.username,
            first_name=player_name,
            response="yes"
        )

        current_text = query.message.text or ""

        await query.answer("Ответ сохранён")
        await query.edit_message_text(
            text=(
                f"{current_text}\n\n"
                "✅ Ты отметил(а), что придёшь на тренировку."
            ),
            reply_markup=get_change_answer_keyboard(training_id)
        )
        return

    if data.startswith("training_no_"):
        training_id = int(data.split("_")[2])

        existing_user = get_user_by_id(query.from_user.id)
        player_name = existing_user[2] if existing_user and existing_user[2] else query.from_user.first_name

        save_player_training_response(
            training_id=training_id,
            user_id=query.from_user.id,
            username=query.from_user.username,
            first_name=player_name,
            response="no"
        )

        current_text = query.message.text or ""

        await query.answer("Ответ сохранён")
        await query.edit_message_text(
            text=(
                f"{current_text}\n\n"
                "❌ Ты отметил(а), что не придёшь на тренировку."
            ),
            reply_markup=get_change_answer_keyboard(training_id)
        )
        return

    if data.startswith("change_training_answer_"):
        training_id = int(data.split("_")[3])

        await query.answer("Можно изменить ответ")
        await query.edit_message_text(
            f"Сегодня тренировка в {build_training_message().splitlines()[0].replace('Сегодня тренировка в ', '').replace('.', '')}\n"
            "Хочешь изменить свой ответ?",
            reply_markup=get_change_answer_confirm_keyboard(training_id)
        )
        return

    if data.startswith("confirm_change_training_"):
        training_id = int(data.split("_")[3])

        await query.answer("Выбери новый ответ")
        await query.edit_message_text(
            build_training_message(),
            reply_markup=get_training_keyboard(training_id)
        )
        return

    if data.startswith("cancel_change_training_"):
        training_id = int(data.split("_")[3])

        await query.answer("Изменение отменено")
        await query.edit_message_text(
            "Твой текущий ответ сохранён.",
            reply_markup=get_change_answer_keyboard(training_id)
        )
        return

    if data == "payment_claimed":
        mark_payment_claimed(query.from_user.id, True)
        add_payment_history(
            user_id=query.from_user.id,
            action="claimed",
            comment="Игрок нажал кнопку 'Оплатил'"
        )

        await query.answer("Твоя отметка об оплате отправлена тренеру.")
        await query.edit_message_reply_markup(reply_markup=None)

        player_name = get_display_name(
            user_id=query.from_user.id,
            fallback_first_name=query.from_user.first_name,
            fallback_username=query.from_user.username
        )

        text = (
            f"Игрок {player_name} сообщил, что оплатил.\n"
            f"ID: {query.from_user.id}"
        )

        keyboard = [[
            InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_payment_{query.from_user.id}"),
            InlineKeyboardButton("❌ Не подтверждать", callback_data=f"reject_payment_{query.from_user.id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        for coach_id in COACH_IDS:
            try:
                await context.bot.send_message(
                    chat_id=int(coach_id),
                    text=text,
                    reply_markup=reply_markup
                )
            except Exception:
                pass

        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="Тренеру отправлено уведомление о том, что ты оплатил."
        )
        return

    if data.startswith("approve_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        target_user_id = int(data.split("_")[1])
        existing_user = get_user_by_id(target_user_id)

        if not existing_user:
            await query.edit_message_text("Такой заявки уже нет.")
            return

        add_or_update_user(
            user_id=existing_user[0],
            username=existing_user[1],
            first_name=existing_user[2],
            status="approved"
        )
        create_subscription_for_user(target_user_id)

        player_name = existing_user[2] or str(target_user_id)
        await query.edit_message_text(f"✅ Игрок {player_name} одобрен.")

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="Тренер одобрил твою заявку. Теперь ты будешь получать уведомления.",
                reply_markup=get_approved_player_menu()
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=f"Игрок {player_name} одобрен, но сообщение ему отправить не удалось."
            )
        return

    if data.startswith("delete_player_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        target_user_id = int(data.split("_")[2])
        existing_user = get_user_by_id(target_user_id)
        player_name = existing_user[2] if existing_user and existing_user[2] else str(target_user_id)

        deleted = delete_user(target_user_id)

        if deleted:
            await query.edit_message_text(f"🗑 Игрок {player_name} удалён из базы.")
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="Ты был удалён из списка игроков. Если нужно, можешь снова подать заявку.",
                    reply_markup=get_player_menu()
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("Игрок уже удалён или не найден.")

        return

    if data.startswith("set_subscription_type_monthly_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        target_user_id = int(data.split("_")[-1])
        target_user = get_user_by_id(target_user_id)
        player_name = target_user[2] if target_user and target_user[2] else str(target_user_id)

        set_subscription_type(target_user_id, "monthly")

        await query.edit_message_text(
            f"✅ Игроку {player_name} установлен тип абонемента: месячный."
        )

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="Тренер обновил твой тип абонемента: месячный."
            )
        except Exception:
            pass

        return

    if data.startswith("set_subscription_type_game_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        target_user_id = int(data.split("_")[-1])
        target_user = get_user_by_id(target_user_id)
        player_name = target_user[2] if target_user and target_user[2] else str(target_user_id)

        set_subscription_type(target_user_id, "game")

        await query.edit_message_text(
            f"✅ Игроку {player_name} установлен тип абонемента: игровой."
        )

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="Тренер обновил твой тип абонемента: игровой."
            )
        except Exception:
            pass

        return

    if data.startswith("confirm_payment_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        target_user_id = int(data.split("_")[2])
        target_user = get_user_by_id(target_user_id)
        player_name = target_user[2] if target_user and target_user[2] else str(target_user_id)

        today = date.today()

        # Временно оставляем вызов функции, которую потом обновим в repositories/payments.py
        new_end_date = confirm_payment(
            user_id=target_user_id,
            today=today,
        )

        add_payment_history(
            user_id=target_user_id,
            action="confirmed",
            comment=f"Тренер подтвердил оплату. Абонемент продлён до {new_end_date.strftime('%d.%m.%Y')}"
        )

        await query.edit_message_text(
            f"✅ Оплата игрока {player_name} подтверждена.\n"
            f"Абонемент продлён до {new_end_date.strftime('%d.%m.%Y')}."
        )

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"✅ Тренер подтвердил оплату.\n"
                    f"Твой абонемент продлён до {new_end_date.strftime('%d.%m.%Y')}."
                )
            )
        except Exception:
            pass

        return

    if data.startswith("reject_payment_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        target_user_id = int(data.split("_")[2])
        target_user = get_user_by_id(target_user_id)
        player_name = target_user[2] if target_user and target_user[2] else str(target_user_id)

        reject_claimed_payment(target_user_id)
        add_payment_history(
            user_id=target_user_id,
            action="rejected",
            comment="Тренер не подтвердил оплату"
        )

        await query.answer("Отклонение получено")

        await query.edit_message_text(
            f"❌ Оплата игрока {player_name} не подтверждена.\n"
            f"Напоминания об оплате продолжатся."
        )

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="Тренер пока не подтвердил оплату. Напоминания продолжатся."
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=f"Не удалось отправить сообщение игроку: {e}"
            )

        return

    if data.startswith("training_pick_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        schedule_id = int(data.split("_")[-1])
        row = get_training_schedule_by_id(schedule_id)

        if not row:
            await query.edit_message_text("Тренировка не найдена.")
            return

        _, training_date, training_time, comment, is_active, created_at = row

        await query.edit_message_text(
            "Выбрана тренировка:\n\n"
            f"{format_training_schedule_row(training_date, training_time, comment)}",
            reply_markup=build_training_action_keyboard(schedule_id)
        )
        return

    if data.startswith("training_delete_direct_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        schedule_id = int(data.split("_")[-1])
        row = get_training_schedule_by_id(schedule_id)

        if not row:
            await query.edit_message_text("Тренировка не найдена.")
            return

        _, training_date, training_time, comment, is_active, created_at = row

        deactivate_training_schedule(schedule_id)

        cancelled_active, notify_success, notify_fail = await cancel_active_training_if_needed(
            query=query,
            context=context,
            training_date=training_date,
            training_time=training_time,
        )

        result_text = (
            "🗑 Тренировка удалена.\n\n"
            f"{format_training_schedule_row(training_date, training_time, comment)}"
        )

        if cancelled_active:
            result_text += (
                "\n\n❌ Активная тренировка отменена."
                f"\nИгрокам отправлено уведомление: {notify_success}"
                f"\nОшибок отправки: {notify_fail}"
            )

        await query.edit_message_text(result_text)

        remaining_schedule = get_upcoming_training_schedule()

        if not remaining_schedule:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Все тренировки удалены."
            )
            return

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Выбери следующую тренировку для удаления:"
        )

        month_keyboards = build_existing_trainings_keyboard(
            remaining_schedule,
            "training_delete_direct"
        )

        for title, reply_markup in month_keyboards:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=title,
                reply_markup=reply_markup
            )
        return

    if data.startswith("training_delete_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        schedule_id = int(data.split("_")[-1])
        row = get_training_schedule_by_id(schedule_id)

        if not row:
            await query.edit_message_text("Тренировка не найдена.")
            return

        _, training_date, training_time, comment, is_active, created_at = row

        deactivate_training_schedule(schedule_id)

        cancelled_active, notify_success, notify_fail = await cancel_active_training_if_needed(
            query=query,
            context=context,
            training_date=training_date,
            training_time=training_time,
        )

        result_text = (
            "🗑 Тренировка удалена.\n\n"
            f"{format_training_schedule_row(training_date, training_time, comment)}"
        )

        if cancelled_active:
            result_text += (
                "\n\n❌ Активная тренировка отменена."
                f"\nИгрокам отправлено уведомление: {notify_success}"
                f"\nОшибок отправки: {notify_fail}"
            )

        await query.edit_message_text(result_text)
        return

    if data.startswith("training_transfer_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        schedule_id = int(data.split("_")[-1])
        row = get_training_schedule_by_id(schedule_id)

        if not row:
            await query.edit_message_text("Тренировка не найдена.")
            return

        _, training_date, training_time, comment, is_active, created_at = row

        context.user_data["transfer_training_schedule_id"] = schedule_id
        context.user_data["awaiting_training_schedule_add"] = False
        context.user_data["awaiting_training_schedule_delete"] = False
        context.user_data["awaiting_training_schedule_manual_date"] = False

        today = date.today()
        keyboard = build_month_dates_keyboard(today.year, today.month, "training_transfer_date")

        await query.edit_message_text(
            "Выбрана тренировка для переноса:\n\n"
            f"{format_training_schedule_row(training_date, training_time, comment)}\n\n"
            "Выбери новую дату:",
            reply_markup=keyboard
        )
        return

    if data.startswith("training_transfer_date_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        suffix = data.replace("training_transfer_date_", "", 1)

        if suffix == "manual":
            context.user_data["awaiting_training_schedule_manual_date"] = True
            await query.edit_message_text(
                "Отправь новую дату и время в формате:\n\n"
                "ДД.ММ.ГГГГ ЧЧ:ММ"
            )
            return

        schedule_id = context.user_data.get("transfer_training_schedule_id")
        old_row = get_training_schedule_by_id(schedule_id) if schedule_id else None

        if not old_row:
            await query.edit_message_text("Не удалось найти тренировку для переноса.")
            return

        _, old_date, old_time, old_comment, _, _ = old_row

        new_date = datetime.strptime(suffix, "%Y-%m-%d").date()

        deactivate_training_schedule(schedule_id)
        add_training_schedule(
            training_date=new_date,
            training_time=old_time,
            comment=old_comment,
        )

        context.user_data.pop("transfer_training_schedule_id", None)
        context.user_data["awaiting_training_schedule_manual_date"] = False

        await query.edit_message_text(
            "📅 Тренировка перенесена.\n\n"
            f"Было: {format_training_schedule_row(old_date, old_time, old_comment)}\n"
            f"Стало: {format_training_schedule_row(new_date, old_time, old_comment)}"
        )
        return

    if data.startswith("training_add_date_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        selected_date = datetime.strptime(data.replace("training_add_date_", "", 1), "%Y-%m-%d").date()
        training_time = datetime.strptime("21:00", "%H:%M").time()

        add_training_schedule(
            training_date=selected_date,
            training_time=training_time,
            comment=None,
        )

        await query.edit_message_text(
            "✅ Тренировка добавлена.\n\n"
            f"{format_training_schedule_row(selected_date, training_time)}"
        )
        return

    if data.startswith("training_view_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        schedule_id = int(data.split("_")[-1])
        row = get_training_schedule_by_id(schedule_id)

        if not row:
            await query.answer("Тренировка не найдена", show_alert=True)
            return

        _, training_date, training_time, comment, is_active, created_at = row

        await query.answer(
            format_training_schedule_row(training_date, training_time, comment),
            show_alert=True
        )
        return

    if data.startswith("training_player_view_"):
        schedule_id = int(data.split("_")[-1])
        row = get_training_schedule_by_id(schedule_id)

        if not row:
            await query.answer("Тренировка не найдена", show_alert=True)
            return

        _, training_date, training_time, comment, is_active, created_at = row

        await query.answer(
            format_training_schedule_row(training_date, training_time, comment),
            show_alert=True
        )
        return

    if data.startswith("reject_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        target_user_id = int(data.split("_")[1])
        existing_user = get_user_by_id(target_user_id)

        if not existing_user:
            await query.edit_message_text("Такой заявки уже нет.")
            return

        add_or_update_user(
            user_id=existing_user[0],
            username=existing_user[1],
            first_name=existing_user[2],
            status="rejected"
        )

        player_name = existing_user[2] or str(target_user_id)
        await query.edit_message_text(f"❌ Игрок {player_name} отклонён.")

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="Твоя заявка была отклонена тренером."
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=f"Игрок {player_name} отклонён, но сообщение ему отправить не удалось."
            )
        return

    if data.startswith("game_add_date_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        selected_date = data.replace("game_add_date_", "", 1)
        context.user_data["selected_game_date"] = selected_date
        context.user_data["awaiting_game_details"] = True

        await query.edit_message_text(
            "Отправь данные матча в формате:\n\n"
            "Команда | ЧЧ:ММ\n\n"
            "Например:\n"
            "Астана Барс | 19:00"
        )
        return

    if data.startswith("game_view_"):
        game_id = int(data.split("_")[-1])
        row = get_game_schedule_by_id(game_id)

        if not row:
            await query.answer("Матч не найден", show_alert=True)
            return

        _, game_date, game_time, opponent_name, comment, is_active, created_at = row

        await query.answer(
            format_game_schedule_row(game_date, game_time, opponent_name, comment),
            show_alert=True
        )
        return

    if data.startswith("game_player_view_"):
        game_id = int(data.split("_")[-1])
        row = get_game_schedule_by_id(game_id)

        if not row:
            await query.answer("Матч не найден", show_alert=True)
            return

        _, game_date, game_time, opponent_name, comment, is_active, created_at = row

        await query.answer(
            format_game_schedule_row(game_date, game_time, opponent_name, comment),
            show_alert=True
        )
        return

    if data.startswith("game_delete_direct_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        game_id = int(data.split("_")[-1])
        row = get_game_schedule_by_id(game_id)

        if not row:
            await query.edit_message_text("Матч не найден.")
            return

        _, game_date, game_time, opponent_name, comment, is_active, created_at = row

        deactivate_game_schedule(game_id)

        await query.edit_message_text(
            "🗑 Матч удалён.\n\n"
            f"{format_game_schedule_row(game_date, game_time, opponent_name, comment)}"
        )

        remaining_games = get_upcoming_game_schedule()

        if not remaining_games:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Все матчи удалены."
            )
            return

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Выбери следующий матч для удаления:"
        )

        month_keyboards = build_existing_games_keyboard(
            remaining_games,
            "game_delete_direct"
        )

        for title, reply_markup in month_keyboards:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=title,
                reply_markup=reply_markup
            )
        return