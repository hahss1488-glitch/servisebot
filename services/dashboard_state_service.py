from __future__ import annotations

import calendar
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime

from database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DashboardSnapshot:
    period_start: date
    period_end: date
    period_label: str
    decade_goal: int
    current_revenue: int
    remaining_to_goal: int
    shifts_left: int
    needed_per_shift: int
    average_check: int
    cars_count: int
    shifts_count: int
    progress_percent: float
    trend_vs_previous_decade: float
    active_shift_target: int
    active_shift_revenue: int
    status: str
    updated_at: datetime

    def to_payload(self) -> dict:
        return asdict(self)


class DashboardStateService:
    @staticmethod
    def _decade_range(day: date) -> tuple[date, date, str]:
        if day.day <= 10:
            start_d = date(day.year, day.month, 1)
            end_d = date(day.year, day.month, 10)
            label = f"1-я декада • 1–10 {calendar.month_name[day.month]}"
            return start_d, end_d, label
        if day.day <= 20:
            start_d = date(day.year, day.month, 11)
            end_d = date(day.year, day.month, 20)
            label = f"2-я декада • 11–20 {calendar.month_name[day.month]}"
            return start_d, end_d, label
        last_day = calendar.monthrange(day.year, day.month)[1]
        start_d = date(day.year, day.month, 21)
        end_d = date(day.year, day.month, last_day)
        label = f"3-я декада • 21–{last_day} {calendar.month_name[day.month]}"
        return start_d, end_d, label

    @staticmethod
    def _previous_decade(day: date) -> tuple[date, date]:
        if day.day <= 10:
            prev_month = day.month - 1 or 12
            prev_year = day.year - 1 if day.month == 1 else day.year
            prev_last = calendar.monthrange(prev_year, prev_month)[1]
            return date(prev_year, prev_month, 21), date(prev_year, prev_month, prev_last)
        if day.day <= 20:
            return date(day.year, day.month, 1), date(day.year, day.month, 10)
        return date(day.year, day.month, 11), date(day.year, day.month, 20)

    @staticmethod
    def build_snapshot(user_id: int, *, today: date | None = None) -> DashboardSnapshot:
        now = datetime.now()
        current_day = today or now.date()
        period_start, period_end, period_label = DashboardStateService._decade_range(current_day)
        prev_start, prev_end = DashboardStateService._previous_decade(current_day)

        decade_goal = int(DatabaseManager.get_decade_goal(user_id) or 0)
        earned = int(DatabaseManager.get_user_total_between_dates(user_id, period_start.isoformat(), period_end.isoformat()) or 0)
        cars_count = int(DatabaseManager.get_cars_count_between_dates(user_id, period_start.isoformat(), period_end.isoformat()) or 0)
        shifts_count = int(DatabaseManager.get_shifts_count_between_dates(user_id, period_start.isoformat(), period_end.isoformat()) or 0)

        remaining = max(0, decade_goal - earned)
        days_left = max(1, (period_end - current_day).days + 1)
        shifts_left = max(1, days_left)
        needed_per_shift = (remaining + shifts_left - 1) // shifts_left if remaining else 0
        average_check = int(earned / cars_count) if cars_count else 0
        progress_percent = (earned / decade_goal * 100.0) if decade_goal > 0 else 0.0

        prev_earned = int(DatabaseManager.get_user_total_between_dates(user_id, prev_start.isoformat(), prev_end.isoformat()) or 0)
        if prev_earned <= 0:
            trend = 0.0
        else:
            trend = ((earned - prev_earned) / prev_earned) * 100.0

        active_shift = DatabaseManager.get_active_shift(user_id)
        active_shift_target = int(active_shift.get("shift_target") or 0) if active_shift else 0
        active_shift_revenue = int(DatabaseManager.get_shift_total(active_shift["id"]) or 0) if active_shift else 0
        status = "Смена активна" if active_shift else "Смена закрыта"

        snapshot = DashboardSnapshot(
            period_start=period_start,
            period_end=period_end,
            period_label=period_label,
            decade_goal=decade_goal,
            current_revenue=earned,
            remaining_to_goal=remaining,
            shifts_left=shifts_left,
            needed_per_shift=needed_per_shift,
            average_check=average_check,
            cars_count=cars_count,
            shifts_count=shifts_count,
            progress_percent=progress_percent,
            trend_vs_previous_decade=trend,
            active_shift_target=active_shift_target,
            active_shift_revenue=active_shift_revenue,
            status=status,
            updated_at=now,
        )
        logger.info(
            "dashboard snapshot user_id=%s period=%s..%s goal=%s earned=%s remaining=%s shifts_left=%s needed_per_shift=%s cars=%s shifts=%s progress=%.2f trend=%.2f status=%s",
            user_id,
            period_start,
            period_end,
            snapshot.decade_goal,
            snapshot.current_revenue,
            snapshot.remaining_to_goal,
            snapshot.shifts_left,
            snapshot.needed_per_shift,
            snapshot.cars_count,
            snapshot.shifts_count,
            snapshot.progress_percent,
            snapshot.trend_vs_previous_decade,
            snapshot.status,
        )
        return snapshot
