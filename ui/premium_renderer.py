from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
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
from ui.renderers.dashboard_renderer import render_dashboard

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
    render_payload = {
        "title": payload.get("title") or ("Дашборд" if mode == "open" else "Итоги смены"),
        "period": payload.get("decade_title") or payload.get("subtitle") or "",
        "status": payload.get("status") or ("Смена активна" if mode == "open" else "Смена закрыта"),
        "revenue_text": format_money(payload.get("decade_earned") if mode == "open" else payload.get("earned")),
        "target_text": f"из {format_money(payload.get('decade_goal') if mode == 'open' else payload.get('goal'))}",
        "updated_at": (payload.get("updated_at") or datetime.now()).strftime("Обновлено: %d.%m.%Y %H:%M") if hasattr(payload.get("updated_at") or datetime.now(), "strftime") else str(payload.get("updated_at")),
    }
    path = render_dashboard(render_payload)
    stream = BytesIO(Path(path).read_bytes())
    stream.name = "dashboard.png"
    stream.seek(0)
    return stream


def render_leaderboard_image_bytes(decade_title: str, decade_leaders: list[dict], highlight_name: str | None = None, top3_avatars: dict[int, object] | None = None, updated_at: datetime | None = None) -> BytesIO:
    leaders = [
        LeaderRow(
            rank=i,
            name=str(row.get("name", "—")),
            earnings=int(row.get("total_amount") or 0),
            shifts=int(row.get("shifts_count") or row.get("shift_count") or 0),
            cars=int(row.get("cars_count") or 0),
            avatar_path=str(row.get("avatar_path") or "") or None,
        )
        for i, row in enumerate(decade_leaders, start=1)
    ]
    data = LeaderboardData("Лидерборд", decade_title, updated_at or datetime.now(), leaders, highlight_name)
    return to_png_bytes(_renderer.render_leaderboard(data), "leaderboard.png")
