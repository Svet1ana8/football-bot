import argparse
import asyncio
import os
import sys

import psycopg
from dotenv import load_dotenv
from telegram import Bot


MESSAGE_TEXT = (
    "🎥 В боте добавлены обучающие материалы по американскому футболу!\n\n"
    "Теперь в главном меню доступен раздел:\n"
    "«Обучающее видео»\n\n"
    "Там собраны лекции и плейлист с YouTube-канала.\n"
    "Открой главное меню и нажми «Обучающее видео»."
)


def parse_coach_ids(value: str | None) -> set[int]:
    if not value:
        return set()

    result = set()

    for item in value.split(","):
        item = item.strip()
        if not item:
            continue

        try:
            result.add(int(item))
        except ValueError:
            pass

    return result


def get_approved_players(database_url: str, coach_ids: set[int]):
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            db_name, db_user = cur.fetchone()

            print(f"База данных: {db_name}")
            print(f"Пользователь БД: {db_user}")

            cur.execute(
                """
                SELECT user_id, username, first_name
                FROM public.users
                WHERE status = 'approved'
                ORDER BY first_name NULLS LAST, username NULLS LAST, user_id
                """
            )

            rows = cur.fetchall()

    players = []

    for user_id, username, first_name in rows:
        if int(user_id) in coach_ids:
            continue

        players.append(
            {
                "user_id": int(user_id),
                "username": username,
                "first_name": first_name,
            }
        )

    return players


async def send_messages(bot_token: str, players: list[dict], dry_run: bool):
    if dry_run:
        print("\nDRY-RUN: сообщения НЕ отправлены.")
        print("Чтобы реально отправить, запусти с флагом --send.")
        return

    bot = Bot(token=bot_token)

    success_count = 0
    fail_count = 0

    for player in players:
        user_id = player["user_id"]
        name = player["first_name"] or player["username"] or str(user_id)

        try:
            await bot.send_message(
                chat_id=user_id,
                text=MESSAGE_TEXT,
            )
            success_count += 1
            print(f"OK: отправлено игроку {name} ({user_id})")

            await asyncio.sleep(0.1)

        except Exception as exc:
            fail_count += 1
            print(f"ERROR: не удалось отправить игроку {name} ({user_id}): {exc}")

    print("\nГотово.")
    print(f"Успешно отправлено: {success_count}")
    print(f"Ошибок: {fail_count}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--send",
        action="store_true",
        help="Реально отправить уведомление игрокам",
    )

    args = parser.parse_args()

    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN")
    database_url = os.getenv("DATABASE_URL")
    coach_ids = parse_coach_ids(os.getenv("COACH_IDS"))

    if not bot_token:
        print("Ошибка: не найден BOT_TOKEN")
        sys.exit(1)

    if not database_url:
        print("Ошибка: не найден DATABASE_URL")
        sys.exit(1)

    print("Уведомление будет таким:")
    print("-" * 40)
    print(MESSAGE_TEXT)
    print("-" * 40)

    players = get_approved_players(database_url, coach_ids)

    print(f"\nНайдено approved-игроков для рассылки: {len(players)}")

    for player in players:
        print(
            f"- {player['first_name']} "
            f"@{player['username']} "
            f"({player['user_id']})"
        )

    await send_messages(
        bot_token=bot_token,
        players=players,
        dry_run=not args.send,
    )


if __name__ == "__main__":
    asyncio.run(main())