from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import COACH_IDS
from app.keyboards import get_approved_player_menu, get_player_menu
from app.repositories.payments import (
    add_payment_history,
    confirm_payment,
    create_subscription_for_user,
    mark_payment_claimed,
    reject_claimed_payment,
)
from app.repositories.users import add_or_update_user, delete_user, get_user_by_id
from app.services.access import is_coach
from app.services.notifications import notify_coaches_about_request
from app.services.trainings import (
    build_training_message,
    get_change_answer_confirm_keyboard,
    get_change_answer_keyboard,
    get_training_keyboard,
    save_player_training_response,
)


def get_display_name(user_id: int, fallback_first_name: str | None = None, fallback_username: str | None = None) -> str:
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

        await query.answer("Ответ сохранён")
        await query.edit_message_text(
            "✅ Ты отметил(а), что придёшь на тренировку.",
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

        await query.answer("Ответ сохранён")
        await query.edit_message_text(
            "❌ Ты отметил(а), что не придёшь на тренировку.",
            reply_markup=get_change_answer_keyboard(training_id)
        )
        return

    if data.startswith("change_training_answer_"):
        training_id = int(data.split("_")[3])

        await query.answer("Можно изменить ответ")
        await query.edit_message_text(
            "Сегодня тренировка в 21:00.\n"
                "Локация: https://2gis.kz/almaty/geo/9430098963876822/76.921711,43.237997\n"
                "Ты хочешь изменить свой ответ?",
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

    if data.startswith("confirm_payment_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        target_user_id = int(data.split("_")[2])
        target_user = get_user_by_id(target_user_id)
        player_name = target_user[2] if target_user and target_user[2] else str(target_user_id)

        today = date.today()
        new_end_date = today + timedelta(days=30)

        confirm_payment(
            user_id=target_user_id,
            today=today,
            new_end_date=new_end_date
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