import os
import psycopg
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
COACH_ID = os.getenv("COACH_ID")
DATABASE_URL = os.getenv("DATABASE_URL")
TIMEZONE = ZoneInfo("Asia/Almaty")


def get_connection():
    if not DATABASE_URL:
        raise ValueError("Не найден BOT_TOKEN в переменных окружения")
    return psycopg.connect(DATABASE_URL)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            status TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_messages (
            id SERIAL PRIMARY KEY,
            send_at TIMESTAMPTZ NOT NULL,
            message_text TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    cur.execute("""
                CREATE TABLE IF NOT EXISTS training_responses (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    response TEXT
                    )
                """)

    conn.commit()
    conn.close()


def add_or_update_user(user_id: int, username: str | None, first_name: str | None, status: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (user_id, username, first_name, status)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            status = excluded.status
    """, (user_id, username, first_name, status))

    conn.commit()
    conn.close()


def get_users_by_status(status: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, username, first_name
        FROM users
        WHERE status = %s
        ORDER BY user_id
    """, (status,))

    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_by_id(user_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, username, first_name, status
        FROM users
        WHERE user_id = %s
    """, (user_id,))

    row = cur.fetchone()
    conn.close()
    return row

def delete_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM users
        WHERE user_id = %s
    """, (user_id,))

    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def create_scheduled_message(send_at: str, message_text: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
                INSERT INTO scheduled_messages (send_at, message_text, status)
                VALUES (%s, %s, %s) RETURNING id
                """, (send_at, message_text, "scheduled"))

    message_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return message_id


def get_scheduled_message(message_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, send_at, message_text, status
        FROM scheduled_messages
        WHERE id = %s
    """, (message_id,))

    row = cur.fetchone()
    conn.close()
    return row


def get_all_scheduled_messages():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, send_at, message_text, status
        FROM scheduled_messages
        ORDER BY send_at
    """)

    rows = cur.fetchall()
    conn.close()
    return rows


def mark_scheduled_message_done(message_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE scheduled_messages
        SET status = 'done'
        WHERE id = %s
    """, (message_id,))

    conn.commit()
    conn.close()


def delete_scheduled_message(message_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM scheduled_messages
        WHERE id = %s
    """, (message_id,))

    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def save_training_response(user_id: int, username: str | None, first_name: str | None, response: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO training_responses (user_id, username, first_name, response)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            response = excluded.response
    """, (user_id, username, first_name, response))

    conn.commit()
    conn.close()


def get_all_training_responses():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, username, first_name, response
        FROM training_responses
        ORDER BY first_name
    """)

    rows = cur.fetchall()
    conn.close()
    return rows


def clear_training_responses():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM training_responses")

    conn.commit()
    conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if is_coach(update.effective_user.id):
        await update.message.reply_text(
            f"Привет, {user.first_name}!\n\n"
            "Ты вошел как тренер.\n"
            "Используй меню ниже для работы с заявками, игроками и рассылками.",
            reply_markup=get_coach_menu()
        )
        return

    await update.message.reply_text(
        f"Привет, {user.first_name}!\n\n"
        "Это бот команды по американскому футболу Алматы Фениксы.\n"
        "Через него ты будешь получать напоминания и уведомления от тренера.\n\n"
        "Чтобы начать, нажми кнопку «Подать заявку» ниже.",
        reply_markup=get_player_menu()
    )
    user = update.effective_user


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id
    data = query.data

    if data == "send_request":
        existing_user = get_user_by_id(user_id)

        if existing_user and existing_user[3] == "approved":
            await query.edit_message_text(
                "Ты уже одобрен тренером и получаешь уведомления."
            )
            return

        add_or_update_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            status="pending"
        )

        await query.edit_message_text(
            "Твоя заявка отправлена тренеру. Ожидай подтверждения."
        )

        await notify_coach_about_request(context, user.id)
        return

    if data == "training_yes":
        save_training_response(
            user_id=query.from_user.id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
            response="yes"
        )
        await query.answer("Ответ сохранён")
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="✅ Ответ сохранён: ты придёшь на тренировку."
        )
        return

    if data == "training_no":
        save_training_response(
            user_id=query.from_user.id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
            response="no"
        )
        await query.answer("Ответ сохранён")
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="❌ Ответ сохранён: ты не придёшь на тренировку."
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

        await query.edit_message_text(
            f"✅ Пользователь {target_user_id} одобрен."
        )

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="Тренер одобрил твою заявку. Теперь ты будешь получать уведомления."
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=f"Пользователь {target_user_id} одобрен, но сообщение ему отправить не удалось."
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

        await query.edit_message_text(
            f"❌ Пользователь {target_user_id} отклонён."
        )

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="Твоя заявка была отклонена тренером."
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=f"Пользователь {target_user_id} отклонён, но сообщение ему отправить не удалось."
            )
        return
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id

    if query.data == "send_request":
        existing_user = get_user_by_id(user_id)

        if existing_user and existing_user[3] == "approved":
            await query.edit_message_text(
                "Ты уже одобрен тренером и получаешь уведомления."
            )
            return

        add_or_update_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            status="pending"
        )

        await query.edit_message_text(
            "Твоя заявка отправлена тренеру. Ожидай подтверждения."
        )

    if data.startswith("delete_player_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        target_user_id = int(data.split("_")[2])
        deleted = delete_user(target_user_id)

        if deleted:
            await query.edit_message_text(
                f"🗑 Игрок {target_user_id} удалён из базы."
            )
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="Ты был удалён из списка игроков. Если нужно, можешь снова подать заявку."
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("Игрок уже удалён или не найден.")
        return


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
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    pending_users = get_users_by_status("pending")

    if not pending_users:
        await update.message.reply_text("Новых заявок пока нет.")
        return

    text = "Новые заявки:\n\n"
    for user_id, username, first_name in pending_users:
        text += f"ID: {user_id}"
        if first_name:
            text += f" | Имя: {first_name}"
        if username:
            text += f" | username: @{username}"
        text += "\n"

    await update.message.reply_text(text)


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

    approved_users = get_users_by_status("approved")

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
        await update.message.reply_text(
            "Используй команду так:\n/send Текст сообщения"
        )
        return

    approved_users = get_users_by_status("approved")

    if not approved_users:
        await update.message.reply_text("Нет одобренных игроков для рассылки.")
        return

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if str(user_id) == str(COACH_ID):
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


async def scheduled_send_job(context: ContextTypes.DEFAULT_TYPE):
    message_id = context.job.data["message_id"]
    scheduled_message = get_scheduled_message(message_id)

    if not scheduled_message:
        return

    _, send_at, message_text, status = scheduled_message

    if status != "scheduled":
        return

    approved_users = get_users_by_status("approved")

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if str(user_id) == str(COACH_ID):
            continue

        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except Exception as e:
            print(f"Ошибка отправки пользователю {user_id}: {e}")
            fail_count += 1

    mark_scheduled_message_done(message_id)

    print(
        f"Scheduled message #{message_id} sent. "
        f"Success: {success_count}, Failed: {fail_count}"
    )


async def schedule_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    full_text = update.message.text.replace("/schedule", "", 1).strip()

    if not full_text:
        await update.message.reply_text(
            "Используй команду так:\n"
            "/schedule 2026-04-30 18:00 Текст сообщения"
        )
        return

    parts = full_text.split(" ", 2)

    if len(parts) < 3:
        await update.message.reply_text(
            "Неверный формат.\n"
            "Пример:\n"
            "/schedule 2026-04-30 18:00 Напоминаю об оплате тренировок"
        )
        return

    date_part = parts[0]
    time_part = parts[1]
    message_text = parts[2].strip()

    try:
        send_at = datetime.strptime(
            f"{date_part} {time_part}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=TIMEZONE)
    except ValueError:
        await update.message.reply_text(
            "Неверный формат даты или времени.\n"
            "Используй так: YYYY-MM-DD HH:MM"
        )
        return

    if send_at <= datetime.now(TIMEZONE):
        await update.message.reply_text(
            "Нельзя запланировать рассылку на прошедшее время."
        )
        return

    message_id = create_scheduled_message(send_at.isoformat(), message_text)

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

def restore_jobs(application: Application):
    messages = get_all_scheduled_messages()

    for message_id, send_at, message_text, status in messages:
        if status != "scheduled":
            continue

        send_at_dt = datetime.fromisoformat(send_at)

        if send_at_dt.tzinfo is None:
            send_at_dt = send_at_dt.replace(tzinfo=TIMEZONE)

        if send_at_dt > datetime.now(TIMEZONE):
            application.job_queue.run_once(
                scheduled_send_job,
                when=send_at_dt,
                data={"message_id": message_id},
                name=f"scheduled_message_{message_id}"
            )


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой chat_id: {update.effective_user.id}")

def is_coach(user_id: int) -> bool:
    return COACH_ID is not None and str(user_id) == str(COACH_ID)

async def deny_access(update: Update):
    await update.message.reply_text("У тебя нет доступа к этой команде.")

def get_player_menu():
    keyboard = [
        ["Подать заявку", "Мой статус"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_coach_menu():
    keyboard = [
        ["Новые заявки", "Одобренные игроки"],
        ["Запланированные рассылки", "Напомнить об оплате"],
        ["Напомнить о тренировке", "Ответы на тренировку"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing_user = get_user_by_id(user.id)

    if not existing_user:
        await update.message.reply_text("Ты ещё не отправлял заявку тренеру.")
        return

    status = existing_user[3]

    if status == "pending":
        text = "Твоя заявка сейчас на рассмотрении у тренера."
    elif status == "approved":
        text = "Ты одобрен тренером и получаешь уведомления."
    elif status == "rejected":
        text = "Твоя заявка была отклонена. Ты можешь подать её снова."
    else:
        text = f"Текущий статус: {status}"

    await update.message.reply_text(text)

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Подать заявку":
        user = update.effective_user
        existing_user = get_user_by_id(user.id)

        if existing_user and existing_user[3] == "approved":
            await update.message.reply_text("Ты уже одобрен тренером и получаешь уведомления.")
            return

        add_or_update_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            status="pending"
        )

        await update.message.reply_text("Твоя заявка отправлена тренеру. Ожидай подтверждения.")
        await notify_coach_about_request(context, user.id)
        return

    if text == "Мой статус":
        await my_status(update, context)
        return

    if text == "Новые заявки":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await coach(update, context)
        return

    if text == "Одобренные игроки":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await approved(update, context)
        return

    if text == "Запланированные рассылки":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await list_scheduled(update, context)
        return

    if text == "Напомнить об оплате":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await send_payment_reminder_by_month(update, context)
        return

    if text == "Напомнить о тренировке":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await send_training_reminder(update, context)
        return

    if text == "Ответы на тренировку":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await show_training_responses(update, context)
        return

async def notify_coach_about_request(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if not COACH_ID:
        return

    existing_user = get_user_by_id(user_id)
    if not existing_user:
        return

    request_user_id, username, first_name, status = existing_user

    text = "Новая заявка\n\n"
    text += f"ID: {request_user_id}"
    if first_name:
        text += f"\nИмя: {first_name}"
    if username:
        text += f"\nusername: @{username}"
    text += f"\nСтатус: {status}"

    keyboard = [[
        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{request_user_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_user_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            chat_id=int(COACH_ID),
            text=text,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Не удалось отправить заявку тренеру: {e}")

def get_month_name_prepositional(dt: datetime) -> str:
    months = {
        1: "январе",
        2: "феврале",
        3: "марте",
        4: "апреле",
        5: "мае",
        6: "июне",
        7: "июле",
        8: "августе",
        9: "сентябре",
        10: "октябре",
        11: "ноябре",
        12: "декабре",
    }
    return months[dt.month]

async def send_payment_reminder_by_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    approved_users = get_users_by_status("approved")

    if not approved_users:
        await update.message.reply_text("Нет одобренных игроков для рассылки.")
        return

    month_name = get_month_name_prepositional(datetime.now(TIMEZONE))
    message_text = f"Напоминаю об оплате за тренировку в {month_name}."

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if str(user_id) == str(COACH_ID):
            continue

        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except Exception:
            fail_count += 1

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

    approved_users = get_users_by_status("approved")

    if not approved_users:
        await update.message.reply_text("Нет одобренных игроков для рассылки.")
        return

    clear_training_responses()

    message_text = (
        "Сегодня тренировка в 21:00.\n"
        "Локация: https://2gis.kz/almaty/geo/9430098963876822/76.921711,43.237997\n"
        "Пожалуйста, ответь, придёшь ли ты."
    )

    keyboard = [[
        InlineKeyboardButton("✅ Приду", callback_data="training_yes"),
        InlineKeyboardButton("❌ Не приду", callback_data="training_no")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    success_count = 0
    fail_count = 0

    for user_id, username, first_name in approved_users:
        if str(user_id) == str(COACH_ID):
            continue

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup
            )
            success_count += 1
        except Exception:
            fail_count += 1

    await update.message.reply_text(
        f"Напоминание о тренировке отправлено.\n"
        f"Успешно: {success_count}\n"
        f"Ошибок: {fail_count}"
    )

async def show_training_responses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await deny_access(update)
        return

    responses = get_all_training_responses()

    if not responses:
        await update.message.reply_text("Пока нет ответов на тренировку.")
        return

    coming = []
    not_coming = []

    for user_id, username, first_name, response in responses:
        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"

        if response == "yes":
            coming.append(name)
        elif response == "no":
            not_coming.append(name)

    text = "Ответы на тренировку:\n\n"

    text += "✅ Придут:\n"
    text += "\n".join(coming) if coming else "Пока никто"
    text += "\n\n"

    text += "❌ Не придут:\n"
    text += "\n".join(not_coming) if not_coming else "Пока никто"

    await update.message.reply_text(text)

def main():
    if not BOT_TOKEN:
        raise ValueError("В файле .env не найден BOT_TOKEN")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", my_id))
    app.add_handler(CommandHandler("coach", coach))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("approved", approved))
    app.add_handler(CommandHandler("send", send_message_to_approved))
    app.add_handler(CommandHandler("schedule", schedule_message))
    app.add_handler(CommandHandler("scheduled", list_scheduled))
    app.add_handler(CommandHandler("reject", reject))
    app.add_handler(CommandHandler("delete_schedule", delete_schedule))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    restore_jobs(app)

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()