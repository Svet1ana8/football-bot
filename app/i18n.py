TEXTS = {
    "ru": {
        "payment_claim_sent": "Тренеру отправлено уведомление о том, что ты оплатил.",
        "application_approved": "Тренер одобрил твою заявку. Теперь ты будешь получать уведомления.",
        "application_rejected": "Твоя заявка была отклонена тренером.",
        "removed_from_players": "Ты был удалён из списка игроков. Если нужно, можешь снова подать заявку.",
        "subscription_type_monthly_updated": "Тренер обновил твой тип абонемента: месячный.",
        "subscription_type_game_updated": "Тренер обновил твой тип абонемента: игровой.",
        "payment_confirmed": "✅ Тренер подтвердил оплату.\nТвой абонемент продлён до {date}.",
        "payment_rejected": "Тренер пока не подтвердил оплату. Напоминания продолжатся.",
        "game_not_found": "Матч не найден.",
        "game_inactive": "Этот матч уже неактивен или был удалён.",
        "game_info_title": "🏆 Информация о матче",
        "date": "Дата",
        "time": "Время",
        "opponent": "Соперник",
        "additional": "Дополнительно",
        "location": "Место проведения",
        "not_set": "не указано",
    },
    "kk": {
        "payment_claim_sent": "Жаттықтырушыға сенің төлем жасағаның туралы хабарлама жіберілді.",
        "application_approved": "Жаттықтырушы сенің өтініміңді мақұлдады. Енді сен хабарламалар алып тұрасың.",
        "application_rejected": "Сенің өтініміңді жаттықтырушы қабылдамады.",
        "removed_from_players": "Сен ойыншылар тізімінен өшірілдің. Қажет болса, қайта өтінім бере аласың.",
        "subscription_type_monthly_updated": "Жаттықтырушы сенің абонемент түріңді жаңартты: айлық.",
        "subscription_type_game_updated": "Жаттықтырушы сенің абонемент түріңді жаңартты: ойындық.",
        "payment_confirmed": "✅ Жаттықтырушы төлемді растады.\nСенің абонементің {date} күніне дейін ұзартылды.",
        "payment_rejected": "Жаттықтырушы төлемді әзірге растаған жоқ. Төлем туралы еске салулар жалғасады.",
        "game_not_found": "Матч табылмады.",
        "game_inactive": "Бұл матч енді белсенді емес немесе өшірілген.",
        "game_info_title": "🏆 Матч туралы ақпарат",
        "date": "Күні",
        "time": "Уақыты",
        "opponent": "Қарсылас",
        "additional": "Қосымша",
        "location": "Өтетін орны",
        "not_set": "көрсетілмеген",
    },
    "en": {
        "payment_claim_sent": "The coach has been notified that you paid.",
        "application_approved": "The coach approved your application. You will now receive notifications.",
        "application_rejected": "Your application was rejected by the coach.",
        "removed_from_players": "You were removed from the players list. You can apply again if needed.",
        "subscription_type_monthly_updated": "The coach updated your subscription type: monthly.",
        "subscription_type_game_updated": "The coach updated your subscription type: game.",
        "payment_confirmed": "✅ The coach confirmed your payment.\nYour subscription has been extended until {date}.",
        "payment_rejected": "The coach has not confirmed your payment yet. Payment reminders will continue.",
        "game_not_found": "Match not found.",
        "game_inactive": "This match is no longer active or has been deleted.",
        "game_info_title": "🏆 Match information",
        "date": "Date",
        "time": "Time",
        "opponent": "Opponent",
        "additional": "Additional information",
        "location": "Location",
        "not_set": "not set",
    },
}


def t(language_code: str | None, key: str, **kwargs) -> str:
    if language_code not in TEXTS:
        language_code = "ru"

    text = TEXTS[language_code].get(key, TEXTS["ru"][key])

    if kwargs:
        return text.format(**kwargs)

    return text