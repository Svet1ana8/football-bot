from telegram import Update
from telegram.ext import ContextTypes

from app.handlers.common import deny_access
from app.repositories.users import add_or_update_user, get_user_by_id
from app.services.access import is_coach
from app.services.notifications import notify_coaches_about_request
from app.handlers.coach import (
    approved,
    coach,
    list_scheduled,
    send_payment_reminder_by_month,
    send_training_reminder,
    show_training_responses,
    open_payments_menu,
    show_ending_soon,
    show_unpaid_players,
    open_mark_payment,
    back_to_coach_menu,
)


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
        await notify_coaches_about_request(context, user.id)
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

    if text == "Ответы на голосование":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await show_training_responses(update, context)
        return

    if text == "Оплаты":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await open_payments_menu(update, context)
        return

    if text == "У кого скоро заканчивается":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await show_ending_soon(update, context)
        return

    if text == "Кто не оплатил":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await show_unpaid_players(update, context)
        return

    if text == "Отметить оплату":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await open_mark_payment(update, context)
        return

    if text == "Назад":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await back_to_coach_menu(update, context)
        return
