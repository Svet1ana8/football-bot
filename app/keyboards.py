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

        "back": "Назад",
        "offense": "Нападение",
        "defense": "Защита",

        "ifaf_rules": "Правила игры IFAF 2025",
        "chrk_regulations": "Регламент ЧРК",
        "refereeing_guide": "Руководство по судейству",

        "video_offense": "Видео: Нападение",
        "video_defense": "Видео: Защита",
        "video_special_teams": "Видео: Спецкоманды",
        "video_linear_offense": "Видео: Линейные нападение",
        "video_receivers": "Видео: Принимающие",
        "video_qb": "Видео: Квотербек",
        "video_running_backs": "Видео: Бегущие",
        "video_linear_defense": "Видео: Линейные защита",
        "video_linebackers": "Видео: Лайнбекеры",
        "video_corners": "Видео: Корнеры",
        "video_safeties": "Видео: Сейфти",
        "video_kicker": "Видео: Кикер",
        "video_longsnapper": "Видео: Лонгснэппер",
        "video_punter": "Видео: Пантер",
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

        "back": "Артқа",
        "offense": "Шабуыл",
        "defense": "Қорғаныс",

        "ifaf_rules": "IFAF 2025 ойын ережелері",
        "chrk_regulations": "ҚРЧ регламенті",
        "refereeing_guide": "Төрешілік нұсқаулығы",

        "video_offense": "Видео: Шабуыл",
        "video_defense": "Видео: Қорғаныс",
        "video_special_teams": "Видео: Арнайы командалар",
        "video_linear_offense": "Видео: Шабуыл шебі",
        "video_receivers": "Видео: Қабылдаушылар",
        "video_qb": "Видео: Квотербек",
        "video_running_backs": "Видео: Жүгіретін ойыншылар",
        "video_linear_defense": "Видео: Қорғаныс шебі",
        "video_linebackers": "Видео: Лайнбекерлер",
        "video_corners": "Видео: Корнерлер",
        "video_safeties": "Видео: Сейфти",
        "video_kicker": "Видео: Кикер",
        "video_longsnapper": "Видео: Лонгснэппер",
        "video_punter": "Видео: Пантер",
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

        "back": "Back",
        "offense": "Offense",
        "defense": "Defense",

        "ifaf_rules": "IFAF 2025 rules",
        "chrk_regulations": "KAF regulations",
        "refereeing_guide": "Refereeing guide",

        "video_offense": "Video: Offense",
        "video_defense": "Video: Defense",
        "video_special_teams": "Video: Special teams",
        "video_linear_offense": "Video: Offensive line",
        "video_receivers": "Video: Receivers",
        "video_qb": "Video: Quarterback",
        "video_running_backs": "Video: Running backs",
        "video_linear_defense": "Video: Defensive line",
        "video_linebackers": "Video: Linebackers",
        "video_corners": "Video: Corners",
        "video_safeties": "Video: Safeties",
        "video_kicker": "Video: Kicker",
        "video_longsnapper": "Video: Long snapper",
        "video_punter": "Video: Punter",
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


def get_language_menu(language_code: str = "ru"):
    labels = PLAYER_MENU_LABELS[normalize_language_code(language_code)]

    keyboard = [
        ["🇷🇺 Русский"],
        ["🇰🇿 Қазақша"],
        ["🇬🇧 English"],
        [labels["back"]],
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_playbook_menu(language_code: str = "ru"):
    labels = PLAYER_MENU_LABELS[normalize_language_code(language_code)]

    keyboard = [
        [labels["offense"], labels["defense"]],
        [labels["back"]],
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_documents_menu(language_code: str = "ru"):
    labels = PLAYER_MENU_LABELS[normalize_language_code(language_code)]

    keyboard = [
        [labels["ifaf_rules"]],
        [labels["chrk_regulations"]],
        [labels["refereeing_guide"]],
        [labels["back"]],
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_video_menu(language_code: str = "ru"):
    labels = PLAYER_MENU_LABELS[normalize_language_code(language_code)]

    keyboard = [
        [labels["video_offense"], labels["video_defense"]],
        [labels["video_special_teams"]],
        [labels["back"]],
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_offense_video_menu(language_code: str = "ru"):
    labels = PLAYER_MENU_LABELS[normalize_language_code(language_code)]

    keyboard = [
        [labels["video_linear_offense"], labels["video_receivers"]],
        [labels["video_qb"], labels["video_running_backs"]],
        [labels["back"]],
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_defense_video_menu(language_code: str = "ru"):
    labels = PLAYER_MENU_LABELS[normalize_language_code(language_code)]

    keyboard = [
        [labels["video_linear_defense"], labels["video_linebackers"]],
        [labels["video_corners"], labels["video_safeties"]],
        [labels["back"]],
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_special_teams_video_menu(language_code: str = "ru"):
    labels = PLAYER_MENU_LABELS[normalize_language_code(language_code)]

    keyboard = [
        [labels["video_kicker"], labels["video_longsnapper"]],
        [labels["video_punter"]],
        [labels["back"]],
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