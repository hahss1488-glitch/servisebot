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
        shift = PerformanceBlock(
            title="Текущая смена",
            badge="В темпе" if (_pct(payload.get("today_progress")) or 0) >= 0.9 else "Ниже плана",
            revenue=int(payload.get("shift_income") or 0),
            target=int(payload.get("shift_target") or 0),
            remaining=max(0, int(payload.get("shift_target") or 0) - int(payload.get("shift_income") or 0)),
            run_rate=_pct(payload.get("today_progress")),
            metrics=[
                MetricItem("Машин", str(int(payload.get("shift_cars") or 0))),
                MetricItem("Средний чек", payload.get("mini", ["", "", "—"])[2].split(":", 1)[-1].strip() if payload.get("mini") else "—"),
                MetricItem("Доход в час", payload.get("mini", ["", "", "—"])[1].split(":", 1)[-1].strip() if payload.get("mini") else "—"),
                MetricItem("Время смены", payload.get("shift_start_label", "—")),
            ],
        )
        decade = PerformanceBlock(
            title="Текущая декада",
            badge="Идешь по плану",
            revenue=int(payload.get("decade_earned") or 0),
            target=int(payload.get("decade_goal") or 0),
            remaining=int(payload.get("remaining_text", "0").replace("₽", "").replace(" ", "") or 0) if isinstance(payload.get("remaining_text"), str) else int(payload.get("remaining") or 0),
            run_rate=_pct(payload.get("completion_percent")),
            metrics=[MetricItem(k, v) for k, v, *_ in (payload.get("decade_metrics") or [])],
        )
        data = MainDashboardData("Дашборд", "Смена открыта", payload.get("updated_at") or datetime.now(), shift, decade)
        return to_png_bytes(_renderer.render_main_dashboard(data), "dashboard.png")

    metrics = [MetricItem(k, v) for k, v, *_ in (payload.get("metrics") or [])]
    data = ShiftSummaryData(
        title="Смена закрыта",
        date_label=datetime.now().strftime("%d.%m.%Y"),
        duration_label="Итог",
        total=int(payload.get("earned") or 0),
        status_message=payload.get("pace_delta_text") or payload.get("plan_deviation_label") or "Итоги смены",
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
        )
        for i, row in enumerate(decade_leaders, start=1)
    ]
    data = LeaderboardData("Лидерборд", decade_title, updated_at or datetime.now(), leaders, highlight_name)
    return to_png_bytes(_renderer.render_leaderboard(data), "leaderboard.png")
