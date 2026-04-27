from telegram import ReplyKeyboardMarkup


def get_player_menu():
    keyboard = [
        ["Подать заявку", "Мой статус"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_coach_menu():
    keyboard = [
        ["Новые заявки", "Одобренные игроки"],
        ["Запланированные рассылки", "Напомнить об оплате"],
        ["Напомнить о тренировке", "Ответы на голосование"],
        ["Оплаты"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_payments_menu():
    keyboard = [
        ["У кого скоро заканчивается"],
        ["Кто не оплатил"],
        ["Отметить оплату"],
        ["Все абонементы"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)