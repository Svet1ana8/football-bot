from telegram import ReplyKeyboardMarkup


from telegram import ReplyKeyboardMarkup


def get_player_menu():
    keyboard = [
        ["Подать заявку", "Мой статус"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_approved_player_menu():
    keyboard = [
        ["Мой статус", "Статус оплаты"],
        ["График тренировок", "Playbook"],
        ["График игр", "Документация"],
        ["Бонусы", "Обучающее видео"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_playbook_menu():
    keyboard = [
        ["Нападение", "Защита"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_documents_menu():
    keyboard = [
        ["Правила игры IFAF 2025"],
        ["Регламент ЧРК"],
        ["Руководство по судейству"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_video_menu():
    keyboard = [
        ["Видео: Нападение", "Видео: Защита"],
        ["Видео: Спецкоманды"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_offense_video_menu():
    keyboard = [
        ["Видео: Линейные нападение", "Видео: Принимающие"],
        ["Видео: Квотербек", "Видео: Бегущие"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_defense_video_menu():
    keyboard = [
        ["Видео: Линейные защита", "Видео: Лайнбекеры"],
        ["Видео: Корнеры", "Видео: Сейфти"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_special_teams_video_menu():
    keyboard = [
        ["Видео: Кикер", "Видео: Лонгснэппер"],
        ["Видео: Пантер"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_coach_menu():
    keyboard = [
        ["Новые заявки", "Одобренные игроки"],
        ["Напомнить об оплате", "Напомнить о тренировке"],
        ["Ответы на голосование", "Статус напоминания"],
        ["Посещаемость", "Календарь тренировок"],
        ["Календарь игр", "Оплаты"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_payments_menu():
    keyboard = [
        ["У кого скоро заканчивается"],
        ["Изменить тип абонемента"],
        ["Кто не оплатил"],
        ["Отметить оплату"],
        ["Все абонементы"],
        ["История оплат"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_training_schedule_menu():
    keyboard = [
        ["Показать календарь тренировок"],
        ["Добавить тренировку"],
        ["Удалить тренировку"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_games_schedule_menu():
    keyboard = [
        ["Показать календарь игр"],
        ["Добавить матч"],
        ["Удалить матч"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)