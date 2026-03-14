from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from config import BASE_DIR, DASHBOARD_TEMPLATE_PATH
from ui.renderers.font_manager import get_font

logger = logging.getLogger(__name__)

CACHE_DIR = BASE_DIR / "cache" / "dashboard"


@dataclass(frozen=True, slots=True)
class DashboardLayout:
    width: int = 1536
    height: int = 1024
    title_xy: tuple[int, int] = (96, 78)
    period_xy: tuple[int, int] = (98, 139)
    status_xy: tuple[int, int] = (1080, 80)

    revenue_label_center: tuple[int, int] = (702, 202)
    revenue_value_center: tuple[int, int] = (707, 238)
    revenue_target_center: tuple[int, int] = (707, 335)
    revenue_safe_width: int = 520

    circle_center: tuple[int, int] = (1215, 277)
    circle_outer_diameter: int = 250
    circle_thickness: int = 20
    circle_percent_center: tuple[int, int] = (1215, 253)
    circle_label_center: tuple[int, int] = (1215, 317)

    progress_fill_xy: tuple[int, int] = (184, 397)
    progress_fill_size: tuple[int, int] = (1200, 23)

    remaining_xy: tuple[int, int] = (1106, 434)

    card1_title_xy: tuple[int, int] = (145, 571)
    card1_value_xy: tuple[int, int] = (145, 619)
    card2_title_xy: tuple[int, int] = (637, 571)
    card2_value_xy: tuple[int, int] = (637, 618)
    card3_title_xy: tuple[int, int] = (1082, 571)
    card3_value_xy: tuple[int, int] = (1082, 618)

    m1_label_xy: tuple[int, int] = (198, 792)
    m1_value_xy: tuple[int, int] = (300, 792)
    m2_label_xy: tuple[int, int] = (484, 792)
    m2_value_xy: tuple[int, int] = (617, 792)
    m3_label_xy: tuple[int, int] = (794, 792)
    m3_value_xy: tuple[int, int] = (980, 792)

    trend_center: tuple[int, int] = (1260, 800)
    updated_center: tuple[int, int] = (780, 878)


LAYOUT = DashboardLayout()


def serialize_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(serialize_payload(payload).encode("utf-8")).hexdigest()


def load_template() -> Image.Image:
    logger.info("dashboard render start template=%s", DASHBOARD_TEMPLATE_PATH)
    if DASHBOARD_TEMPLATE_PATH.exists() and DASHBOARD_TEMPLATE_PATH.is_file():
        try:
            template = Image.open(DASHBOARD_TEMPLATE_PATH).convert("RGBA")
            if template.size != (LAYOUT.width, LAYOUT.height):
                logger.warning("template resized from=%s to=%s", template.size, (LAYOUT.width, LAYOUT.height))
                template = template.resize((LAYOUT.width, LAYOUT.height), Image.Resampling.LANCZOS)
            return template
        except OSError:
            logger.exception("failed to open dashboard template path=%s", DASHBOARD_TEMPLATE_PATH)

    logger.error("dashboard template missing or invalid path=%s", DASHBOARD_TEMPLATE_PATH)
    return Image.new("RGBA", (LAYOUT.width, LAYOUT.height), (15, 22, 35, 255))


def _text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    size: int,
    weight: str,
    fill: tuple[int, int, int, int],
    anchor: str | None = None,
) -> None:
    font = get_font(size, weight)
    draw.text((xy[0] + 1, xy[1] + 2), text, font=font, fill=(0, 0, 0, 85), anchor=anchor)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def _fit_font(draw: ImageDraw.ImageDraw, text: str, base: int, min_size: int, safe_width: int, weight: str) -> Any:
    current = base
    while current >= min_size:
        font = get_font(current, weight)
        width = draw.textbbox((0, 0), text, font=font)[2]
        if width <= safe_width:
            return font
        current -= 2
    return get_font(min_size, weight)


def _lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int, int]:
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
        255,
    )


def _gradient_color(stops: list[tuple[int, int, int]], t: float) -> tuple[int, int, int, int]:
    if t <= 0:
        return (*stops[0], 255)
    if t >= 1:
        return (*stops[-1], 255)
    segment = 1 / (len(stops) - 1)
    idx = min(int(t / segment), len(stops) - 2)
    local_t = (t - segment * idx) / segment
    return _lerp_color(stops[idx], stops[idx + 1], local_t)


def draw_gradient_progress_bar(canvas: Image.Image, progress: float) -> None:
    x, y = LAYOUT.progress_fill_xy
    max_w, height = LAYOUT.progress_fill_size
    p = max(0.0, min(1.0, progress))
    width = int(max_w * p)
    if width <= 0:
        return

    grad = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)
    stops = [(42, 239, 255), (46, 223, 255), (51, 212, 255), (59, 186, 255)]
    for xx in range(width):
        color = _gradient_color(stops, xx / max(1, width - 1))
        grad_draw.line((xx, 0, xx, height), fill=color)

    # мягкий верхний блик
    highlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(highlight)
    h_draw.rounded_rectangle((0, 0, width, max(2, height // 3)), radius=11, fill=(255, 255, 255, 28))
    grad.alpha_composite(highlight)

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=11, fill=255)
    canvas.paste(grad, (x, y), mask)


def draw_gradient_progress_arc(canvas: Image.Image, progress: float) -> None:
    cx, cy = LAYOUT.circle_center
    diameter = LAYOUT.circle_outer_diameter
    thickness = LAYOUT.circle_thickness
    radius = diameter / 2
    bbox = (cx - radius, cy - radius, cx + radius, cy + radius)

    p = max(0.0, min(1.0, progress))
    if p <= 0:
        return

    total_deg = 360 * p
    segments = max(18, int(total_deg / 2.0))
    stops = [(44, 164, 255), (66, 244, 255), (29, 255, 154)]
    draw = ImageDraw.Draw(canvas)

    for i in range(segments):
        t0 = i / segments
        t1 = (i + 1) / segments
        start = -90 + total_deg * t0
        end = -90 + total_deg * t1
        color = _gradient_color(stops, t1)
        draw.arc(bbox, start=start, end=end, fill=color, width=thickness)


def _extract_progress(payload: dict[str, Any]) -> float:
    for key in ("progress", "completion_percent", "progress_percent"):
        value = payload.get(key)
        if value is None:
            continue
        try:
            fv = float(value)
        except (TypeError, ValueError):
            continue
        if fv > 1.0:
            return max(0.0, min(1.0, fv / 100.0))
        return max(0.0, min(1.0, fv))
    return 0.0


def render_dashboard(payload: dict[str, Any]) -> Path:
    started = time.perf_counter()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_key = payload_hash(payload)
    out_path = CACHE_DIR / f"{cache_key}.png"
    if out_path.exists():
        logger.info("dashboard cache hit hash=%s", cache_key)
        return out_path
    logger.info("dashboard cache miss hash=%s", cache_key)

    canvas = load_template()
    draw = ImageDraw.Draw(canvas)

    title = str(payload.get("title") or "Дашборд")
    period = str(payload.get("period") or payload.get("decade_title") or "")
    status = str(payload.get("status") or "Смена активна")
    revenue_text = str(payload.get("revenue_text") or "0 ₽")
    target_text = str(payload.get("target_text") or "из 0 ₽")
    progress = _extract_progress(payload)
    percent_text = str(payload.get("progress_text") or f"{int(progress * 100)}%")
    progress_subtitle = str(payload.get("progress_subtitle") or "Выполнение")
    remaining_text = str(payload.get("remaining_text") or "Осталось 0 ₽")

    cards: list[dict[str, str]] = payload.get("cards") or [
        {"title": "Смен", "value": str(payload.get("decade_shifts") or "0"), "title_color": "#F1F3F8", "value_color": "#FFFFFF"},
        {"title": "Машин", "value": str(payload.get("decade_cars") or "0"), "title_color": "#F1F3F8", "value_color": "#FFFFFF"},
        {"title": "Средний чек", "value": str(payload.get("avg_check_text") or "0 ₽"), "title_color": "#7BFF9A", "value_color": "#F8FFFA"},
    ]
    metrics: list[dict[str, str]] = payload.get("bottom_metrics") or [
        {"label": "Смен", "value": str(payload.get("decade_shifts") or "0")},
        {"label": "Машин", "value": str(payload.get("decade_cars") or "0")},
        {"label": "Цель/смену", "value": str(payload.get("needed_per_shift_text") or "—")},
    ]
    trend_text = str(payload.get("trend_text") or "0% к прошлой декаде")
    trend_color = tuple(payload.get("trend_color") or (221, 227, 238, 255))

    updated = payload.get("updated_at")
    if isinstance(updated, datetime):
        updated_text = f"Обновлено: {updated.strftime('%d.%m.%Y %H:%M')}"
    elif isinstance(updated, str) and updated:
        updated_text = updated if updated.lower().startswith("обновлено") else f"Обновлено: {updated}"
    else:
        updated_text = f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    _text(draw, LAYOUT.title_xy, title, size=42, weight="extrabold", fill=(245, 247, 251, 255))
    _text(draw, LAYOUT.period_xy, period, size=22, weight="medium", fill=(211, 217, 229, 255))
    _text(draw, LAYOUT.status_xy, status, size=24, weight="bold", fill=(237, 248, 240, 255))

    _text(draw, LAYOUT.revenue_label_center, "Выручка", size=24, weight="semibold", fill=(200, 207, 222, 255), anchor="ma")
    revenue_font = _fit_font(draw, revenue_text, base=78, min_size=58, safe_width=LAYOUT.revenue_safe_width, weight="extrabold")
    draw.text((LAYOUT.revenue_value_center[0] + 1, LAYOUT.revenue_value_center[1] + 2), revenue_text, font=revenue_font, fill=(0, 0, 0, 95), anchor="ma")
    draw.text(LAYOUT.revenue_value_center, revenue_text, font=revenue_font, fill=(247, 248, 251, 255), anchor="ma")
    _text(draw, LAYOUT.revenue_target_center, target_text, size=33, weight="semibold", fill=(215, 221, 234, 255), anchor="ma")

    draw_gradient_progress_arc(canvas, progress)
    _text(draw, LAYOUT.circle_percent_center, percent_text, size=54, weight="extrabold", fill=(248, 250, 253, 255), anchor="ma")
    _text(draw, LAYOUT.circle_label_center, progress_subtitle, size=22, weight="semibold", fill=(212, 219, 232, 255), anchor="ma")

    draw_gradient_progress_bar(canvas, progress)
    _text(draw, LAYOUT.remaining_xy, remaining_text, size=27, weight="bold", fill=(245, 247, 251, 255))

    c1 = cards[0] if len(cards) > 0 else {"title": "", "value": ""}
    c2 = cards[1] if len(cards) > 1 else {"title": "", "value": ""}
    c3 = cards[2] if len(cards) > 2 else {"title": "", "value": ""}
    _text(draw, LAYOUT.card1_title_xy, str(c1.get("title") or ""), size=24, weight="semibold", fill=(241, 243, 248, 255))
    _text(draw, LAYOUT.card1_value_xy, str(c1.get("value") or ""), size=50, weight="extrabold", fill=(255, 255, 255, 255))
    _text(draw, LAYOUT.card2_title_xy, str(c2.get("title") or ""), size=24, weight="semibold", fill=(241, 243, 248, 255))
    _text(draw, LAYOUT.card2_value_xy, str(c2.get("value") or ""), size=64, weight="extrabold", fill=(255, 255, 255, 255))
    _text(draw, LAYOUT.card3_title_xy, str(c3.get("title") or ""), size=24, weight="semibold", fill=(123, 255, 154, 255))
    _text(draw, LAYOUT.card3_value_xy, str(c3.get("value") or ""), size=56, weight="extrabold", fill=(248, 255, 250, 255))

    m1 = metrics[0] if len(metrics) > 0 else {"label": "", "value": ""}
    m2 = metrics[1] if len(metrics) > 1 else {"label": "", "value": ""}
    m3 = metrics[2] if len(metrics) > 2 else {"label": "", "value": ""}
    _text(draw, LAYOUT.m1_label_xy, str(m1.get("label") or ""), size=22, weight="semibold", fill=(221, 227, 238, 255))
    _text(draw, LAYOUT.m1_value_xy, str(m1.get("value") or ""), size=24, weight="extrabold", fill=(255, 255, 255, 255))
    _text(draw, LAYOUT.m2_label_xy, str(m2.get("label") or ""), size=22, weight="semibold", fill=(221, 227, 238, 255))
    _text(draw, LAYOUT.m2_value_xy, str(m2.get("value") or ""), size=24, weight="extrabold", fill=(255, 255, 255, 255))
    _text(draw, LAYOUT.m3_label_xy, str(m3.get("label") or ""), size=22, weight="semibold", fill=(221, 227, 238, 255))
    _text(draw, LAYOUT.m3_value_xy, str(m3.get("value") or ""), size=24, weight="extrabold", fill=(255, 255, 255, 255))

    _text(draw, LAYOUT.trend_center, trend_text, size=18, weight="bold", fill=trend_color, anchor="ma")
    _text(draw, LAYOUT.updated_center, updated_text, size=23, weight="medium", fill=(200, 207, 220, 255), anchor="ma")

    canvas.save(out_path, format="PNG", optimize=True)
    render_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info("dashboard rendered hash=%s path=%s render_ms=%s", cache_key, out_path, render_ms)
    return out_path


def render_debug_dashboard(output_path: Path | None = None) -> Path:
    demo = {
        "title": "Дашборд",
        "period": "1-я декада • 1–10 марта",
        "status": "Смена активна",
        "revenue_text": "30 205 ₽",
        "target_text": "из 50 000 ₽",
        "progress": 0.60,
        "progress_subtitle": "до цели",
        "remaining_text": "Осталось 19 795 ₽",
        "cards": [
            {"title": "Смен", "value": "6"},
            {"title": "Машин", "value": "91"},
            {"title": "Нужно в смену", "value": "4 949 ₽"},
        ],
        "bottom_metrics": [
            {"label": "Ср. чек", "value": "332 ₽"},
            {"label": "Смен осталось", "value": "4"},
            {"label": "Цель", "value": "50 000 ₽"},
        ],
        "trend_text": "+12% к прошлой декаде",
        "trend_color": (122, 255, 159, 255),
        "updated_at": datetime.now(),
    }
    path = render_dashboard(demo)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(path.read_bytes())
        return output_path
    return path
