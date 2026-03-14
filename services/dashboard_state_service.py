from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DashboardSnapshot:
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
    decade_title: str

    def to_payload(self) -> dict:
        return asdict(self)


class DashboardStateService:
    @staticmethod
    def build_snapshot(user_id: int, *, today: date | None = None) -> DashboardSnapshot:
        now = datetime.now()
        d = today or now.date()
        if d.day <= 10:
            start_d = date(d.year, d.month, 1)
            end_d = date(d.year, d.month, 10)
            prev_start = date(d.year - 1, 12, 21) if d.month == 1 else date(d.year, d.month - 1, 21)
            prev_end = date(d.year - 1, 12, 31) if d.month == 1 else date(d.year, d.month - 1, 28)
            title = f"1-я декада • 1–10"
        elif d.day <= 20:
            start_d = date(d.year, d.month, 11)
            end_d = date(d.year, d.month, 20)
            prev_start = date(d.year, d.month, 1)
            prev_end = date(d.year, d.month, 10)
            title = f"2-я декада • 11–20"
        else:
            start_d = date(d.year, d.month, 21)
            end_d = date(d.year, d.month, 28)
            prev_start = date(d.year, d.month, 11)
            prev_end = date(d.year, d.month, 20)
            title = f"3-я декада • 21–конец"

        goal = int(DatabaseManager.get_decade_goal(user_id) or 0)
        earned = int(DatabaseManager.get_user_total_between_dates(user_id, start_d.isoformat(), end_d.isoformat()) or 0)
        cars = int(DatabaseManager.get_cars_count_between_dates(user_id, start_d.isoformat(), end_d.isoformat()) or 0)
        shifts = int(DatabaseManager.get_shifts_count_between_dates(user_id, start_d.isoformat(), end_d.isoformat()) or 0)

        remaining = max(goal - earned, 0)
        shifts_left = max(1, (end_d - d).days + 1)
        needed_per_shift = int((remaining + shifts_left - 1) / shifts_left) if remaining else 0
        avg_check = int(earned / cars) if cars else 0
        progress = (earned / goal * 100.0) if goal > 0 else 0.0

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
            decade_goal=goal,
            current_revenue=earned,
            remaining_to_goal=remaining,
            shifts_left=shifts_left,
            needed_per_shift=needed_per_shift,
            average_check=avg_check,
            cars_count=cars,
            shifts_count=shifts,
            progress_percent=progress,
            trend_vs_previous_decade=trend,
            active_shift_target=active_shift_target,
            active_shift_revenue=active_shift_revenue,
            status=status,
            updated_at=now,
            decade_title=title,
        )
        logger.info(
            "dashboard snapshot user_id=%s goal=%s earned=%s remaining=%s shifts_left=%s needed=%s avg_check=%s trend=%s source=db",
            user_id,
            snapshot.decade_goal,
            snapshot.current_revenue,
            snapshot.remaining_to_goal,
            snapshot.shifts_left,
            snapshot.needed_per_shift,
            snapshot.average_check,
            round(snapshot.trend_vs_previous_decade, 2),
        )
        return snapshot
