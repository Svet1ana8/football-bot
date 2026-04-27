from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import TIMEZONE
from app.handlers.common import deny_access
from app.keyboards import get_payments_menu, get_coach_menu
from app.repositories.schedules import (
    create_scheduled_message,
    delete_scheduled_message,
    get_all_scheduled_messages,
)
from app.repositories.users import (
    add_or_update_user,
    get_user_by_id,
    get_users_by_status,
)
from app.services.access import is_broadcast_recipient, is_coach
from app.services.schedules import scheduled_send_job
from app.services.trainings import (
    build_training_responses_text,
    schedule_training_repeat_job,
    send_payment_reminder_by_month_text,
    start_training_reminder,
)


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
            text="Тренер одобрил твою заявку. Теперь ты будешь получать уведомления."
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
        text = f"ID: {user_id}"
        if first_name:
            text += f" | Имя: {first_name}"
        if username:
            text += f" | username: @{username}"

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


async def schedule_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    full_text = update.message.text.replace("/schedule", "", 1).strip()

    if not full_text:
        await update.message.reply_text(
            "Используй команду так:\n"
            "/schedule 30.04.2026 21:00 Текст сообщения"
        )
        return

    parts = full_text.split(" ", 2)

    if len(parts) < 3:
        await update.message.reply_text(
            "Неверный формат.\n"
            "Пример:\n"
            "/schedule 30.04.2026 21:00 Напоминаю об оплате тренировок"
        )
        return

    date_part = parts[0]
    time_part = parts[1]
    message_text = parts[2].strip()

    try:
        send_at = datetime.strptime(
            f"{date_part} {time_part}", "%d.%m.%Y %H:%M"
        ).replace(tzinfo=TIMEZONE)
    except ValueError:
        await update.message.reply_text(
            "Неверный формат даты или времени.\n"
            "Используй так: ДД.ММ.ГГГГ ЧЧ:ММ"
        )
        return

    if send_at <= datetime.now(TIMEZONE):
        await update.message.reply_text("Нельзя запланировать рассылку на прошедшее время.")
        return

    message_id = create_scheduled_message(send_at, message_text)

    context.job_queue.run_once(
        scheduled_send_job,
        when=send_at,
        data={"message_id": message_id},
        name=f"scheduled_message_{message_id}"
    )

    await update.message.reply_text(
        f"Рассылка запланирована.\n"
        f"ID: {message_id}\n"
        f"Дата и время: {send_at}\n"
        f"Текст: {message_text}"
    )


async def list_scheduled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    messages = get_all_scheduled_messages()

    if not messages:
        await update.message.reply_text("Запланированных рассылок нет.")
        return

    text = "Запланированные рассылки:\n\n"
    for message_id, send_at, message_text, status in messages:
        text += (
            f"ID: {message_id}\n"
            f"Дата: {send_at}\n"
            f"Статус: {status}\n"
            f"Текст: {message_text}\n\n"
        )

    await update.message.reply_text(text)


async def delete_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    if not context.args:
        await update.message.reply_text("Используй команду так: /delete_schedule ID")
        return

    try:
        message_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    deleted = delete_scheduled_message(message_id)

    current_jobs = context.application.job_queue.jobs()
    for job in current_jobs:
        if job.name == f"scheduled_message_{message_id}":
            job.schedule_removal()

    if deleted:
        await update.message.reply_text(f"Запланированная рассылка {message_id} удалена.")
    else:
        await update.message.reply_text("Рассылка с таким ID не найдена.")


async def send_payment_reminder_by_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    approved_users = get_users_by_status("approved")
    if not approved_users:
        await update.message.reply_text("Нет одобренных игроков для рассылки.")
        return

    message_text, success_count, fail_count = await send_payment_reminder_by_month_text(context)

    await update.message.reply_text(
        f"Рассылка отправлена.\n"
        f"Текст: {message_text}\n"
        f"Успешно: {success_count}\n"
        f"Ошибок: {fail_count}"
    )


async def send_training_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
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
        f"Повторы будут отправляться каждые 2 часа до {result['stop_at'].strftime('%H:%M')}."
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


async def show_ending_soon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    await update.message.reply_text(
        "Здесь позже появится список игроков, у кого скоро заканчивается абонемент."
    )


async def show_unpaid_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    await update.message.reply_text(
        "Здесь позже появится список игроков, которые ещё не оплатили."
    )


async def open_mark_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    await update.message.reply_text(
        "Здесь позже появится выбор игрока для отметки оплаты."
    )


async def back_to_coach_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    await update.message.reply_text(
        "Возвращаю в главное меню тренера.",
        reply_markup=get_coach_menu()
    )
