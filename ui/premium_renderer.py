from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from ui.renderers.dashboard_renderer import render_dashboard
from ui.renderers.leaderboard_renderer import render_leaderboard

TOKENS = {
    "TEXT_PRIMARY": (243, 247, 255, 255),
    "TEXT_SECONDARY": (156, 172, 191, 255),
    "POSITIVE": (58, 208, 122, 255),
    "NEGATIVE": (233, 99, 99, 255),
}



RANK_PREFIX_DEFAULTS = {
    1: "ЛЕГЕНДА",
    2: "PRO",
    3: "ELITE",
}
RANK_PREFIX_FALLBACK = "НОВИЧОК"
RANK_PREFIX_MAX_LENGTH = 20


def sanitize_rank_prefix(raw: Any, place: int) -> str:
    value = " ".join(str(raw or "").strip().split())
    if value.startswith("👤") or value.lower() == "профиль":
        value = ""
    if len(value) > RANK_PREFIX_MAX_LENGTH:
        value = value[:RANK_PREFIX_MAX_LENGTH].rstrip()
    return value or RANK_PREFIX_DEFAULTS.get(place, RANK_PREFIX_FALLBACK)


def format_money(v: Any) -> str:
    try:
        return f"{int(round(float(v))):,}".replace(",", " ") + " ₽"
    except Exception:
        return "—"


def _as_percent(progress_value: Any) -> float:
    try:
        value = float(progress_value)
    except (TypeError, ValueError):
        return 0.0
    if value > 1:
        value = value / 100.0
    return max(0.0, min(1.0, value))


def _trend_payload(payload: dict[str, Any]) -> tuple[str, tuple[int, int, int, int]]:
    pace = str(payload.get("pace_delta_text") or payload.get("trend_text") or "").strip()
    if not pace or pace == "—":
        return "0% к прошлой декаде", (221, 227, 238, 255)
    if pace.startswith("+"):
        return f"{pace} к прошлой декаде" if "%" in pace else pace, (122, 255, 159, 255)
    if pace.startswith("-"):
        return f"{pace} к прошлой декаде" if "%" in pace else pace, (255, 172, 96, 255)
    return pace, (221, 227, 238, 255)


def _leaderboard_payload(decade_title: str, decade_leaders: list[dict], updated_at: datetime | None) -> dict[str, Any]:
    leaders = []
    for i in range(1, 6):
        src = decade_leaders[i - 1] if i - 1 < len(decade_leaders) else {}
        amount = format_money(src.get("total_amount") or 0)
        row = {
            "place": i,
            "name": str(src.get("name") or "—"),
            "amount": amount,
        }
        if i <= 3:
            row.update(
                {
                    "rank_prefix": sanitize_rank_prefix(src.get("rank_prefix") or src.get("rank_text"), i),
                    "avatar_path": str(src.get("avatar_path") or ""),
                }
            )
        leaders.append(row)
    return {
        "period_text": decade_title,
        "updated_text": updated_at or datetime.now(),
        "leaders": leaders,
    }


def render_dashboard_image_bytes(mode: str, payload: dict) -> BytesIO:
    progress = _as_percent(payload.get("completion_percent") or payload.get("decade_progress") or payload.get("progress"))
    trend_text, trend_color = _trend_payload(payload)

    render_payload = {
        "title": payload.get("title") or ("Дашборд" if mode == "open" else "Итоги смены"),
        "period": payload.get("decade_title") or payload.get("subtitle") or "",
        "status": payload.get("status") or ("Смена активна" if mode == "open" else "Смена закрыта"),
        "revenue_text": format_money(payload.get("decade_earned") if mode == "open" else payload.get("earned")),
        "target_text": f"из {format_money(payload.get('decade_goal') if mode == 'open' else payload.get('goal'))}",
        "progress": progress,
        "progress_text": f"{int(progress * 100)}%",
        "progress_subtitle": "до цели",
        "remaining_text": f"Осталось {payload.get('remaining_text') or format_money(max(0, int((payload.get('decade_goal') or payload.get('goal') or 0) - (payload.get('decade_earned') or payload.get('earned') or 0))))}",
        "cards": [
            {"title": "Смен", "value": str(payload.get("decade_shifts") or "0")},
            {"title": "Машин", "value": str(payload.get("decade_cars") or "0")},
            {"title": "Нужно в смену", "value": str(payload.get("needed_per_shift_text") or payload.get("remaining_shift_text") or "—")},
        ],
        "bottom_metrics": [
            {"label": "Ср. чек", "value": str((payload.get("mini") or ["", "", "Средний чек: —"])[2]).split(":", 1)[-1].strip()},
            {"label": "Смен осталось", "value": str(payload.get("work_units_left") or "—")},
            {"label": "Цель", "value": format_money(payload.get("decade_goal") if mode == "open" else payload.get("goal"))},
        ],
        "trend_text": trend_text,
        "trend_color": trend_color,
        "updated_at": payload.get("updated_at") or datetime.now(),
    }

    path = render_dashboard(render_payload)
    stream = BytesIO(Path(path).read_bytes())
    stream.name = "dashboard.png"
    stream.seek(0)
    return stream


def render_leaderboard_image_bytes(
    decade_title: str,
    decade_leaders: list[dict],
    highlight_name: str | None = None,
    top3_avatars: dict[int, object] | None = None,
    updated_at: datetime | None = None,
) -> BytesIO:
    payload = _leaderboard_payload(decade_title, decade_leaders, updated_at)
    path = render_leaderboard(payload)
    stream = BytesIO(Path(path).read_bytes())
    stream.name = "leaderboard.png"
    stream.seek(0)
    return stream
