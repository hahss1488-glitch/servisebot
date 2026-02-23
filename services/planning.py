from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import ceil


@dataclass
class PlanMetrics:
    days_total: int
    days_elapsed: int
    days_left_including_today: int
    remaining: int
    avg_per_day: int
    need_today: int
    pct_today: float
    planned_by_today: int
    delta: int
    runrate_to_need_today: float


def compute_plan_metrics(
    today_date: date,
    period_start: date,
    period_end: date,
    period_plan_total: int,
    period_earned_total: int,
    today_earned: int,
) -> dict:
    days_total = max((period_end - period_start).days + 1, 1)
    raw_elapsed = (today_date - period_start).days + 1
    days_elapsed = max(1, min(raw_elapsed, days_total))
    days_left_including_today = max(1, days_total - (days_elapsed - 1))

    remaining = max(0, int(period_plan_total) - int(period_earned_total))
    avg_per_day = ceil(int(period_plan_total) / days_total) if period_plan_total > 0 else 0

    if remaining == 0:
        need_today = 0
        pct_today = 1.0
        runrate_to_need_today = 0.0
    else:
        need_today = ceil(remaining / days_left_including_today)
        pct_today = (today_earned / need_today) if need_today > 0 else 1.0
        runrate_to_need_today = (today_earned / need_today - 1) if need_today > 0 else 0.0

    planned_by_today = avg_per_day * days_elapsed
    delta = int(period_earned_total) - planned_by_today

    metrics = PlanMetrics(
        days_total=days_total,
        days_elapsed=days_elapsed,
        days_left_including_today=days_left_including_today,
        remaining=remaining,
        avg_per_day=avg_per_day,
        need_today=need_today,
        pct_today=pct_today,
        planned_by_today=planned_by_today,
        delta=delta,
        runrate_to_need_today=runrate_to_need_today,
    )
    return metrics.__dict__.copy()


def _test_compute_plan_metrics() -> None:
    # A) Рабочих дней может быть 3, но расчёт идёт по календарным 6 (переменная не используется)
    working_days_left = 3
    m = compute_plan_metrics(
        today_date=date(2026, 2, 15),
        period_start=date(2026, 2, 11),
        period_end=date(2026, 2, 20),  # 10 дней, прошло 5, осталось включая сегодня 6
        period_plan_total=35000,
        period_earned_total=15140,
        today_earned=2000,
    )
    assert working_days_left == 3  # just to show external variable exists
    assert m["days_left_including_today"] == 6
    assert m["remaining"] == 19860
    assert m["need_today"] == 3310  # ceil(19860/6)

    # B) Последний день периода
    m = compute_plan_metrics(
        today_date=date(2026, 2, 20),
        period_start=date(2026, 2, 11),
        period_end=date(2026, 2, 20),
        period_plan_total=35000,
        period_earned_total=22717,
        today_earned=1000,
    )
    assert m["days_left_including_today"] == 1
    assert m["need_today"] == 12283

    # C) План закрыт
    m = compute_plan_metrics(
        today_date=date(2026, 2, 18),
        period_start=date(2026, 2, 11),
        period_end=date(2026, 2, 20),
        period_plan_total=35000,
        period_earned_total=36000,
        today_earned=500,
    )
    assert m["remaining"] == 0
    assert m["need_today"] == 0
    assert m["pct_today"] == 1.0
    assert m["runrate_to_need_today"] == 0.0
