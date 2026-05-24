from app.db import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.game_schedule');")
        result = cur.fetchone()[0]
        print("game_schedule =", result)

        if result is None:
            print("Таблицы нет. Создаю...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_schedule (
                    id SERIAL PRIMARY KEY,
                    game_date DATE NOT NULL,
                    game_time TIME NOT NULL,
                    opponent_name TEXT NOT NULL,
                    comment TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            conn.commit()
            print("Таблица game_schedule создана.")
        else:
            print("Таблица уже существует.")