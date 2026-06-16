BEGIN;

CREATE TABLE IF NOT EXISTS public.team_breaks (
    id SERIAL PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    notify_at TIMESTAMPTZ NOT NULL,
    message_text TEXT NOT NULL,
    notified_at TIMESTAMPTZ,
    notification_success_count INTEGER NOT NULL DEFAULT 0,
    notification_fail_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_team_breaks_dates
ON public.team_breaks(start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_team_breaks_notify_pending
ON public.team_breaks(notified_at, notify_at);

INSERT INTO public.team_breaks (
    start_date,
    end_date,
    notify_at,
    message_text,
    notified_at,
    notification_success_count,
    notification_fail_count
)
VALUES (
    DATE '2026-07-01',
    DATE '2026-07-19',
    TIMESTAMP '2026-06-30 10:00:00' AT TIME ZONE 'Asia/Almaty',
    '📢 Уведомление от тренера

С завтрашнего дня команда уходит на отдых.

Период отдыха: с 1 по 19 июля включительно.

В этот период тренировок не будет. После отдыха тренировки продолжатся по расписанию.',
    NULL,
    0,
    0
)
ON CONFLICT (start_date, end_date)
DO UPDATE SET
    notify_at = EXCLUDED.notify_at,
    message_text = EXCLUDED.message_text,
    notified_at = public.team_breaks.notified_at;

COMMIT;