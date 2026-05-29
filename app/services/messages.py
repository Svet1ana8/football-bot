from telegram.ext import ContextTypes


TELEGRAM_MESSAGE_LIMIT = 4000


def split_long_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """
    Делит длинный текст на части, чтобы Telegram не падал с ошибкой:
    BadRequest: Message is too long
    """
    if len(text) <= limit:
        return [text]

    parts = []
    current_part = ""

    for line in text.splitlines(keepends=True):
        if len(current_part) + len(line) > limit:
            if current_part:
                parts.append(current_part)
                current_part = ""

            while len(line) > limit:
                parts.append(line[:limit])
                line = line[limit:]

        current_part += line

    if current_part:
        parts.append(current_part)

    return parts


async def send_long_message_by_update(update, text: str, **kwargs):
    """
    Отправляет длинный текст через update.message.reply_text частями.
    """
    for part in split_long_message(text):
        await update.message.reply_text(part, **kwargs)


async def send_long_message_by_bot(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    **kwargs,
):
    """
    Отправляет длинный текст через context.bot.send_message частями.
    """
    for part in split_long_message(text):
        await context.bot.send_message(
            chat_id=chat_id,
            text=part,
            **kwargs,
        )