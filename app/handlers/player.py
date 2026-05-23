from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.handlers.common import deny_access
from app.handlers.coach import (
    approved,
    back_to_coach_menu,
    coach,
    handle_training_schedule_add_input,
    handle_training_schedule_delete_input,
    open_mark_payment,
    open_payments_menu,
    open_subscription_type_menu,
    open_training_schedule_menu,
    send_payment_reminder_by_month,
    send_training_reminder,
    show_all_subscriptions,
    show_ending_soon,
    show_payment_history,
    show_training_calendar,
    show_training_responses,
    show_training_status,
    show_unpaid_players,
    show_month_attendance,
    start_add_training_schedule,
    start_delete_training_schedule,
)
from app.keyboards import (
    get_approved_player_menu,
    get_defense_video_menu,
    get_documents_menu,
    get_offense_video_menu,
    get_playbook_menu,
    get_special_teams_video_menu,
    get_video_menu,
)
from app.repositories.payments import get_subscription_by_user_id
from app.repositories.training_schedule import get_upcoming_training_schedule
from app.repositories.users import add_or_update_user, get_user_by_id
from app.services.access import is_coach
from app.services.notifications import notify_coaches_about_request


def get_days_until_next_payment(payment_day: int) -> int:
    today = date.today()

    if today.day <= payment_day:
        return payment_day - today.day

    next_month = today.month + 1
    next_year = today.year

    if next_month == 13:
        next_month = 1
        next_year += 1

    next_payment_date = date(next_year, next_month, payment_day)
    return (next_payment_date - today).days


def build_player_trainings_keyboard(schedule) -> list[tuple[str, InlineKeyboardMarkup]]:
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
                    callback_data=f"training_player_view_{schedule_id}",
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

    if status == "awaiting_name":
        await update.message.reply_text(
            "📝 Заявка ещё не завершена.\n\n"
            "Напиши своё имя и фамилию, чтобы отправить заявку тренеру."
        )
        return

    if status == "pending":
        await update.message.reply_text(
            "⏳ Твой статус: не одобрен\n\n"
            "Твоя заявка ещё на рассмотрении у тренера."
        )
        return

    if status == "rejected":
        await update.message.reply_text(
            "❌ Твой статус: не одобрен\n\n"
            "Ты можешь подать заявку повторно."
        )
        return

    if status != "approved":
        await update.message.reply_text(f"ℹ️ Текущий статус: {status}")
        return

    subscription = get_subscription_by_user_id(user.id)

    text = "✅ Твой статус: одобрен\n"

    if not subscription:
        text += "\nАбонемент: не указан"
        await update.message.reply_text(text)
        return

    (
        user_id,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) = subscription

    subscription_type_text = "месячный"
    if subscription_type == "game":
        subscription_type_text = "игровой"

    text += f"\nАбонемент: {subscription_type_text}"
    await update.message.reply_text(text)


async def show_payment_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subscription = get_subscription_by_user_id(update.effective_user.id)

    if not subscription:
        await update.message.reply_text("💳 Данные по оплате пока не заполнены.")
        return

    (
        user_id,
        payment_day,
        subscription_type,
        subscription_end_date,
        last_payment_date,
        is_paid_current_period,
        _has_custom_schedule,
        payment_claimed,
    ) = subscription

    paid_text = "да" if is_paid_current_period else "нет"
    days_left = get_days_until_next_payment(payment_day)

    await update.message.reply_text(
        "💳 Статус оплаты\n\n"
        f"Оплачено: {paid_text}\n"
        f"Осталось дней: {days_left}"
    )


async def show_training_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    schedule = get_upcoming_training_schedule()

    if not schedule:
        await update.message.reply_text("📅 График тренировок пока пуст.")
        return

    await update.message.reply_text("📅 График тренировок")

    month_keyboards = build_player_trainings_keyboard(schedule)

    for title, reply_markup in month_keyboards:
        await update.message.reply_text(title, reply_markup=reply_markup)


async def open_playbook_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Playbook. Выбери раздел:",
        reply_markup=get_playbook_menu()
    )


async def show_offense_playbook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Документ по разделу «Нападение» скоро будет добавлен.")


async def show_defense_playbook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Документ по разделу «Защита» скоро будет добавлен.")


async def show_games_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏆 График игр скоро будет добавлен в виде календаря.")


async def open_documents_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Документация. Выбери документ:",
        reply_markup=get_documents_menu()
    )


async def show_ifaf_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📘 Правила игры по американскому футболу IFAF 2025 скоро будут добавлены.")


async def show_chrk_regulations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Регламент ЧРК скоро будет добавлен.")


async def show_refereeing_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧑‍⚖️ Руководство по судейству скоро будет добавлено.")


async def show_bonuses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎁 Бонусы\n\n"
        "Скидка за посещение всех тренировок: нет\n"
        "Бесплатный абонемент за приведенного игрока: нет"
    )


async def open_video_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎥 Обучающее видео. Выбери раздел:",
        reply_markup=get_video_menu()
    )


async def open_offense_video_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎥 Обучающее видео / Нападение",
        reply_markup=get_offense_video_menu()
    )


async def open_defense_video_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎥 Обучающее видео / Защита",
        reply_markup=get_defense_video_menu()
    )


async def open_special_teams_video_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎥 Обучающее видео / Спецкоманды",
        reply_markup=get_special_teams_video_menu()
    )


async def show_video_linear_offense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: линейные (нападение) скоро будет добавлено.")


async def show_video_receivers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: принимающие скоро будет добавлено.")


async def show_video_qb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: квотербек скоро будет добавлено.")


async def show_video_running_backs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: бегущие скоро будет добавлено.")


async def show_video_linear_defense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: линейные (защита) скоро будет добавлено.")


async def show_video_linebackers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: лайнбекеры скоро будет добавлено.")


async def show_video_corners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: корнеры скоро будет добавлено.")


async def show_video_safeties(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: сейфти скоро будет добавлено.")


async def show_video_kicker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: кикер скоро будет добавлено.")


async def show_video_longsnapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: лонгснэппер скоро будет добавлено.")


async def show_video_punter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Видео для позиции: пантер скоро будет добавлено.")


async def back_to_player_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Возвращаю в меню игрока.",
        reply_markup=get_approved_player_menu()
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    existing_user = get_user_by_id(user.id)

    if text == "Назад":
        context.user_data["awaiting_training_schedule_add"] = False
        context.user_data["awaiting_training_schedule_delete"] = False
        context.user_data["awaiting_training_schedule_manual_date"] = False
        context.user_data.pop("transfer_training_schedule_id", None)

        if is_coach(update.effective_user.id):
            await back_to_coach_menu(update, context)
            return
        await back_to_player_menu(update, context)
        return

    if text == "Календарь тренировок":
        context.user_data["awaiting_training_schedule_add"] = False
        context.user_data["awaiting_training_schedule_delete"] = False
        context.user_data["awaiting_training_schedule_manual_date"] = False
        context.user_data.pop("transfer_training_schedule_id", None)

        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await open_training_schedule_menu(update, context)
        return

    if text == "Показать календарь тренировок":
        context.user_data["awaiting_training_schedule_add"] = False
        context.user_data["awaiting_training_schedule_delete"] = False
        context.user_data["awaiting_training_schedule_manual_date"] = False
        context.user_data.pop("transfer_training_schedule_id", None)

        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await show_training_calendar(update, context)
        return

    if text == "Добавить тренировку":
        context.user_data["awaiting_training_schedule_delete"] = False
        context.user_data["awaiting_training_schedule_manual_date"] = False
        context.user_data.pop("transfer_training_schedule_id", None)

        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await start_add_training_schedule(update, context)
        return

    if text == "Удалить тренировку":
        context.user_data["awaiting_training_schedule_add"] = False
        context.user_data["awaiting_training_schedule_manual_date"] = False
        context.user_data.pop("transfer_training_schedule_id", None)

        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await start_delete_training_schedule(update, context)
        return

    if is_coach(user.id) and context.user_data.get("awaiting_training_schedule_manual_date"):
        await handle_training_schedule_add_input(update, context)
        return

    if is_coach(user.id) and context.user_data.get("awaiting_training_schedule_add"):
        await handle_training_schedule_add_input(update, context)
        return

    if is_coach(user.id) and context.user_data.get("awaiting_training_schedule_delete"):
        await handle_training_schedule_delete_input(update, context)
        return

    if existing_user and existing_user[3] == "awaiting_name":
        full_name = text

        if len(full_name.split()) < 2:
            await update.message.reply_text(
                "Пожалуйста, напиши имя и фамилию полностью.\n\n"
                "Например: Иванов Иван"
            )
            return

        add_or_update_user(
            user_id=user.id,
            username=user.username,
            first_name=full_name,
            status="pending"
        )

        await update.message.reply_text(
            f"✅ Заявка отправлена тренеру.\n\n"
            f"Имя: {full_name}"
        )
        await notify_coaches_about_request(context, user.id)
        return

    if text == "Подать заявку":
        if existing_user and existing_user[3] == "approved":
            await update.message.reply_text("Ты уже одобрен тренером и получаешь уведомления.")
            return

        add_or_update_user(
            user_id=user.id,
            username=user.username,
            first_name=existing_user[2] if existing_user else user.first_name,
            status="awaiting_name"
        )

        await update.message.reply_text(
            "Напиши своё имя и фамилию.\n\n"
            "Например: Иванов Иван"
        )
        return

    if text == "Мой статус":
        await my_status(update, context)
        return

    if text == "Статус оплаты":
        await show_payment_status(update, context)
        return

    if text == "График тренировок":
        await show_training_schedule(update, context)
        return

    if text == "Playbook":
        await open_playbook_menu(update, context)
        return

    if text == "Нападение":
        await show_offense_playbook(update, context)
        return

    if text == "Защита":
        await show_defense_playbook(update, context)
        return

    if text == "График игр":
        await show_games_schedule(update, context)
        return

    if text == "Документация":
        await open_documents_menu(update, context)
        return

    if text == "Правила игры IFAF 2025":
        await show_ifaf_rules(update, context)
        return

    if text == "Регламент ЧРК":
        await show_chrk_regulations(update, context)
        return

    if text == "Руководство по судейству":
        await show_refereeing_guide(update, context)
        return

    if text == "Бонусы":
        await show_bonuses(update, context)
        return

    if text == "Обучающее видео":
        await open_video_menu(update, context)
        return

    if text == "Видео: Нападение":
        await open_offense_video_menu(update, context)
        return

    if text == "Видео: Защита":
        await open_defense_video_menu(update, context)
        return

    if text == "Видео: Спецкоманды":
        await open_special_teams_video_menu(update, context)
        return

    if text == "Видео: Линейные нападение":
        await show_video_linear_offense(update, context)
        return

    if text == "Видео: Принимающие":
        await show_video_receivers(update, context)
        return

    if text == "Видео: Квотербек":
        await show_video_qb(update, context)
        return

    if text == "Видео: Бегущие":
        await show_video_running_backs(update, context)
        return

    if text == "Видео: Линейные защита":
        await show_video_linear_defense(update, context)
        return

    if text == "Видео: Лайнбекеры":
        await show_video_linebackers(update, context)
        return

    if text == "Видео: Корнеры":
        await show_video_corners(update, context)
        return

    if text == "Видео: Сейфти":
        await show_video_safeties(update, context)
        return

    if text == "Видео: Кикер":
        await show_video_kicker(update, context)
        return

    if text == "Видео: Лонгснэппер":
        await show_video_longsnapper(update, context)
        return

    if text == "Видео: Пантер":
        await show_video_punter(update, context)
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

    if text == "Посещаемость":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await show_month_attendance(update, context)
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

    if text == "Изменить тип абонемента":
        if not is_coach(update.effective_user.id):
            await deny_access(update)
            return
        await open_subscription_type_menu(update, context)
        return