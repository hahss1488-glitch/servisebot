from datetime import date, datetime

import bot


def test_decade_shift_plan_uses_remaining_work_shifts(monkeypatch):
    db_user = {"id": 1}

    monkeypatch.setattr(bot, "now_local", lambda: datetime(2026, 3, 15, 12, 0))
    monkeypatch.setattr(bot.DatabaseManager, "get_calendar_overrides", lambda user_id: {})
    monkeypatch.setattr(bot.DatabaseManager, "get_days_for_month", lambda user_id, month: [])
    monkeypatch.setattr(bot.DatabaseManager, "get_shifts_count_between_dates", lambda user_id, start, end: 1 if start == end == "2026-03-15" else 0)
    monkeypatch.setattr(bot.DatabaseManager, "get_decade_goal", lambda user_id: 35000)
    monkeypatch.setattr(bot.DatabaseManager, "get_user_total_between_dates", lambda user_id, start, end: 15140)

    planned_days = {date(2026, 3, 11), date(2026, 3, 12), date(2026, 3, 15), date(2026, 3, 16), date(2026, 3, 19), date(2026, 3, 20)}
    monkeypatch.setattr(bot, "get_work_day_type", lambda db_user, target_day, overrides=None: "planned" if target_day in planned_days else "off")

    plan = bot.calculate_current_decade_shift_plan(db_user)

    assert plan["work_units_total"] == 6
    assert plan["work_units_left"] == 4
    assert plan["remaining"] == 19860
    assert plan["shift_target_now"] == 4965


def test_decade_shift_plan_handles_missing_calendar_without_division_by_zero(monkeypatch):
    db_user = {"id": 1}

    monkeypatch.setattr(bot, "now_local", lambda: datetime(2026, 3, 15, 12, 0))
    monkeypatch.setattr(bot.DatabaseManager, "get_calendar_overrides", lambda user_id: {})
    monkeypatch.setattr(bot.DatabaseManager, "get_days_for_month", lambda user_id, month: [])
    monkeypatch.setattr(bot.DatabaseManager, "get_shifts_count_between_dates", lambda user_id, start, end: 0)
    monkeypatch.setattr(bot.DatabaseManager, "get_decade_goal", lambda user_id: 35000)
    monkeypatch.setattr(bot.DatabaseManager, "get_user_total_between_dates", lambda user_id, start, end: 10000)
    monkeypatch.setattr(bot, "get_work_day_type", lambda db_user, target_day, overrides=None: "off")

    plan = bot.calculate_current_decade_shift_plan(db_user)

    assert plan["work_units_total"] == 0
    assert plan["work_units_left"] == 0
    assert plan["shift_target_now"] == 25000
