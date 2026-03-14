from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from config import BASE_DIR, DASHBOARD_TEMPLATE_PATH

logger = logging.getLogger(__name__)

CACHE_DIR = BASE_DIR / "cache" / "dashboard"


@dataclass(frozen=True, slots=True)
class DashboardLayout:
    width: int = 1536
    height: int = 1024
    title_xy: tuple[int, int] = (96, 78)
    period_xy: tuple[int, int] = (98, 139)
    status_xy: tuple[int, int] = (1080, 80)
    revenue_label_center_x: int = 702
    revenue_label_y: int = 202
    revenue_center_x: int = 707
    revenue_y: int = 238
    revenue_safe_width: int = 520
    revenue_target_y: int = 335


LAYOUT = DashboardLayout()


@lru_cache(maxsize=128)
def load_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    candidates = {
        "extrabold": ["/usr/share/fonts/truetype/manrope/Manrope-ExtraBold.ttf", "/usr/share/fonts/truetype/inter/Inter-ExtraBold.ttf", "/usr/share/fonts/truetype/inter/Inter-Bold.ttf"],
        "bold": ["/usr/share/fonts/truetype/manrope/Manrope-Bold.ttf", "/usr/share/fonts/truetype/inter/Inter-Bold.ttf"],
        "semibold": ["/usr/share/fonts/truetype/manrope/Manrope-SemiBold.ttf", "/usr/share/fonts/truetype/inter/Inter-SemiBold.ttf", "/usr/share/fonts/truetype/inter/Inter-Medium.ttf"],
        "medium": ["/usr/share/fonts/truetype/manrope/Manrope-Medium.ttf", "/usr/share/fonts/truetype/inter/Inter-Medium.ttf"],
        "regular": ["/usr/share/fonts/truetype/manrope/Manrope-Regular.ttf", "/usr/share/fonts/truetype/inter/Inter-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    }
    for p in candidates.get(weight, candidates["regular"]):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            logger.debug("font not found path=%s", p)
    logger.warning("font fallback used size=%s weight=%s", size, weight)
    return ImageFont.load_default()


def serialize_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(serialize_payload(payload).encode("utf-8")).hexdigest()


def _safe_template() -> Image.Image:
    if DASHBOARD_TEMPLATE_PATH.exists():
        logger.info("dashboard template path=%s", DASHBOARD_TEMPLATE_PATH)
        return Image.open(DASHBOARD_TEMPLATE_PATH).convert("RGBA")
    logger.error("dashboard template is missing path=%s", DASHBOARD_TEMPLATE_PATH)
    return Image.new("RGBA", (LAYOUT.width, LAYOUT.height), (15, 22, 35, 255))


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, *, size: int, weight: str, fill: tuple[int, int, int, int], anchor: str | None = None) -> None:
    font = load_font(size, weight)
    shadow_xy = (xy[0] + 1, xy[1] + 2)
    draw.text(shadow_xy, text, font=font, fill=(0, 0, 0, 90), anchor=anchor)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, base_size: int, min_size: int, safe_width: int, weight: str) -> ImageFont.FreeTypeFont:
    size = base_size
    while size >= min_size:
        font = load_font(size, weight)
        w = draw.textbbox((0, 0), text, font=font)[2]
        if w <= safe_width:
            return font
        size -= 2
    return load_font(min_size, weight)


def render_dashboard(payload: dict[str, Any]) -> Path:
    started = time.perf_counter()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = payload_hash(payload)
    out_path = CACHE_DIR / f"{h}.png"
    if out_path.exists():
        logger.info("dashboard cache hit hash=%s", h)
        return out_path
    logger.info("dashboard cache miss hash=%s", h)

    img = _safe_template()
    draw = ImageDraw.Draw(img)
    _text(draw, LAYOUT.title_xy, str(payload.get("title") or "Дашборд"), size=42, weight="extrabold", fill=(245, 247, 251, 255))
    _text(draw, LAYOUT.period_xy, str(payload.get("period") or ""), size=22, weight="medium", fill=(211, 217, 229, 255))
    _text(draw, LAYOUT.status_xy, str(payload.get("status") or ""), size=24, weight="bold", fill=(237, 248, 240, 255))
    _text(draw, (LAYOUT.revenue_label_center_x, LAYOUT.revenue_label_y), "Выручка", size=24, weight="semibold", fill=(200, 207, 222, 255), anchor="ma")

    revenue = str(payload.get("revenue_text") or "0 ₽")
    revenue_font = _fit_text(draw, revenue, 78, 58, LAYOUT.revenue_safe_width, "extrabold")
    draw.text((LAYOUT.revenue_center_x + 1, LAYOUT.revenue_y + 2), revenue, font=revenue_font, fill=(0, 0, 0, 90), anchor="ma")
    draw.text((LAYOUT.revenue_center_x, LAYOUT.revenue_y), revenue, font=revenue_font, fill=(247, 248, 251, 255), anchor="ma")
    _text(draw, (LAYOUT.revenue_center_x, LAYOUT.revenue_target_y), str(payload.get("target_text") or ""), size=33, weight="semibold", fill=(215, 221, 234, 255), anchor="ma")
    _text(draw, (780, 878), str(payload.get("updated_at") or datetime.now().strftime("Обновлено: %d.%m.%Y %H:%M")), size=23, weight="medium", fill=(200, 207, 220, 255), anchor="ma")

    img.save(out_path, format="PNG", optimize=True)
    logger.info("dashboard rendered hash=%s path=%s render_ms=%s", h, out_path, round((time.perf_counter() - started) * 1000, 2))
    return out_path
