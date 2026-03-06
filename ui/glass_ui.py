from __future__ import annotations

import random
from functools import lru_cache
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

TOKENS = {
    "BG_0": "#08111F",
    "BG_1": "#0B1630",
    "BG_2": "#050A12",
    "AURORA_CYAN": "#38D6FF",
    "AURORA_BLUE": "#3C7DFF",
    "AURORA_VIOLET": "#7A5CFF",
    "AURORA_MAGENTA": "#FF4FD8",
    "TEXT_PRIMARY": (243, 250, 255, 255),
    "TEXT_SECONDARY": (226, 239, 255, 174),
    "TEXT_DIM": (226, 239, 255, 122),
    "POSITIVE": (107, 255, 176, 255),
    "NEGATIVE": (255, 123, 158, 255),
    "WARNING": (255, 201, 107, 255),
    "GLASS_FILL_LIGHT": (255, 255, 255, 26),
    "GLASS_FILL_MID": (210, 230, 255, 20),
    "GLASS_BORDER": (255, 255, 255, 46),
    "GLASS_BORDER_BRIGHT": (255, 255, 255, 70),
    "GLASS_INNER_HIGHLIGHT": (255, 255, 255, 26),
}

FONT_PATHS_BOLD = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
FONT_PATHS_REGULAR = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)


@lru_cache(maxsize=128)
def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = FONT_PATHS_BOLD if bold else FONT_PATHS_REGULAR
    for p in paths:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


@lru_cache(maxsize=64)
def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    w, h = size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    return mask


def _hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = value.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha


def truncate_text_to_width(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    value = (text or "—").strip() or "—"
    if draw.textbbox((0, 0), value, font=font)[2] <= max_w:
        return value
    for i in range(len(value), 0, -1):
        candidate = f"{value[:i].rstrip()}…"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_w:
            return candidate
    return "…"


def format_money(value: int | float | None) -> str:
    if value is None:
        return "—"
    try:
        amount = int(value)
    except Exception:
        return "—"
    return f"{amount:,}".replace(",", "\u202f") + " ₽"


def format_runrate(value: float | int | None) -> tuple[str, tuple[int, int, int, int]]:
    if value is None:
        return "—", TOKENS["TEXT_SECONDARY"]
    try:
        delta = int(round((float(value) - 1.0) * 100))
    except Exception:
        return "—", TOKENS["TEXT_SECONDARY"]
    if delta > 0:
        return f"+{delta}%", TOKENS["POSITIVE"]
    if delta < 0:
        return f"−{abs(delta)}%", TOKENS["NEGATIVE"]
    return "0%", TOKENS["TEXT_SECONDARY"]


def create_aurora_background(width: int, height: int, seed: int = 42) -> Image.Image:
    image = Image.new("RGBA", (width, height), _hex_to_rgba(TOKENS["BG_0"]))
    draw = ImageDraw.Draw(image, "RGBA")
    top = _hex_to_rgba(TOKENS["BG_1"])
    bottom = _hex_to_rgba(TOKENS["BG_2"])
    for y in range(height):
        t = y / max(height - 1, 1)
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        draw.line((0, y, width, y), fill=col)

    rng = random.Random(seed)
    blob_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blob_layer, "RGBA")
    colors = [TOKENS["AURORA_CYAN"], TOKENS["AURORA_BLUE"], TOKENS["AURORA_VIOLET"], TOKENS["AURORA_MAGENTA"]]
    for _ in range(6):
        color = _hex_to_rgba(rng.choice(colors), rng.randint(34, 62))
        w = rng.randint(width // 4, width // 2)
        h = rng.randint(height // 4, height // 2)
        x = rng.randint(-200, width - 100)
        y = rng.randint(-120, height - 100)
        bd.ellipse((x, y, x + w, y + h), fill=color)
    blob_layer = blob_layer.filter(ImageFilter.GaussianBlur(120))
    image.alpha_composite(blob_layer)
    apply_vignette(image, 0.42)
    add_noise_overlay(image, 16, seed=seed + 99)
    return image


def apply_vignette(image: Image.Image, strength: float = 0.35) -> None:
    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((-w * 0.2, -h * 0.15, w * 1.2, h * 1.15), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(w, h) // 5))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, int(255 * strength)))
    image.paste(dark, (0, 0), ImageOps.invert(mask))


def add_noise_overlay(image: Image.Image, opacity: int = 16, seed: int = 1) -> None:
    rng = random.Random(seed)
    w, h = image.size
    noise = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = noise.load()
    for y in range(h):
        for x in range(w):
            v = rng.randint(0, opacity)
            px[x, y] = (255, 255, 255, v)
    image.alpha_composite(noise)


def draw_glow(image: Image.Image, bbox: tuple[int, int, int, int], color: tuple[int, int, int, int], blur: int = 26, expand: int = 12) -> None:
    x1, y1, x2, y2 = bbox
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    d.rounded_rectangle((x1 - expand, y1 - expand, x2 + expand, y2 + expand), radius=28, fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    image.alpha_composite(layer)


def draw_glass_card(
    canvas: Image.Image,
    background: Image.Image,
    bbox: tuple[int, int, int, int],
    radius: int,
    blur_radius: int = 20,
    border_bright: bool = False,
    glow_color: tuple[int, int, int, int] | None = None,
) -> None:
    x1, y1, x2, y2 = bbox
    w = max(1, x2 - x1)
    h = max(1, y2 - y1)
    backdrop = background.crop((x1, y1, x2, y2)).filter(ImageFilter.GaussianBlur(blur_radius))
    mask = rounded_mask((w, h), radius)
    canvas.paste(backdrop, (x1, y1), mask)

    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card, "RGBA")
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=TOKENS["GLASS_FILL_LIGHT"])

    veil = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(veil, "RGBA")
    for y in range(h // 2):
        a = int(34 * (1 - (y / max(h // 2, 1))))
        vd.line((8, y + 8, w - 8, y + 8), fill=(255, 255, 255, a))
    veil = veil.filter(ImageFilter.GaussianBlur(4))
    card.alpha_composite(veil)

    border = TOKENS["GLASS_BORDER_BRIGHT"] if border_bright else TOKENS["GLASS_BORDER"]
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, outline=border, width=2)
    d.rounded_rectangle((3, 3, w - 4, max(8, h // 2)), radius=max(8, radius - 8), outline=TOKENS["GLASS_INNER_HIGHLIGHT"], width=1)

    canvas.alpha_composite(card, (x1, y1))
    if glow_color:
        draw_glow(canvas, bbox, glow_color)


def draw_glass_pill(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], text: str, font, text_color):
    draw_glass_card(canvas, background, bbox, radius=(bbox[3] - bbox[1]) // 2, blur_radius=16)
    d = ImageDraw.Draw(canvas, "RGBA")
    b = d.textbbox((0, 0), text, font=font)
    x1, y1, x2, y2 = bbox
    d.text((x1 + (x2 - x1 - (b[2] - b[0])) / 2, y1 + (y2 - y1 - (b[3] - b[1])) / 2 - 2), text, fill=text_color, font=font)


def draw_progress_bar(canvas: Image.Image, bbox: tuple[int, int, int, int], progress: float | None):
    x1, y1, x2, y2 = bbox
    w = x2 - x1
    h = y2 - y1
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rounded_rectangle(bbox, radius=h // 2, fill=(40, 58, 88, 140), outline=(255, 255, 255, 35), width=1)
    d.rounded_rectangle((x1 + 2, y1 + 2, x2 - 2, y1 + h // 2), radius=h // 2, fill=(255, 255, 255, 22))
    if progress is None:
        return
    p = max(0.0, min(1.0, progress))
    fw = max(8, int((w - 4) * p))
    fill = Image.new("RGBA", (fw, h - 4), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill, "RGBA")
    c1 = _hex_to_rgba(TOKENS["AURORA_CYAN"], 230)
    c2 = _hex_to_rgba(TOKENS["AURORA_VIOLET"], 230)
    for i in range(fw):
        t = i / max(fw - 1, 1)
        col = tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(4))
        fd.line((i, 0, i, h - 4), fill=col)
    fmask = rounded_mask((fw, h - 4), (h - 4) // 2)
    canvas.paste(fill, (x1 + 2, y1 + 2), fmask)
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.rounded_rectangle((x1 + 2, y1 + 1, x1 + 2 + fw, y2 + 1), radius=h // 2, fill=(80, 210, 255, 72))
    glow = glow.filter(ImageFilter.GaussianBlur(8))
    canvas.alpha_composite(glow)


def draw_metric_box(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], title: str, value: str, value_color=None):
    draw_glass_card(canvas, background, bbox, radius=22, blur_radius=16)
    x1, y1, x2, y2 = bbox
    d = ImageDraw.Draw(canvas, "RGBA")
    d.text((x1 + 20, y1 + 18), title, fill=TOKENS["TEXT_DIM"], font=get_font(28, bold=False))
    d.text((x1 + 20, y1 + (y2 - y1) // 2), value or "—", fill=value_color or TOKENS["TEXT_PRIMARY"], font=get_font(40, bold=True))


def draw_avatar_circle(canvas: Image.Image, bbox: tuple[int, int, int, int], avatar: Image.Image | None, name: str, border_color=(210, 230, 255, 220)):
    x1, y1, x2, y2 = bbox
    size = min(x2 - x1, y2 - y1)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    if avatar is None:
        av = Image.new("RGBA", (size, size), (40, 64, 96, 255))
        d = ImageDraw.Draw(av, "RGBA")
        for y in range(size):
            a = int(80 * (y / max(size - 1, 1)))
            d.line((0, y, size, y), fill=(90, 130, 190, 90 + a))
        initials = "".join([p[:1] for p in (name or "?").split()[:2]]).upper() or "?"
        f = get_font(max(24, size // 3), bold=True)
        bb = d.textbbox((0, 0), initials, font=f)
        d.text(((size - (bb[2] - bb[0])) / 2, (size - (bb[3] - bb[1])) / 2 - 2), initials, fill=TOKENS["TEXT_PRIMARY"], font=f)
    else:
        av = ImageOps.fit(avatar.convert("RGBA"), (size, size), method=Image.Resampling.LANCZOS)
    canvas.paste(av, (x1, y1), mask)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.ellipse((x1 - 2, y1 - 2, x1 + size + 2, y1 + size + 2), outline=border_color, width=3)


def draw_divider_glow(canvas: Image.Image, x1: int, x2: int, y: int):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    d.line((x1, y, x2, y), fill=(130, 210, 255, 170), width=2)
    layer = layer.filter(ImageFilter.GaussianBlur(4))
    canvas.alpha_composite(layer)
