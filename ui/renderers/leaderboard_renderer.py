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


@dataclass(frozen=True, slots=True)
class AvatarSlot:
    center: tuple[int, int]
    image_size: int = 148


@dataclass(frozen=True, slots=True)
class TextSlot:
    xy: tuple[int, int]
    max_width: int
    anchor: str | None = None


@dataclass(frozen=True, slots=True)
class LeaderboardLayout:
    period_box: tuple[int, int, int, int] = (330, 285, 365, 72)
    updated_slot: TextSlot = TextSlot((285, 1432), 470)

    avatar_slots: dict[int, AvatarSlot] = None  # type: ignore[assignment]
    rank_slots: dict[int, tuple[int, int, int, int]] = None  # type: ignore[assignment]
    name_slots: dict[int, TextSlot] = None  # type: ignore[assignment]
    amount_slots: dict[int, tuple[int, int, int, int]] = None  # type: ignore[assignment]
    tail_name_slots: dict[int, TextSlot] = None  # type: ignore[assignment]
    tail_amount_right_x: int = 960

    def __post_init__(self) -> None:
        object.__setattr__(self, "avatar_slots", {
            1: AvatarSlot((256, 523)),
            2: AvatarSlot((256, 748)),
            3: AvatarSlot((256, 975)),
        })
        object.__setattr__(self, "rank_slots", {
            1: (378, 489, 243, 52),
            2: (378, 714, 185, 52),
            3: (378, 940, 205, 52),
        })
        object.__setattr__(self, "name_slots", {
            1: TextSlot((382, 552), 300),
            2: TextSlot((382, 778), 350),
            3: TextSlot((382, 1003), 320),
        })
        object.__setattr__(self, "amount_slots", {
            1: (720, 528, 210, 74),
            2: (734, 764, 210, 68),
            3: (730, 992, 210, 68),
        })
        object.__setattr__(self, "tail_name_slots", {
            4: TextSlot((128, 1212), 560),
            5: TextSlot((128, 1312), 560),
        })


LAYOUT = LeaderboardLayout()

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
    return hashlib.sha256(serialize_payload(payload).encode("utf-8")).hexdigest()


def fit_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    start_size: int,
    min_size: int,
    weight: str,
) -> tuple[str, Any]:
    current = start_size
    while current >= min_size:
        font = get_font(current, weight)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return text, font
        current -= 2

    font = get_font(min_size, weight)
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text, font

    shortened = text
    while shortened:
        candidate = shortened.rstrip() + "…"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            return candidate, font
        shortened = shortened[:-1]
    return "…", font


def _format_updated_text(raw: Any) -> str:
    if isinstance(raw, datetime):
        return raw.strftime("%d.%m.%Y %H:%M МСК")
    if raw:
        return str(raw)
    return datetime.now().strftime("%d.%m.%Y %H:%M МСК")


def _default_avatar() -> Image.Image:
    return Image.new("RGB", (148, 148), (44, 59, 92))


def _load_avatar_image(path: str | None) -> tuple[Image.Image, str]:
    if not path:
        logger.info("leaderboard avatar source=fallback reason=empty-path")
        return _default_avatar(), "fallback"
    p = Path(path)
    if not p.exists():
        logger.info("leaderboard avatar source=fallback reason=missing-file path=%s", p)
        return _default_avatar(), "fallback"
    try:
        with Image.open(p) as src:
            img = ImageOps.exif_transpose(src).convert("RGB")
    except OSError:
        logger.info("leaderboard avatar source=fallback reason=decode-error path=%s", p)
        return _default_avatar(), "fallback"
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    logger.info("leaderboard avatar source=file path=%s", p)
    return img.crop((left, top, left + side, top + side)).resize((148, 148), Image.Resampling.LANCZOS), "file"


def _avatar_circle(image: Image.Image, center: tuple[int, int], avatar: Image.Image) -> None:
    mask = Image.new("L", avatar.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, avatar.width, avatar.height), fill=255)
    image.paste(avatar.convert("RGBA"), (center[0] - avatar.width // 2, center[1] - avatar.height // 2), mask)


def load_template() -> Image.Image | None:
    exists = LEADERBOARD_TEMPLATE_PATH.exists() and LEADERBOARD_TEMPLATE_PATH.is_file()
    logger.info("leaderboard template load path=%s exists=%s", LEADERBOARD_TEMPLATE_PATH.resolve(), exists)
    if exists:
        try:
            return Image.open(LEADERBOARD_TEMPLATE_PATH).convert("RGBA")
        except OSError:
            logger.exception("leaderboard template read error path=%s", LEADERBOARD_TEMPLATE_PATH)
            return None
    logger.error("leaderboard template missing path=%s", LEADERBOARD_TEMPLATE_PATH)
    return None


def render_fallback(payload: dict[str, Any], out_path: Path) -> Path:
    canvas = Image.new("RGBA", (1024, 1536), (18, 25, 42, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((60, 80), "🏆 Топ героев", fill=(255, 255, 255, 255), font=get_font(52, "extrabold"))
    draw.text((60, 170), str(payload.get("period_text") or ""), fill=(220, 228, 244, 255), font=get_font(34, "bold"))
    y = 260
    for leader in (payload.get("leaders") or [])[:5]:
        row = f"{leader.get('place', '?')}. {leader.get('name', '—')} — {leader.get('amount', '—')}"
        draw.text((60, y), row, fill=(245, 246, 250, 255), font=get_font(34, "semibold"))
        y += 96
    draw.text((60, 1460), _format_updated_text(payload.get("updated_text")), fill=(181, 192, 218, 255), font=get_font(26, "medium"))
    canvas.save(out_path)
    return out_path


def render_leaderboard(payload: dict[str, Any]) -> Path:
    started = time.perf_counter()
    logger.info("leaderboard renderer selected=template-v2")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_key = payload_hash(payload)
    out_path = CACHE_DIR / f"{cache_key}.png"
    if out_path.exists():
        logger.info("leaderboard cache hit hash=%s", cache_key)
        return out_path
    logger.info("leaderboard cache miss hash=%s", cache_key)

    canvas = load_template()
    if canvas is None:
        return render_fallback(payload, out_path)

    draw = ImageDraw.Draw(canvas)
    period = str(payload.get("period_text") or "")
    period_text, period_font = fit_text_to_width(draw, period, LAYOUT.period_box[2], 36, 30, "bold")
    draw.text(
        (LAYOUT.period_box[0] + LAYOUT.period_box[2] // 2, LAYOUT.period_box[1] + LAYOUT.period_box[3] // 2),
        period_text,
        fill=(242, 245, 255, 255),
        font=period_font,
        anchor="mm",
    )

    leaders: list[dict[str, Any]] = list(payload.get("leaders") or [])
    by_place = {int(row.get("place", idx + 1)): row for idx, row in enumerate(leaders)}

    for place in (1, 2, 3):
        row = by_place.get(place, {})
        avatar, avatar_source = _load_avatar_image(str(row.get("avatar_path") or "") or None)
        _avatar_circle(canvas, LAYOUT.avatar_slots[place].center, avatar)
        logger.info("leaderboard avatar inserted place=%s source=%s path=%s", place, avatar_source, row.get("avatar_path") or "default")

        rank_box = LAYOUT.rank_slots[place]
        rank_text = str(row.get("rank_prefix") or row.get("rank_text") or "—")
        rank_color = RANK_COLORS.get(place, (242, 245, 255, 255))
        rank_start_size = 26 if place in (1, 3) else 28
        rank_value, rank_font = fit_text_to_width(draw, rank_text, rank_box[2], rank_start_size, 22, "bold")
        draw.text((rank_box[0] + rank_box[2] // 2, rank_box[1] + rank_box[3] // 2), rank_value, fill=rank_color, font=rank_font, anchor="mm")

        name_slot = LAYOUT.name_slots[place]
        name = str(row.get("name") or "—")
        if place == 1:
            name_text, name_font = fit_text_to_width(draw, name, name_slot.max_width, 58, 40, "extrabold")
        elif place == 2:
            name_text, name_font = fit_text_to_width(draw, name, name_slot.max_width, 44, 34, "extrabold")
        else:
            name_text, name_font = fit_text_to_width(draw, name, name_slot.max_width, 50, 38, "extrabold")
        draw.text(name_slot.xy, name_text, fill=(255, 255, 255, 255), font=name_font)

        amount_box = LAYOUT.amount_slots[place]
        amount = str(row.get("amount") or format_money_rub(int(row.get("total_amount") or 0)))
        amount_start_size = {1: 48, 2: 44, 3: 42}[place]
        amount_text, amount_font = fit_text_to_width(draw, amount, amount_box[2], amount_start_size, 30, "extrabold")
        draw.text(
            (amount_box[0] + amount_box[2] // 2, amount_box[1] + amount_box[3] // 2),
            amount_text,
            fill=AMOUNT_COLORS[place],
            font=amount_font,
            anchor="mm",
        )

    for place in (4, 5):
        row = by_place.get(place, {})
        name_slot = LAYOUT.tail_name_slots[place]
        name = str(row.get("name") or "—")
        name_text, name_font = fit_text_to_width(draw, name, name_slot.max_width, 36, 30, "bold")
        draw.text(name_slot.xy, name_text, fill=(232, 237, 255, 255), font=name_font)

        amount = str(row.get("amount") or format_money_rub(int(row.get("total_amount") or 0)))
        amount_text, amount_font = fit_text_to_width(draw, amount, 260, 36, 30, "extrabold")
        draw.text((LAYOUT.tail_amount_right_x, name_slot.xy[1]), amount_text, fill=(255, 255, 255, 255), font=amount_font, anchor="ra")

    updated_text = _format_updated_text(payload.get("updated_text"))
    fitted_updated, updated_font = fit_text_to_width(draw, updated_text, LAYOUT.updated_slot.max_width, 30, 24, "semibold")
    draw.text(LAYOUT.updated_slot.xy, fitted_updated, fill=(215, 221, 242, 255), font=updated_font)

    canvas.save(out_path)
    elapsed = (time.perf_counter() - started) * 1000
    logger.info("leaderboard render done hash=%s took_ms=%.2f output=%s", cache_key, elapsed, out_path)
    return out_path
