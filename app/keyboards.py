from calendar import monthrange
from datetime import datetime

from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

from app.config import TIMEZONE


MONTHS_RU = [
    ("Январь", 1),
    ("Февраль", 2),
    ("Март", 3),
    ("Апрель", 4),
    ("Май", 5),
    ("Июнь", 6),
    ("Июль", 7),
    ("Август", 8),
    ("Сентябрь", 9),
    ("Октябрь", 10),
    ("Ноябрь", 11),
    ("Декабрь", 12),
]


def get_player_menu():
    keyboard = [
        ["Подать заявку", "Мой статус"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


PLAYER_MENU_LABELS = {
    "ru": {
        "my_status": "Мой статус",
        "payment_status": "Статус оплаты",
        "training_schedule": "График тренировок",
        "playbook": "Playbook",
        "game_schedule": "График игр",
        "documents": "Документация",
        "bonuses": "Бонусы",
        "training_video": "Обучающее видео",
        "language": "🌐 Язык / Тіл / Language",
    },
    "kk": {
        "my_status": "Менің мәртебем",
        "payment_status": "Төлем мәртебесі",
        "training_schedule": "Жаттығу кестесі",
        "playbook": "Playbook",
        "game_schedule": "Ойындар кестесі",
        "documents": "Құжаттар",
        "bonuses": "Бонустар",
        "training_video": "Оқу видеолары",
        "language": "🌐 Тіл",
    },
    "en": {
        "my_status": "My status",
        "payment_status": "Payment status",
        "training_schedule": "Training schedule",
        "playbook": "Playbook",
        "game_schedule": "Game schedule",
        "documents": "Documents",
        "bonuses": "Bonuses",
        "training_video": "Training videos",
        "language": "🌐 Language",
    },
}


def normalize_language_code(language_code: str | None) -> str:
    if language_code in PLAYER_MENU_LABELS:
        return language_code

    return "ru"


def get_approved_player_menu(language_code: str = "ru"):
    labels = PLAYER_MENU_LABELS[normalize_language_code(language_code)]

    keyboard = [
        [labels["my_status"], labels["payment_status"]],
        [labels["training_schedule"], labels["playbook"]],
        [labels["game_schedule"], labels["documents"]],
        [labels["bonuses"], labels["training_video"]],
        [labels["language"]],
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_language_menu():
    keyboard = [
        ["🇷🇺 Русский"],
        ["🇰🇿 Қазақша"],
        ["🇬🇧 English"],
        ["Назад"],
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
        ["Обновить меню игрокам"],
        ["Обновить меню"],
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


def get_games_month_menu():
    """
    Меню выбора месяца для добавления матча.

    Год тренер не выбирает — бот определит его сам:
    - если месяц ещё впереди в текущем году, берётся текущий год;
    - если месяц уже прошёл, берётся следующий год.
    """
    keyboard = [
        ["Январь", "Февраль", "Март"],
        ["Апрель", "Май", "Июнь"],
        ["Июль", "Август", "Сентябрь"],
        ["Октябрь", "Ноябрь", "Декабрь"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_game_days_menu(month: int, year: int | None = None):
    """
    Меню выбора дня матча для выбранного месяца.

    Если year не передан, бот сам определяет год.
    """
    if year is None:
        year = resolve_year_for_month(month)

    days_in_month = monthrange(year, month)[1]

    keyboard = []
    row = []

    for day in range(1, days_in_month + 1):
        row.append(str(day))

        if len(row) == 4:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append(["Назад"])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_game_input_cancel_menu():
    """
    Меню для шагов ввода:
    - имя соперника;
    - время матча;
    - ссылка на место проведения.
    """
    keyboard = [
        ["Отменить добавление матча"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_game_time_examples_menu():
    """
    Подсказка для ввода времени матча.
    Тренер может нажать готовый вариант или написать вручную.
    """
    keyboard = [
        ["10:00", "12:00", "14:00"],
        ["16:00", "18:00", "20:00"],
        ["Отменить добавление матча"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_game_location_skip_menu():
    """
    Меню для ввода ссылки на место проведения.
    Можно пропустить, если ссылка пока неизвестна.
    """
    keyboard = [
        ["Пропустить ссылку"],
        ["Отменить добавление матча"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def resolve_year_for_month(month: int) -> int:
    """
    Автоматически определяет год для выбранного месяца.

    Пример:
    сейчас май 2026:
    - июнь -> 2026
    - декабрь -> 2026
    - январь -> 2027
    """
    now = datetime.now(TIMEZONE)

    if month >= now.month:
        return now.year

    return now.year + 1


def get_month_number_by_name(month_name: str) -> int | None:
    """
    Возвращает номер месяца по русскому названию.
    """
    normalized = month_name.strip().lower()

    for name, number in MONTHS_RU:
        if name.lower() == normalized:
            return number

    return None


def get_month_name_by_number(month: int) -> str:
    """
    Возвращает русское название месяца по номеру.
    """
    for name, number in MONTHS_RU:
        if number == month:
            return name

    return str(month)

def get_training_video_links_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(
                "🎥 Открыть YouTube-канал",
                url="https://www.youtube.com/@36%D0%A1%D1%82%D1%83%D0%B4%D0%B8%D1%8F"
            )
        ],
        [
            InlineKeyboardButton(
                "🏈 Лекция 1",
                url="https://www.youtube.com/watch?v=gUgExXMlAHQ&list=PLZ8Fx36DixRqT2xj8t8Fg5ZKmyw975ukC"
            )
        ],
        [
            InlineKeyboardButton(
                "🏃 Лекция 2",
                url="https://www.youtube.com/watch?v=_xA4Yn9QVFM&list=PLZ8Fx36DixRqT2xj8t8Fg5ZKmyw975ukC&index=2"
            )
        ],
        [
            InlineKeyboardButton(
                "🛡 Лекция 3",
                url="https://www.youtube.com/watch?v=MnlPSHuGqC4&list=PLZ8Fx36DixRqT2xj8t8Fg5ZKmyw975ukC&index=3"
            )
        ],
        [
            InlineKeyboardButton(
                "🛡 Лекция 4",
                url="https://www.youtube.com/watch?v=Xyy7i3tGRrY&list=PLZ8Fx36DixRqT2xj8t8Fg5ZKmyw975ukC&index=4"
            )
        ],
        [
            InlineKeyboardButton(
                "🛡 Лекция 5",
                url="https://www.youtube.com/watch?v=dLeCd5DM_3w&list=PLZ8Fx36DixRqT2xj8t8Fg5ZKmyw975ukC&index=5"
            )
        ],
        [
            InlineKeyboardButton(
                "📚 Плейлист",
                url="https://youtube.com/playlist?list=PLZ8Fx36DixRqT2xj8t8Fg5ZKmyw975ukC&si=TW3PrWh6nfv6ixGM"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)