from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from ui.dashboard_renderer import (
    DashboardRenderer,
    LeaderRow,
    LeaderboardData,
    MainDashboardData,
    MetricItem,
    PerformanceBlock,
    ShiftSummaryData,
    to_png_bytes,
)

TOKENS = {
    "TEXT_PRIMARY": (243, 247, 255, 255),
    "TEXT_SECONDARY": (156, 172, 191, 255),
    "POSITIVE": (58, 208, 122, 255),
    "NEGATIVE": (233, 99, 99, 255),
}

_renderer = DashboardRenderer()


def format_money(v: Any) -> str:
    try:
        return f"{int(round(float(v))):,}".replace(",", " ") + " ₽"
    except Exception:
        return "—"


def _pct(value: Any) -> float | None:
    try:
        v = float(value)
    except Exception:
        return None
    return v if v <= 3 else v / 100.0


def render_dashboard_image_bytes(mode: str, payload: dict) -> BytesIO:
    if mode == "open":
        mini = payload.get("mini") or []
        mini_income_per_hour = mini[1] if len(mini) > 1 else "Машин: —"
        mini_avg_check = mini[2] if len(mini) > 2 else "Средний чек: —"
        shift_income = int(payload.get("shift_income") or 0)
        shift_target = int(payload.get("shift_target") or 0)
        shift_progress = _pct(payload.get("today_progress"))
        if shift_income <= 0:
            shift_badge = "Смена только началась"
        elif (shift_progress or 0.0) >= 1.0:
            shift_badge = "В темпе"
        elif (shift_progress or 0.0) >= 0.9:
            shift_badge = "Почти по плану"
        else:
            shift_badge = "Ниже плана"

        decade_progress = _pct(payload.get("completion_percent"))
        if (decade_progress or 0.0) >= 1.0:
            decade_badge = "В темпе"
        elif (decade_progress or 0.0) >= 0.9:
            decade_badge = "Почти по плану"
        else:
            decade_badge = "Ниже плана"

        shift = PerformanceBlock(
            title="Текущая смена",
            badge=shift_badge,
            revenue=shift_income,
            target=shift_target,
            remaining=max(0, shift_target - shift_income),
            run_rate=shift_progress,
            metrics=[
                MetricItem("Машин", str(int(payload.get("shift_cars") or 0))),
                MetricItem("Средний чек", str(mini_avg_check).split(":", 1)[-1].strip() or "—"),
                MetricItem("Доход в час", str(mini_income_per_hour).split(":", 1)[-1].strip() or "—"),
                MetricItem("Время смены", payload.get("shift_start_label", "—")),
            ],
        )
        decade = PerformanceBlock(
            title="Текущая декада",
            badge=decade_badge,
            revenue=int(payload.get("decade_earned") or 0),
            target=int(payload.get("decade_goal") or 0),
            remaining=int(payload.get("remaining_text", "0").replace("₽", "").replace(" ", "") or 0) if isinstance(payload.get("remaining_text"), str) else int(payload.get("remaining") or 0),
            run_rate=decade_progress,
            metrics=[MetricItem(k, v) for k, v, *_ in (payload.get("decade_metrics") or [])],
        )
        data = MainDashboardData("Дашборд", "Смена открыта", payload.get("updated_at") or datetime.now(), shift, decade)
        return to_png_bytes(_renderer.render_main_dashboard(data), "dashboard.png")

    metrics = [MetricItem(k, v) for k, v, *_ in (payload.get("metrics") or [])]
    status = str(payload.get("plan_deviation_label") or "").strip()
    delta_text = str(payload.get("pace_delta_text") or "").strip()
    if not status and delta_text and delta_text != "—":
        status = delta_text
    if not status:
        status = "Итог смены"
    data = ShiftSummaryData(
        title="Смена закрыта",
        date_label=datetime.now().strftime("%d.%m.%Y"),
        duration_label="Итог",
        total=int(payload.get("earned") or 0),
        status_message=status,
        metrics=metrics,
        decade_total=int(payload.get("earned") or 0),
        decade_remaining=max(0, int(payload.get("goal") or 0) - int(payload.get("earned") or 0)),
    )
    return to_png_bytes(_renderer.render_shift_summary(data), "dashboard.png")


def render_leaderboard_image_bytes(decade_title: str, decade_leaders: list[dict], highlight_name: str | None = None, top3_avatars: dict[int, object] | None = None, updated_at: datetime | None = None) -> BytesIO:
    leaders = [
        LeaderRow(
            rank=i,
            name=str(row.get("name", "—")),
            earnings=int(row.get("total_amount") or 0),
            cars=int(row.get("cars_count") or 0) if row.get("cars_count") is not None else None,
            income_per_hour=int(row.get("avg_per_hour") or 0) if row.get("avg_per_hour") is not None else None,
            avatar_path=str(row.get("avatar_path") or "") or None,
        )
        for i, row in enumerate(decade_leaders, start=1)
    ]
    data = LeaderboardData("Лидерборд", decade_title, updated_at or datetime.now(), leaders, highlight_name)
    return to_png_bytes(_renderer.render_leaderboard(data), "leaderboard.png")
