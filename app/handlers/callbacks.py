from telegram import Update
from telegram.ext import ContextTypes

from app.repositories.trainings import save_training_response
from app.repositories.users import add_or_update_user, delete_user, get_user_by_id
from app.services.access import is_coach
from app.services.notifications import notify_coaches_about_request


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

        await query.edit_message_text(f"✅ Пользователь {target_user_id} одобрен.")

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

        await query.edit_message_text(f"❌ Пользователь {target_user_id} отклонён.")

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

    if data.startswith("delete_player_"):
        if not is_coach(query.from_user.id):
            await query.edit_message_text("У тебя нет доступа к этому действию.")
            return

        target_user_id = int(data.split("_")[2])
        deleted = delete_user(target_user_id)

        if deleted:
            await query.edit_message_text(f"🗑 Игрок {target_user_id} удалён из базы.")
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
