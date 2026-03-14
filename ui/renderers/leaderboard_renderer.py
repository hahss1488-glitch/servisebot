from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from config import BASE_DIR, LEADERBOARD_TEMPLATE_PATH
from services.formatting import format_money_rub
from ui.renderers.font_manager import get_font

logger = logging.getLogger(__name__)

CACHE_DIR = BASE_DIR / "cache" / "leaderboard"
BASE_SIZE = (1024, 1536)
RENDER_VERSION = "v2-layout-fix-2026-03-14"


@dataclass(frozen=True, slots=True)
class Box:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass(frozen=True, slots=True)
class LeaderboardLayout:
    title_box: Box
    period_box: Box
    role_boxes: dict[int, Box]
    name_boxes: dict[int, Box]
    amount_boxes: dict[int, Box]
    row_name_boxes: dict[int, Box]
    row_amount_boxes: dict[int, Box]
    updated_small_box: Box
    updated_bottom_box: Box
    avatar_centers: dict[int, tuple[int, int]]
    avatar_diameter: int


BASE_LAYOUT = LeaderboardLayout(
    title_box=Box(236, 240, 552, 74),
    period_box=Box(240, 322, 544, 42),
    role_boxes={
        1: Box(406, 490, 220, 56),
        2: Box(406, 678, 220, 56),
        3: Box(406, 866, 220, 56),
    },
    name_boxes={
        1: Box(382, 582, 320, 50),
        2: Box(384, 770, 310, 50),
        3: Box(384, 958, 310, 50),
    },
    amount_boxes={
        1: Box(692, 489, 236, 92),
        2: Box(692, 677, 236, 92),
        3: Box(692, 865, 236, 92),
    },
    row_name_boxes={
        4: Box(200, 1052, 520, 60),
        5: Box(200, 1148, 520, 60),
    },
    row_amount_boxes={
        4: Box(738, 1050, 190, 60),
        5: Box(738, 1146, 190, 60),
    },
    updated_small_box=Box(97, 1238, 430, 52),
    updated_bottom_box=Box(287, 1410, 450, 46),
    avatar_centers={
        1: (268, 542),
        2: (260, 730),
        3: (259, 918),
    },
    avatar_diameter=146,
)

RANK_COLORS = {
    1: (247, 216, 255, 255),
    2: (89, 196, 255, 255),
    3: (255, 195, 110, 255),
}

AMOUNT_COLORS = {
    1: (255, 213, 74, 255),
    2: (243, 246, 255, 255),
    3: (255, 194, 111, 255),
}


def serialize_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def payload_hash(payload: dict[str, Any]) -> str:
    payload_with_version = {"_renderer_version": RENDER_VERSION, **payload}
    return hashlib.sha256(serialize_payload(payload_with_version).encode("utf-8")).hexdigest()


def _scaled(value: int, ratio: float) -> int:
    return max(1, int(round(value * ratio)))


def _scale_box(box: Box, x_ratio: float, y_ratio: float) -> Box:
    return Box(
        _scaled(box.x, x_ratio),
        _scaled(box.y, y_ratio),
        _scaled(box.width, x_ratio),
        _scaled(box.height, y_ratio),
    )


def resolve_layout(size: tuple[int, int]) -> LeaderboardLayout:
    x_ratio = size[0] / BASE_SIZE[0]
    y_ratio = size[1] / BASE_SIZE[1]
    if x_ratio == 1 and y_ratio == 1:
        return BASE_LAYOUT
    return LeaderboardLayout(
        title_box=_scale_box(BASE_LAYOUT.title_box, x_ratio, y_ratio),
        period_box=_scale_box(BASE_LAYOUT.period_box, x_ratio, y_ratio),
        role_boxes={k: _scale_box(v, x_ratio, y_ratio) for k, v in BASE_LAYOUT.role_boxes.items()},
        name_boxes={k: _scale_box(v, x_ratio, y_ratio) for k, v in BASE_LAYOUT.name_boxes.items()},
        amount_boxes={k: _scale_box(v, x_ratio, y_ratio) for k, v in BASE_LAYOUT.amount_boxes.items()},
        row_name_boxes={k: _scale_box(v, x_ratio, y_ratio) for k, v in BASE_LAYOUT.row_name_boxes.items()},
        row_amount_boxes={k: _scale_box(v, x_ratio, y_ratio) for k, v in BASE_LAYOUT.row_amount_boxes.items()},
        updated_small_box=_scale_box(BASE_LAYOUT.updated_small_box, x_ratio, y_ratio),
        updated_bottom_box=_scale_box(BASE_LAYOUT.updated_bottom_box, x_ratio, y_ratio),
        avatar_centers={k: (_scaled(v[0], x_ratio), _scaled(v[1], y_ratio)) for k, v in BASE_LAYOUT.avatar_centers.items()},
        avatar_diameter=_scaled(BASE_LAYOUT.avatar_diameter, min(x_ratio, y_ratio)),
    )


def text_width(draw: ImageDraw.ImageDraw, text: str, font: Any) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def fit_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_font_size: int,
    min_font_size: int,
    weight: str,
    *,
    ellipsis: bool = True,
) -> tuple[str, Any]:
    source = " ".join(str(text or "").split())
    if not source:
        source = "—"

    for size in range(max_font_size, min_font_size - 1, -1):
        font = get_font(size, weight)
        if text_width(draw, source, font) <= max_width:
            return source, font

    font = get_font(min_font_size, weight)
    if not ellipsis:
        return source, font

    cut = source
    while cut:
        candidate = cut.rstrip() + "…"
        if text_width(draw, candidate, font) <= max_width:
            return candidate, font
        cut = cut[:-1]
    return "…", font


def draw_text_aligned(
    draw: ImageDraw.ImageDraw,
    box: Box,
    text: str,
    font: Any,
    fill: tuple[int, int, int, int],
    *,
    align: str = "left",
    valign: str = "middle",
    padding_left: int = 0,
    padding_right: int = 0,
) -> None:
    anchor_map = {
        ("left", "top"): "la",
        ("left", "middle"): "lm",
        ("left", "bottom"): "ld",
        ("center", "top"): "ma",
        ("center", "middle"): "mm",
        ("center", "bottom"): "md",
        ("right", "top"): "ra",
        ("right", "middle"): "rm",
        ("right", "bottom"): "rd",
    }
    x = box.x + padding_left
    if align == "center":
        x = box.x + box.width // 2
    elif align == "right":
        x = box.right - padding_right

    y = box.y
    if valign == "middle":
        y = box.y + box.height // 2
    elif valign == "bottom":
        y = box.bottom

    draw.text((x, y), text, fill=fill, font=font, anchor=anchor_map[(align, valign)])


def _format_amount(row: dict[str, Any], *, with_currency_default: bool = True) -> str:
    amount = str(row.get("amount") or "").strip()
    if amount:
        return amount
    total_amount = row.get("total_amount")
    if total_amount is not None:
        try:
            return format_money_rub(int(total_amount))
        except (TypeError, ValueError):
            pass
    return "0 ₽" if with_currency_default else "0"


def _format_updated_text(raw: Any, *, compact: bool = False) -> str:
    fmt = "%d.%m.%Y %H:%M"
    if isinstance(raw, datetime):
        return raw.strftime(fmt + " МСК")
    if raw:
        return str(raw)
    if compact:
        return "—"
    return datetime.now().strftime(fmt + " МСК")


def _initials(name: str) -> str:
    tokens = [p for p in str(name).strip().split() if p]
    if not tokens:
        return "?"
    if len(tokens) == 1:
        return tokens[0][:2].upper()
    return (tokens[0][0] + tokens[1][0]).upper()


def _clean_display_name(raw: Any, fallback: str) -> str:
    value = " ".join(str(raw or "").split())
    lowered = value.lower()
    blocked = {"👤 профиль", "профиль", "profile", "👤profile", "👤"}
    if not value or lowered in blocked:
        return fallback
    return value


def _load_avatar_circle(path: str | None, diameter: int, initials: str) -> Image.Image:
    if path:
        p = Path(path)
        if p.exists():
            try:
                with Image.open(p) as src:
                    img = ImageOps.exif_transpose(src).convert("RGBA")
                side = min(img.size)
                left = (img.width - side) // 2
                top = (img.height - side) // 2
                img = img.crop((left, top, left + side, top + side)).resize((diameter, diameter), Image.Resampling.LANCZOS)
            except OSError:
                logger.warning("leaderboard avatar decode error path=%s", p)
                img = Image.new("RGBA", (diameter, diameter), (44, 59, 92, 255))
        else:
            logger.info("leaderboard avatar missing path=%s", p)
            img = Image.new("RGBA", (diameter, diameter), (44, 59, 92, 255))
    else:
        img = Image.new("RGBA", (diameter, diameter), (44, 59, 92, 255))

    mask = Image.new("L", (diameter * 4, diameter * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter * 4 - 1, diameter * 4 - 1), fill=255)
    mask = mask.resize((diameter, diameter), Image.Resampling.LANCZOS)

    avatar = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    avatar.paste(img, (0, 0), mask)

    if not path or (path and not Path(path).exists()):
        draw = ImageDraw.Draw(avatar)
        font = get_font(max(14, int(round(diameter * 0.30))), "bold")
        draw.text((diameter // 2, diameter // 2), initials, fill=(255, 255, 255, 217), font=font, anchor="mm")

    return avatar


def load_template() -> Image.Image | None:
    exists = LEADERBOARD_TEMPLATE_PATH.exists() and LEADERBOARD_TEMPLATE_PATH.is_file()
    logger.info("leaderboard template load path=%s exists=%s", LEADERBOARD_TEMPLATE_PATH.resolve(), exists)
    if exists:
        try:
            image = Image.open(LEADERBOARD_TEMPLATE_PATH).convert("RGBA")
            logger.info("leaderboard template size=%sx%s", image.width, image.height)
            return image
        except OSError:
            logger.exception("leaderboard template read error path=%s", LEADERBOARD_TEMPLATE_PATH)
            return None
    logger.error("leaderboard template missing path=%s", LEADERBOARD_TEMPLATE_PATH)
    return None



def _title_region_has_text(canvas: Image.Image, box: Box) -> bool:
    region = canvas.crop((box.x, box.y, box.right, box.bottom)).convert("L")
    histogram = region.histogram()
    bright_pixels = sum(histogram[170:])
    return bright_pixels > 2200


def _render_top_title(draw: ImageDraw.ImageDraw, canvas: Image.Image, layout: LeaderboardLayout) -> None:
    if _title_region_has_text(canvas, layout.title_box):
        return
    title_text, title_font = fit_text_to_width(draw, "ТОП ГЕРОЕВ", layout.title_box.width, 64, 54, "extrabold")
    draw_text_aligned(draw, layout.title_box, title_text, title_font, (245, 245, 250, 255), align="center", valign="middle")


def render_fallback(payload: dict[str, Any], out_path: Path) -> Path:
    canvas = Image.new("RGBA", BASE_SIZE, (18, 25, 42, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((60, 80), "🏆 Топ героев", fill=(255, 255, 255, 255), font=get_font(52, "extrabold"))
    draw.text((60, 170), str(payload.get("period_text") or "Текущий период"), fill=(220, 228, 244, 255), font=get_font(34, "bold"))
    y = 260
    for leader in (payload.get("leaders") or [])[:5]:
        row = f"{leader.get('place', '?')}. {leader.get('name', '—')} — {_format_amount(leader)}"
        draw.text((60, y), row, fill=(245, 246, 250, 255), font=get_font(34, "semibold"))
        y += 96
    draw.text((60, 1460), _format_updated_text(payload.get("updated_text")), fill=(181, 192, 218, 255), font=get_font(26, "medium"))
    canvas.save(out_path)
    return out_path


def render_leaderboard(payload: dict[str, Any]) -> Path:
    started = time.perf_counter()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_key = payload_hash(payload)
    out_path = CACHE_DIR / f"{cache_key}.png"
    if out_path.exists():
        logger.info("leaderboard cache hit hash=%s", cache_key)
        return out_path

    canvas = load_template()
    if canvas is None:
        return render_fallback(payload, out_path)

    layout = resolve_layout(canvas.size)
    draw = ImageDraw.Draw(canvas)

    _render_top_title(draw, canvas, layout)

    period = str(payload.get("period_text") or "Текущий период")
    period_text, period_font = fit_text_to_width(draw, period, layout.period_box.width, 32, 26, "bold")
    draw_text_aligned(draw, layout.period_box, period_text, period_font, (245, 245, 250, 255), align="center", valign="middle")

    leaders: list[dict[str, Any]] = list(payload.get("leaders") or [])
    by_place = {int(row.get("place", idx + 1)): row for idx, row in enumerate(leaders)}

    for place in (1, 2, 3):
        row = by_place.get(place, {})
        name_raw = _clean_display_name(row.get("name"), "Неизвестный герой")
        avatar_img = _load_avatar_circle(str(row.get("avatar_path") or "") or None, layout.avatar_diameter, _initials(name_raw))
        center = layout.avatar_centers[place]
        canvas.alpha_composite(avatar_img, (center[0] - layout.avatar_diameter // 2, center[1] - layout.avatar_diameter // 2))

        role = str(row.get("rank_prefix") or row.get("rank_text") or "PLAYER").upper()
        role_text, role_font = fit_text_to_width(draw, role, _scaled(190, canvas.width / BASE_SIZE[0]), 24, 20, "bold")
        draw_text_aligned(draw, layout.role_boxes[place], role_text, role_font, RANK_COLORS.get(place, (242, 245, 255, 255)), align="center", valign="middle")

        name_box = layout.name_boxes[place]
        name_size = {1: 40, 2: 38, 3: 36}[place]
        name_text, name_font = fit_text_to_width(draw, name_raw, name_box.width, _scaled(name_size, canvas.width / BASE_SIZE[0]), _scaled(30, canvas.width / BASE_SIZE[0]), "extrabold")
        draw_text_aligned(draw, name_box, name_text, name_font, (250, 252, 255, 255), align="left", valign="middle", padding_left=_scaled(2, canvas.width / BASE_SIZE[0]))

        amount_box = layout.amount_boxes[place]
        amount_text_raw = _format_amount(row)
        amount_text, amount_font = fit_text_to_width(draw, amount_text_raw, _scaled(200, canvas.width / BASE_SIZE[0]), _scaled(34, canvas.width / BASE_SIZE[0]), _scaled(26, canvas.width / BASE_SIZE[0]), "extrabold", ellipsis=False)
        draw_text_aligned(
            draw,
            amount_box,
            amount_text,
            amount_font,
            AMOUNT_COLORS.get(place, (255, 255, 255, 255)),
            align="right",
            valign="middle",
            padding_right=_scaled(18, canvas.width / BASE_SIZE[0]),
        )

    for place in (4, 5):
        row = by_place.get(place, {})
        name = _clean_display_name(row.get("name"), "—")
        amount = _format_amount(row)

        name_box = layout.row_name_boxes[place]
        name_text, name_font = fit_text_to_width(draw, name, name_box.width, _scaled(28, canvas.width / BASE_SIZE[0]), _scaled(24, canvas.width / BASE_SIZE[0]), "bold")
        draw_text_aligned(draw, name_box, name_text, name_font, (245, 248, 255, 255), align="left", valign="middle")

        amount_box = layout.row_amount_boxes[place]
        amount_text, amount_font = fit_text_to_width(draw, amount, amount_box.width - _scaled(10, canvas.width / BASE_SIZE[0]), _scaled(28, canvas.width / BASE_SIZE[0]), _scaled(24, canvas.width / BASE_SIZE[0]), "bold", ellipsis=False)
        draw_text_aligned(draw, amount_box, amount_text, amount_font, (255, 255, 255, 255), align="right", valign="middle", padding_right=_scaled(10, canvas.width / BASE_SIZE[0]))

    updated_text = _format_updated_text(payload.get("updated_text"))
    updated_small_text, updated_small_font = fit_text_to_width(
        draw,
        updated_text,
        layout.updated_small_box.width,
        _scaled(24, canvas.width / BASE_SIZE[0]),
        _scaled(20, canvas.width / BASE_SIZE[0]),
        "medium",
    )
    draw_text_aligned(draw, layout.updated_small_box, updated_small_text, updated_small_font, (255, 255, 255, 191), align="left", valign="middle")

    updated_bottom_text, updated_bottom_font = fit_text_to_width(
        draw,
        updated_text,
        layout.updated_bottom_box.width,
        _scaled(28, canvas.width / BASE_SIZE[0]),
        _scaled(22, canvas.width / BASE_SIZE[0]),
        "medium",
    )
    draw_text_aligned(draw, layout.updated_bottom_box, updated_bottom_text, updated_bottom_font, (255, 255, 255, 230), align="center", valign="middle")

    canvas.save(out_path)
    elapsed = (time.perf_counter() - started) * 1000
    logger.info("leaderboard render done hash=%s took_ms=%.2f output=%s", cache_key, elapsed, out_path)
    return out_path
