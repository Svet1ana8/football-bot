from telegram import Update
from telegram.ext import ContextTypes

from app.handlers.common import deny_access
from app.handlers.coach import (
    approved,
    back_to_coach_menu,
    coach,
    list_scheduled,
    open_mark_payment,
    open_payments_menu,
    send_payment_reminder_by_month,
    send_training_reminder,
    show_all_subscriptions,
    show_ending_soon,
    show_payment_history,
    show_training_responses,
    show_training_status,
    show_unpaid_players,
)
from app.keyboards import get_approved_player_menu, get_learning_menu, get_playbook_menu
from app.repositories.payments import get_subscription_by_user_id
from app.repositories.users import add_or_update_user, get_user_by_id
from app.services.access import is_coach
from app.services.notifications import notify_coaches_about_request
from app.repositories.trainings import get_player_training_stats


async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing_user = get_user_by_id(user.id)

    if not existing_user:
        await update.message.reply_text(
            "📭 Заявка ещё не отправлена.\n\n"
            "Нажми кнопку «Подать заявку», чтобы тренер увидел тебя."
        )
        return

    status = existing_user[3]

    if status == "pending":
        await update.message.reply_text(
            "⏳ Статус заявки: на рассмотрении\n\n"
            "Тренер ещё не принял решение."
        )
        return

    if status == "rejected":
        await update.message.reply_text(
            "❌ Статус заявки: отклонена\n\n"
            "Ты можешь подать заявку повторно."
        )
        return

    if status != "approved":
        await update.message.reply_text(f"ℹ️ Текущий статус: {status}")
        return

    subscription = get_subscription_by_user_id(user.id)

    text = "✅ Твой статус: одобрен\n\n"

    if not subscription:
        text += "💳 Данные абонемента пока не заполнены."
        await update.message.reply_text(text)
        return

    (
        user_id,
        payment_day,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        has_custom_schedule,
        payment_claimed,
    ) = subscription

    end_date_text = subscription_end_date.strftime("%d.%m.%Y") if subscription_end_date else "Не указана"
    last_payment_text = last_payment_date.strftime("%d.%m.%Y") if last_payment_date else "Не указана"
    paid_text = "Да" if is_paid_current_period else "Нет"
    claimed_text = "Да" if payment_claimed else "Нет"

    text += (
        f"💳 Абонемент до: {end_date_text}\n"
        f"📅 Дата оплаты: {last_payment_text}\n"
        f"✅ Оплата подтверждена: {paid_text}\n"
        f"💸 Кнопка «Оплатил»: {claimed_text}"
    )

    await update.message.reply_text(text)


async def show_training_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 График тренировок скоро будет добавлен.")


async def show_player_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏈 Твоя позиция пока не заполнена.")


async def show_team_roster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👥 Состав команды скоро будет добавлен.")


async def show_attendance_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_player_training_stats(update.effective_user.id)

    if not stats:
        await update.message.reply_text("📊 Статистика тренировок пока недоступна.")
        return

    yes_count, no_count, total_count = stats

    yes_count = yes_count or 0
    no_count = no_count or 0
    total_count = total_count or 0

    await update.message.reply_text(
        "📊 Статистика тренировок\n\n"
        f"✅ Ответов «Приду»: {yes_count}\n"
        f"❌ Ответов «Не приду»: {no_count}\n"
        f"📌 Всего ответов: {total_count}"
    )


async def show_payment_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await my_status(update, context)


async def open_playbook_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Плейбук. Выбери раздел:",
        reply_markup=get_playbook_menu()
    )


async def show_offense_playbook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Раздел «Нападение» скоро будет заполнен.")


async def show_defense_playbook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡 Раздел «Защита» скоро будет заполнен.")


async def show_training_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎥 Обучающее видео скоро будет добавлено.")


async def show_games_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏆 График игр скоро будет добавлен.")


async def open_learning_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 Обучение. Выбери раздел:",
        reply_markup=get_learning_menu()
    )


async def show_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Документация скоро будет добавлена.")


async def show_recovery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💪 Раздел по восстановлению скоро будет добавлен.")


async def show_pre_game_tips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏟 Рекомендации перед игрой скоро будут добавлены.")


async def show_bonuses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎁 Раздел «Бонусы» скоро будет добавлен.")


async def back_to_player_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Возвращаю в меню игрока.",
        reply_markup=get_approved_player_menu()
    )


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

    if text == "График тренировок":
        await show_training_schedule(update, context)
        return

    if text == "Моя позиция":
        await show_player_position(update, context)
        return

    if text == "Состав команды":
        await show_team_roster(update, context)
        return

    if text == "Количество посещенных тренировок":
        await show_attendance_count(update, context)
        return

    if text == "Статус оплаты":
        await show_payment_status(update, context)
        return

    if text == "Плейбук":
        await open_playbook_menu(update, context)
        return

    if text == "Нападение":
        await show_offense_playbook(update, context)
        return

    if text == "Защита":
        await show_defense_playbook(update, context)
        return

    if text == "Обучающее видео":
        await show_training_videos(update, context)
        return

    if text == "График игр":
        await show_games_schedule(update, context)
        return

    if text == "Обучение":
        await open_learning_menu(update, context)
        return

    if text == "Документация":
        await show_docs(update, context)
        return

    if text == "Как восстанавливаться после игры и тренировок":
        await show_recovery(update, context)
        return

    if text == "Рекомендации перед игрой":
        await show_pre_game_tips(update, context)
        return

    if text == "Бонусы":
        await show_bonuses(update, context)
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

    if text == "Статус напоминания":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await show_training_status(update, context)
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

    if text == "Все абонементы":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await show_all_subscriptions(update, context)
        return

    if text == "История оплат":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await show_payment_history(update, context)
        return

    if text == "Назад":
        if is_coach(update.effective_user.id):
            await back_to_coach_menu(update, context)
            return
        await back_to_player_menu(update, context)
        return