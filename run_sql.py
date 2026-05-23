import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise ValueError("DATABASE_URL не найден в .env")

sql = """
INSERT INTO training_schedule (training_date, training_time, comment, is_active)
VALUES
    ('2026-05-25', '21:00:00', NULL, TRUE),
    ('2026-05-27', '21:00:00', NULL, TRUE),
    ('2026-05-29', '21:00:00', NULL, TRUE),
    ('2026-06-01', '21:00:00', NULL, TRUE),
    ('2026-06-03', '21:00:00', NULL, TRUE),
    ('2026-06-05', '21:00:00', NULL, TRUE),
    ('2026-06-08', '21:00:00', NULL, TRUE),
    ('2026-06-10', '21:00:00', NULL, TRUE),
    ('2026-06-12', '21:00:00', NULL, TRUE),
    ('2026-06-15', '21:00:00', NULL, TRUE),
    ('2026-06-17', '21:00:00', NULL, TRUE),
    ('2026-06-19', '21:00:00', NULL, TRUE),
    ('2026-06-22', '21:00:00', NULL, TRUE),
    ('2026-06-24', '21:00:00', NULL, TRUE),
    ('2026-06-26', '21:00:00', NULL, TRUE),
    ('2026-06-29', '21:00:00', NULL, TRUE);
"""

with psycopg.connect(database_url) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()

print("Тренировки успешно добавлены в training_schedule")