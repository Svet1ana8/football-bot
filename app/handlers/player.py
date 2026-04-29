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
    show_all_subscriptions,
    back_to_coach_menu,
)
from app.repositories.payments import get_subscription_by_user_id


async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing_user = get_user_by_id(user.id)

    if not existing_user:
        await update.message.reply_text("Ты ещё не отправлял заявку тренеру.")
        return

    status = existing_user[3]

    if status == "pending":
        text = "Твоя заявка сейчас на рассмотрении у тренера."
        await update.message.reply_text(text)
        return

    if status == "rejected":
        text = "Твоя заявка была отклонена. Ты можешь подать её снова."
        await update.message.reply_text(text)
        return

    if status != "approved":
        await update.message.reply_text(f"Текущий статус: {status}")
        return

    subscription = get_subscription_by_user_id(user.id)

    text = "Твой статус: одобрен ✅\n\n"

    if not subscription:
        text += "Данные абонемента пока не заполнены."
        await update.message.reply_text(text)
        return

    user_id, payment_day, subscription_end_date, last_payment_date, is_paid_current_period, has_custom_schedule, payment_claimed = subscription

    end_date_text = subscription_end_date.strftime("%d.%m.%Y") if subscription_end_date else "Не указана"
    last_payment_text = last_payment_date.strftime("%d.%m.%Y") if last_payment_date else "Не указана"
    paid_text = "Да" if is_paid_current_period else "Нет"
    custom_text = "Да" if has_custom_schedule else "Нет"
    claimed_text = "Да" if payment_claimed else "Нет"

    text += (
        f"Абонемент до: {end_date_text}\n"
        f"День оплаты: {payment_day}\n"
        f"Последняя оплата: {last_payment_text}\n"
        f"Оплачено в текущем периоде: {paid_text}\n"
        f"Особый график: {custom_text}\n"
        f"Отметка 'Оплатил': {claimed_text}"
    )

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

    if text == "Все абонементы":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await show_all_subscriptions(update, context)
        return
