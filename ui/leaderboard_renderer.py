from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, TypedDict

from PIL import Image, ImageDraw, ImageFont, ImageOps

DEFAULT_TEMPLATE_PATH = Path("ui/assets/leaderboard/leaderboard_template_v2.png")


class PlayerInput(TypedDict, total=False):
    """Raw player payload used by the leaderboard renderer."""

    name: str | None
    prefix: str | None
    money: int | float | Decimal | str | None
    avatar_path: str | Path | bytes | Image.Image | None


@dataclass(frozen=True, slots=True)
class TopPlaceLayout:
    avatar_box: tuple[int, int, int, int]
    name_xy: tuple[int, int]
    name_max_width: int
    name_font_size: int
    name_color: tuple[int, int, int]
    money_center: tuple[int, int]
    money_font_size: int
    money_color: tuple[int, int, int]
    prefix_center: tuple[int, int] | None = None
    prefix_font_size: int | None = None
    prefix_min_font_size: int | None = None
    prefix_max_width: int | None = None
    prefix_color: tuple[int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class CompactPlaceLayout:
    place_xy: tuple[int, int]
    place_font_size: int
    place_color: tuple[int, int, int]
    name_xy: tuple[int, int]
    name_max_width: int
    name_font_size: int
    name_color: tuple[int, int, int]
    money_center: tuple[int, int]
    money_font_size: int
    money_color: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class RenderConfig:
    image_size: tuple[int, int]
    top_layouts: dict[int, TopPlaceLayout]
    compact_layouts: dict[int, CompactPlaceLayout]


CONFIG = RenderConfig(
    image_size=(1024, 1536),
    top_layouts={
        1: TopPlaceLayout(
            avatar_box=(170, 468, 326, 624),
            name_xy=(380, 605),
            name_max_width=420,
            name_font_size=48,
            name_color=(245, 245, 245),
            money_center=(860, 542),
            money_font_size=42,
            money_color=(255, 210, 120),
        ),
        2: TopPlaceLayout(
            avatar_box=(180, 659, 320, 799),
            name_xy=(380, 792),
            name_max_width=420,
            name_font_size=48,
            name_color=(245, 245, 245),
            money_center=(860, 730),
            money_font_size=42,
            money_color=(210, 220, 255),
            prefix_center=(520, 730),
            prefix_font_size=30,
            prefix_min_font_size=22,
            prefix_max_width=280,
            prefix_color=(130, 200, 255),
        ),
        3: TopPlaceLayout(
            avatar_box=(180, 847, 320, 987),
            name_xy=(380, 980),
            name_max_width=420,
            name_font_size=48,
            name_color=(245, 245, 245),
            money_center=(860, 918),
            money_font_size=42,
            money_color=(255, 200, 150),
            prefix_center=(520, 918),
            prefix_font_size=30,
            prefix_min_font_size=22,
            prefix_max_width=280,
            prefix_color=(255, 180, 120),
        ),
    },
    compact_layouts={
        4: CompactPlaceLayout(
            place_xy=(120, 1080),
            place_font_size=44,
            place_color=(245, 245, 245),
            name_xy=(200, 1080),
            name_max_width=520,
            name_font_size=42,
            name_color=(245, 245, 245),
            money_center=(860, 1080),
            money_font_size=40,
            money_color=(220, 230, 255),
        ),
        5: CompactPlaceLayout(
            place_xy=(120, 1176),
            place_font_size=44,
            place_color=(245, 245, 245),
            name_xy=(200, 1176),
            name_max_width=520,
            name_font_size=42,
            name_color=(245, 245, 245),
            money_center=(860, 1176),
            money_font_size=40,
            money_color=(220, 230, 255),
        ),
    },
)

_FONT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "bold": (
        "Inter-Bold.ttf",
        "Inter-SemiBold.ttf",
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
    ),
    "semibold": (
        "Inter-SemiBold.ttf",
        "Inter-Medium.ttf",
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
    ),
    "regular": (
        "Inter-Regular.ttf",
        "Inter-Medium.ttf",
        "DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf",
    ),
}
_SYSTEM_FONT_DIRS = (
    Path("/usr/share/fonts/truetype/inter"),
    Path("/usr/share/fonts/truetype/dejavu"),
)


class LeaderboardRenderError(RuntimeError):
    """Raised when rendering cannot continue."""


def load_font(
    size: int,
    weight: Literal["regular", "semibold", "bold"] = "regular",
    fonts_dir: str | Path | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a project font and fall back to DejaVu/default font when unavailable."""

    weight_key: Literal["regular", "semibold", "bold"] = weight if weight in _FONT_CANDIDATES else "regular"
    search_dirs: list[Path] = []
    if fonts_dir is not None:
        search_dirs.append(Path(fonts_dir))
    search_dirs.extend([Path("ui/assets/fonts"), *(_SYSTEM_FONT_DIRS)])

    for directory in search_dirs:
        for file_name in _FONT_CANDIDATES[weight_key]:
            font_path = directory / file_name
            if font_path.is_file():
                try:
                    return ImageFont.truetype(str(font_path), size)
                except OSError:
                    continue

    # Known absolute fallback when present in container/runtime.
    for fallback in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(fallback, size)
        except OSError:
            continue
    return ImageFont.load_default()


def measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    """Measure text width in pixels using Pillow metrics."""

    bbox = draw.textbbox((0, 0), text, font=font)
    return max(0, bbox[2] - bbox[0])


def fit_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str | None,
    font: ImageFont.ImageFont,
    max_width: int,
    ellipsis: str = "...",
) -> str:
    """Fit single-line text into max_width by truncating and appending ellipsis."""

    normalized = " ".join(str(text or "").split())
    if not normalized:
        return ""
    if measure_text(draw, normalized, font) <= max_width:
        return normalized

    ellipsis_width = measure_text(draw, ellipsis, font)
    if ellipsis_width >= max_width:
        return ""

    left, right = 0, len(normalized)
    while left < right:
        middle = (left + right + 1) // 2
        candidate = normalized[:middle].rstrip() + ellipsis
        if measure_text(draw, candidate, font) <= max_width:
            left = middle
        else:
            right = middle - 1

    fitted = normalized[:left].rstrip()
    return f"{fitted}{ellipsis}" if fitted else ""


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    """Draw text centered by its midpoint using anchor mm."""

    if not text:
        return
    draw.text(center, text, font=font, fill=fill, anchor="mm")


def safe_get_initials(name: str | None) -> str:
    """Extract up to two initials from a name, supporting Cyrillic and Latin input."""

    cleaned = " ".join(str(name or "").split())
    if not cleaned:
        return "?"
    parts = [part for part in cleaned.split(" ") if part]
    if not parts:
        return "?"

    letters = [part[0].upper() for part in parts if part[0].isalpha()]
    if not letters:
        first = parts[0][0]
        return first.upper() if first else "?"
    if len(letters) == 1:
        token = "".join(ch for ch in parts[0] if ch.isalpha())
        return token[:2].upper() if token else letters[0]
    return (letters[0] + letters[1]).upper()


def create_default_avatar(size: int, name: str | None = None) -> Image.Image:
    """Create a circular fallback avatar with initials in the center."""

    avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient_bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient_draw = ImageDraw.Draw(gradient_bg)
    for y in range(size):
        ratio = y / max(1, size - 1)
        r = int(58 + (96 - 58) * ratio)
        g = int(74 + (112 - 74) * ratio)
        b = int(122 + (172 - 122) * ratio)
        gradient_draw.line((0, y, size, y), fill=(r, g, b, 255))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    avatar.paste(gradient_bg, (0, 0), mask)

    initials = safe_get_initials(name)
    draw = ImageDraw.Draw(avatar)
    text_font = load_font(max(18, int(size * 0.34)), weight="bold")
    draw_centered_text(draw, (size // 2, size // 2), initials, text_font, (255, 255, 255))
    return avatar


def _crop_to_square(image: Image.Image) -> Image.Image:
    side = min(image.width, image.height)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    return image.crop((left, top, left + side, top + side))


def safe_open_avatar(source: str | Path | bytes | Image.Image | None) -> Image.Image | None:
    """Safely open avatar from path, bytes or PIL image."""

    if source is None:
        return None
    try:
        if isinstance(source, Image.Image):
            return source.convert("RGBA")
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.is_file():
                return None
            with Image.open(path) as img:
                return ImageOps.exif_transpose(img).convert("RGBA")
        if isinstance(source, bytes):
            with Image.open(BytesIO(source)) as img:
                return ImageOps.exif_transpose(img).convert("RGBA")
    except (OSError, ValueError):
        return None
    return None


def paste_circular_avatar(
    base_image: Image.Image,
    avatar_source: str | Path | bytes | Image.Image | None,
    box: tuple[int, int, int, int],
    fallback_text: str | None = None,
) -> None:
    """Paste avatar into a circular area defined by box."""

    x1, y1, x2, y2 = box
    size = min(x2 - x1, y2 - y1)
    avatar = safe_open_avatar(avatar_source)
    if avatar is None:
        prepared = create_default_avatar(size=size, name=fallback_text)
    else:
        squared = _crop_to_square(avatar)
        prepared = squared.resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        circular = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circular.paste(prepared, (0, 0), mask)
        prepared = circular

    paste_x = x1 + ((x2 - x1) - size) // 2
    paste_y = y1 + ((y2 - y1) - size) // 2
    base_image.alpha_composite(prepared, (paste_x, paste_y))


def _clean_name(name: str | None) -> str:
    return " ".join(str(name or "").split())


def _to_decimal(value: int | float | Decimal | str | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        normalized = value.replace("₽", "").replace(" ", "").replace(",", ".").strip()
        if not normalized:
            return None
        try:
            return Decimal(normalized)
        except InvalidOperation:
            return None
    return None


def format_money(value: int | float | Decimal | str | None) -> str:
    """Format money as grouped RUB integer, defaulting to zero for invalid data."""

    decimal_value = _to_decimal(value)
    if decimal_value is None:
        amount = 0
    else:
        amount = int(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    grouped = f"{amount:,}".replace(",", " ")
    return f"{grouped} ₽"


def _normalize_players(players: list[PlayerInput]) -> list[PlayerInput]:
    normalized: list[PlayerInput] = []
    for index in range(5):
        source = players[index] if index < len(players) else {}
        normalized.append(
            {
                "name": _clean_name(source.get("name")),
                "prefix": " ".join(str(source.get("prefix") or "").split()),
                "money": source.get("money", 0),
                "avatar_path": source.get("avatar_path"),
            }
        )
    return normalized


def render_top_player(
    base: Image.Image,
    draw: ImageDraw.ImageDraw,
    place: int,
    player: PlayerInput,
    fonts_dir: str | Path | None = None,
) -> None:
    """Render top-3 row with avatar, optional prefix, name and amount."""

    layout = CONFIG.top_layouts[place]
    name = _clean_name(player.get("name"))

    paste_circular_avatar(
        base_image=base,
        avatar_source=player.get("avatar_path"),
        box=layout.avatar_box,
        fallback_text=name,
    )

    if place in (2, 3) and layout.prefix_center and layout.prefix_font_size and layout.prefix_color and layout.prefix_max_width:
        prefix = " ".join(str(player.get("prefix") or "").split())
        if prefix:
            selected_font = load_font(layout.prefix_font_size, weight="semibold", fonts_dir=fonts_dir)
            if layout.prefix_min_font_size is not None:
                for size in range(layout.prefix_font_size, layout.prefix_min_font_size - 1, -1):
                    candidate_font = load_font(size, weight="semibold", fonts_dir=fonts_dir)
                    if measure_text(draw, prefix, candidate_font) <= layout.prefix_max_width:
                        selected_font = candidate_font
                        break
            fitted_prefix = fit_text_to_width(draw, prefix, selected_font, layout.prefix_max_width)
            draw_centered_text(draw, layout.prefix_center, fitted_prefix, selected_font, layout.prefix_color)

    name_font = load_font(layout.name_font_size, weight="bold", fonts_dir=fonts_dir)
    fitted_name = fit_text_to_width(draw, name, name_font, layout.name_max_width)
    if fitted_name:
        draw.text(layout.name_xy, fitted_name, fill=layout.name_color, font=name_font, anchor="lm")

    money_text = format_money(player.get("money"))
    money_font = load_font(layout.money_font_size, weight="bold", fonts_dir=fonts_dir)
    draw_centered_text(draw, layout.money_center, money_text, money_font, layout.money_color)


def render_compact_player(
    draw: ImageDraw.ImageDraw,
    place: int,
    player: PlayerInput,
    fonts_dir: str | Path | None = None,
) -> None:
    """Render compact 4th/5th row with place number, name and amount."""

    layout = CONFIG.compact_layouts[place]
    name = _clean_name(player.get("name"))
    name_font = load_font(layout.name_font_size, weight="bold", fonts_dir=fonts_dir)
    fitted_name = fit_text_to_width(draw, name, name_font, layout.name_max_width)
    if fitted_name:
        draw.text(layout.name_xy, fitted_name, fill=layout.name_color, font=name_font, anchor="lm")

    money_text = format_money(player.get("money"))
    money_font = load_font(layout.money_font_size, weight="bold", fonts_dir=fonts_dir)
    draw_centered_text(draw, layout.money_center, money_text, money_font, layout.money_color)


def _safe_open_template(template_path: str | Path) -> Image.Image:
    path = Path(template_path)
    if not path.is_file():
        raise LeaderboardRenderError(f"Template PNG not found: {path}")
    try:
        template = Image.open(path)
    except OSError as exc:
        raise LeaderboardRenderError(f"Failed to open template PNG: {path}") from exc

    image = template.convert("RGBA")
    template.close()
    if image.size != CONFIG.image_size:
        raise LeaderboardRenderError(
            f"Invalid template size {image.size}, expected {CONFIG.image_size}"
        )
    return image



def _title_region_has_text(base: Image.Image) -> bool:
    """Return True when template already contains a visible top title."""

    region = base.crop((300, 170, 724, 370)).convert("L")
    histogram = region.histogram()
    bright_pixels = sum(histogram[170:])
    return bright_pixels > 1800


def render_header_title(
    base: Image.Image,
    draw: ImageDraw.ImageDraw,
    fonts_dir: str | Path | None = None,
) -> None:
    """Draw "ТОП ГЕРОЕВ" between laurels only when template does not have this text."""

    if _title_region_has_text(base):
        return
    title_font = load_font(62, weight="bold", fonts_dir=fonts_dir)
    draw_centered_text(draw, (512, 250), "ТОП ГЕРОЕВ", title_font, (245, 245, 245))


def render_leaderboard(
    players: list[PlayerInput],
    output_path: str | Path | None = None,
    *,
    template_path: str | Path = DEFAULT_TEMPLATE_PATH,
    fonts_dir: str | Path | None = None,
) -> Image.Image:
    """Render leaderboard image for up to five players and optionally save PNG to disk."""

    base = _safe_open_template(template_path)
    draw = ImageDraw.Draw(base)
    prepared_players = _normalize_players(players)

    render_header_title(base, draw, fonts_dir=fonts_dir)

    for place in (1, 2, 3):
        render_top_player(base, draw, place, prepared_players[place - 1], fonts_dir=fonts_dir)
    for place in (4, 5):
        render_compact_player(draw, place, prepared_players[place - 1], fonts_dir=fonts_dir)

    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        base.save(output, format="PNG")
    return base


def render_leaderboard_to_bytes(
    players: list[PlayerInput],
    *,
    template_path: str | Path = DEFAULT_TEMPLATE_PATH,
    fonts_dir: str | Path | None = None,
) -> BytesIO:
    """Render leaderboard and return PNG bytes (ready for Telegram send_photo)."""

    image = render_leaderboard(players, template_path=template_path, fonts_dir=fonts_dir)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


EXAMPLE_PLAYERS: list[PlayerInput] = [
    {
        "name": "Некий Лох",
        "prefix": "ЛЕГЕНДА",
        "money": 17737,
        "avatar_path": "path/to/avatar1.png",
    },
    {
        "name": "bro",
        "prefix": "AXAXAXAX",
        "money": 14837,
        "avatar_path": "path/to/avatar2.png",
    },
    {
        "name": "Alex Sholohov",
        "prefix": "ELITE",
        "money": 8288,
        "avatar_path": "path/to/avatar3.png",
    },
    {
        "name": "Неизвестный ге...",
        "money": 5473,
    },
    {
        "name": "Rgrxch",
        "money": 6473,
    },
]


def example_usage() -> None:
    """Minimal usage example for local generation."""

    render_leaderboard(
        EXAMPLE_PLAYERS,
        output_path="leaderboard_preview.png",
        template_path=DEFAULT_TEMPLATE_PATH,
    )
