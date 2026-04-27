from app.config import COACH_IDS


def is_coach(user_id: int) -> bool:
    return str(user_id) in COACH_IDS


def is_broadcast_recipient(user_id: int) -> bool:
    return str(user_id) not in COACH_IDS
