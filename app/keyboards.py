from telegram import ReplyKeyboardMarkup


def get_player_menu():
    keyboard = [
        ["Подать заявку", "Мой статус"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_approved_player_menu():
    keyboard = [
        ["Мой статус", "Статус оплаты"],
        ["График тренировок", "Моя позиция"],
        ["Состав команды", "Количество посещенных тренировок"],
        ["Плейбук", "График игр"],
        ["Обучение"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_playbook_menu():
    keyboard = [
        ["Нападение", "Защита"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_learning_menu():
    keyboard = [
        ["Обучающие видео"],
        ["Документация"],
        ["Как восстанавливаться после игры и тренировок"],
        ["Рекомендации перед игрой"],
        ["Бонусы"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_coach_menu():
    keyboard = [
        ["Новые заявки", "Одобренные игроки"],
        ["Напомнить об оплате", "Напомнить о тренировке"],
        ["Ответы на голосование", "Статус напоминания"],
        ["Оплаты"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_payments_menu():
    keyboard = [
        ["У кого скоро заканчивается"],
        ["Кто не оплатил"],
        ["Отметить оплату"],
        ["Все абонементы"],
        ["История оплат"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)