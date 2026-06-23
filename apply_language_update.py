from pathlib import Path
import re
import sys


ROOT = Path.cwd()

KEYBOARDS_PATH = ROOT / "app" / "keyboards.py"
PLAYER_PATH = ROOT / "app" / "handlers" / "player.py"
USERS_PATH = ROOT / "app" / "repositories" / "users.py"


LANGUAGE_KEYBOARDS_BLOCK = """
PLAYER_MENU_TEXTS = {
    "ru": {
        "my_status": "Мой статус",
        "payment_status": "Статус оплаты",
        "training_schedule": "График тренировок",
        "playbook": "Playbook",
        "games_schedule": "График игр",
        "documents": "Документация",
        "bonuses": "Бонусы",
        "training_video": "Обучающее видео",
        "language": "🌐 Язык",
    },
    "kk": {
        "my_status": "Менің мәртебем",
        "payment_status": "Төлем мәртебесі",
        "training_schedule": "Жаттығу кестесі",
        "playbook": "Playbook",
        "games_schedule": "Ойындар кестесі",
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
        "games_schedule": "Games schedule",
        "documents": "Documents",
        "bonuses": "Bonuses",
        "training_video": "Training videos",
        "language": "🌐 Language",
    },
}


def get_player_menu_texts(language_code: str = "ru"):
    return PLAYER_MENU_TEXTS.get(language_code, PLAYER_MENU_TEXTS["ru"])


def get_player_menu_action(text: str):
    for language_texts in PLAYER_MENU_TEXTS.values():
        for action, button_text in language_texts.items():
            if text == button_text:
                return action

    return None


def get_language_select_menu():
    keyboard = [
        ["🇷🇺 Русский"],
        ["🇰🇿 Қазақша"],
        ["🇬🇧 English"],
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_approved_player_menu(language_code: str = "ru"):
    t = get_player_menu_texts(language_code)

    keyboard = [
        [t["my_status"], t["payment_status"]],
        [t["training_schedule"], t["playbook"]],
        [t["games_schedule"], t["documents"]],
        [t["bonuses"], t["training_video"]],
        [t["language"]],
    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
""".lstrip()


USER_LANGUAGE_FUNCTIONS = """
def ensure_language_column():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(\"\"\"
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS language_code TEXT NOT NULL DEFAULT 'ru'
            \"\"\")
        conn.commit()


def get_user_language(user_id: int) -> str:
    ensure_language_column()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(\"\"\"
                SELECT COALESCE(language_code, 'ru')
                FROM users
                WHERE user_id = %s
            \"\"\", (user_id,))
            row = cur.fetchone()

    if not row:
        return "ru"

    return row[0] or "ru"


def set_user_language(user_id: int, language_code: str):
    ensure_language_column()

    if language_code not in ("ru", "kk", "en"):
        language_code = "ru"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(\"\"\"
                UPDATE users
                SET language_code = %s
                WHERE user_id = %s
            \"\"\", (language_code, user_id))
        conn.commit()
""".lstrip()


LANGUAGE_CHOICE_BLOCK = """
    if text in ["🇷🇺 Русский", "🇰🇿 Қазақша", "🇬🇧 English"]:
        language_map = {
            "🇷🇺 Русский": "ru",
            "🇰🇿 Қазақша": "kk",
            "🇬🇧 English": "en",
        }

        selected_language = language_map[text]

        if not existing_user:
            await update.message.reply_text("Сначала подай заявку через /start.")
            return

        set_user_language(user.id, selected_language)

        language_names = {
            "ru": "Русский",
            "kk": "Қазақша",
            "en": "English",
        }

        await update.message.reply_text(
            f"✅ Язык изменён: {language_names[selected_language]}",
            reply_markup=get_approved_player_menu(selected_language)
        )
        return

"""


PLAYER_ACTION_BLOCK = """
    if player_action == "my_status":
        await my_status(update, context)
        return

    if player_action == "payment_status":
        await show_payment_status(update, context)
        return

    if player_action == "training_schedule":
        await show_training_schedule(update, context)
        return

    if player_action == "games_schedule":
        await show_games_schedule(update, context)
        return

    if player_action == "playbook":
        await open_playbook_menu(update, context)
        return

    if player_action == "documents":
        await open_documents_menu(update, context)
        return

    if player_action == "bonuses":
        await show_bonuses(update, context)
        return

    if player_action == "training_video":
        await update.message.reply_text(
            "🎥 Обучающие видео по американскому футболу\\n\\n"
            "Выбери нужную лекцию или открой весь плейлист:",
            reply_markup=get_training_video_links_keyboard()
        )
        return

    if player_action == "language":
        await update.message.reply_text(
            "🌐 Выбери язык / Тілді таңда / Choose language:",
            reply_markup=get_language_select_menu()
        )
        return

"""


def read_text(path: Path) -> str:
    if not path.exists():
        print(f"ERROR: файл не найден: {path}")
        sys.exit(1)

    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


def backup(path: Path):
    backup_path = path.with_suffix(path.suffix + ".bak_language")
    if not backup_path.exists():
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup создан: {backup_path}")
    else:
        print(f"Backup уже есть: {backup_path}")


def patch_keyboards():
    text = read_text(KEYBOARDS_PATH)
    backup(KEYBOARDS_PATH)

    if "PLAYER_MENU_TEXTS =" not in text:
        pattern = r"(?ms)^def get_approved_player_menu\([^)]*\):\n.*?(?=\n\ndef |\Z)"
        if re.search(pattern, text):
            text = re.sub(pattern, LANGUAGE_KEYBOARDS_BLOCK.rstrip(), text, count=1)
            print("keyboards.py: get_approved_player_menu заменён на языковую версию.")
        else:
            text = text.rstrip() + "\n\n\n" + LANGUAGE_KEYBOARDS_BLOCK.rstrip() + "\n"
            print("keyboards.py: языковой блок добавлен в конец файла.")
    else:
        print("keyboards.py: языковой блок уже есть, пропускаю.")

    write_text(KEYBOARDS_PATH, text)


def patch_users():
    text = read_text(USERS_PATH)
    backup(USERS_PATH)

    if "def get_user_language(" not in text:
        text = text.rstrip() + "\n\n\n" + USER_LANGUAGE_FUNCTIONS.rstrip() + "\n"
        print("users.py: добавлены функции языка.")
    else:
        print("users.py: функции языка уже есть, пропускаю.")

    write_text(USERS_PATH, text)


def add_to_import_block(text: str, import_start: str, names: list[str]) -> str:
    start = text.find(import_start)
    if start == -1:
        return text

    end = text.find(")", start)
    if end == -1:
        return text

    block = text[start:end]
    for name in names:
        if name not in block:
            block += f"    {name},\n"

    return text[:start] + block + text[end:]


def patch_player():
    text = read_text(PLAYER_PATH)
    backup(PLAYER_PATH)

    text = add_to_import_block(
        text,
        "from app.keyboards import (\n",
        ["get_language_select_menu", "get_player_menu_action"],
    )

    old_import = "from app.repositories.users import add_or_update_user, get_user_by_id"
    new_import = "from app.repositories.users import add_or_update_user, get_user_by_id, get_user_language, set_user_language"

    if new_import not in text and old_import in text:
        text = text.replace(old_import, new_import)
        print("player.py: импорт users обновлён.")
    elif new_import in text:
        print("player.py: импорт users уже обновлён.")
    else:
        print("WARNING: не нашёл ожидаемый импорт users. Проверь player.py вручную.")

    back_pattern = r"(?ms)^async def back_to_player_menu\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):\n.*?(?=\n\nasync def menu_handler)"
    back_new = """async def back_to_player_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language_code = get_user_language(update.effective_user.id)

    await update.message.reply_text(
        "Возвращаю в меню игрока.",
        reply_markup=get_approved_player_menu(language_code)
    )"""

    if re.search(back_pattern, text):
        text = re.sub(back_pattern, back_new, text, count=1)
        print("player.py: back_to_player_menu обновлён.")
    else:
        print("WARNING: не нашёл back_to_player_menu. Проверь player.py вручную.")

    marker = "    existing_user = get_user_by_id(user.id)\n"
    insert = (
        marker
        + "    language_code = get_user_language(user.id)\n"
        + "    player_action = get_player_menu_action(text)\n"
    )

    if "player_action = get_player_menu_action(text)" not in text:
        if marker in text:
            text = text.replace(marker, insert, 1)
            print("player.py: добавлены language_code и player_action.")
        else:
            print("WARNING: не нашёл строку existing_user = get_user_by_id(user.id).")
    else:
        print("player.py: player_action уже есть, пропускаю.")

    if 'if text in ["🇷🇺 Русский", "🇰🇿 Қазақша", "🇬🇧 English"]:' not in text:
        nav_marker = '    if text == "Назад":\n'
        if nav_marker in text:
            text = text.replace(nav_marker, LANGUAGE_CHOICE_BLOCK + nav_marker, 1)
            print("player.py: добавлен выбор языка.")
        else:
            print('WARNING: не нашёл блок if text == "Назад".')
    else:
        print("player.py: выбор языка уже есть, пропускаю.")

    if 'if player_action == "my_status":' not in text:
        first_player_button = '    if text == "Мой статус":\n'
        if first_player_button in text:
            text = text.replace(first_player_button, PLAYER_ACTION_BLOCK + first_player_button, 1)
            print("player.py: добавлен маршрутизатор player_action.")
        else:
            print('WARNING: не нашёл блок if text == "Мой статус".')
    else:
        print("player.py: маршрутизатор player_action уже есть, пропускаю.")

    write_text(PLAYER_PATH, text)


def main():
    print("Применяю безопасное обновление выбора языка...")
    print(f"Проект: {ROOT}")

    patch_keyboards()
    patch_users()
    patch_player()

    print("\nГотово.")
    print("Теперь выполни проверку:")
    print(r".\venv\Scripts\python.exe -m py_compile app\keyboards.py app\handlers\player.py app\repositories\users.py")
    print("\nЕсли ошибок нет, запускай тестового бота:")
    print(r".\venv\Scripts\python.exe bot.py")


if __name__ == "__main__":
    main()
