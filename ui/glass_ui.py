from __future__ import annotations

import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

TOKENS = {
    "BG_BASE": "#07111F",
    "BG_DEEP": "#030A14",
    "BG_BLUE": "#0A1E33",
    "BG_VIOLET_HINT": "#10192B",
    "GLASS_FILL_PRIMARY": (190, 220, 255, 31),
    "GLASS_FILL_SECONDARY": (150, 200, 255, 20),
    "GLASS_FILL_DARK": (20, 30, 50, 71),
    "GLASS_BORDER": (220, 240, 255, 56),
    "GLASS_BORDER_SOFT": (255, 255, 255, 26),
    "INNER_HIGHLIGHT": (255, 255, 255, 46),
    "INNER_HIGHLIGHT_TOP": (255, 255, 255, 51),
    "TEXT_PRIMARY": (244, 248, 255, 255),
    "TEXT_SECONDARY": (198, 212, 231, 255),
    "TEXT_MUTED": (143, 165, 191, 255),
    "TEXT_DIM": (111, 132, 156, 255),
    "ACCENT_CYAN": "#69E6FF",
    "ACCENT_SKY": "#59B8FF",
    "ACCENT_BLUE": "#6A7CFF",
    "ACCENT_VIOLET": "#8B7CFF",
    "ACCENT_MINT": "#63F5D2",
    "ACCENT_GREEN": "#66F08B",
    "ACCENT_PINK": "#FF6FB5",
    "ACCENT_GOLD": "#FFD76A",
    "POSITIVE": (99, 245, 210, 255),
    "NEGATIVE": (255, 126, 157, 255),
    "NEUTRAL": (217, 230, 245, 255),
}

TYPE_STYLES = {
    "DISPLAY_TITLE": (56, True),
    "SCREEN_TITLE": (56, True),
    "SECTION_TITLE": (34, True),
    "KPI_XL": (86, True),
    "KPI_L": (64, True),
    "METRIC_VALUE": (42, True),
    "METRIC_LABEL": (24, False),
    "CHIP_TEXT": (21, True),
    "CAPTION": (20, False),
}

FONT_PATHS_BOLD = (
    "/usr/share/fonts/truetype/inter/Inter-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
FONT_PATHS_REGULAR = (
    "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


@lru_cache(maxsize=256)
def get_font(size: int, bold: bool = False):
    paths = FONT_PATHS_BOLD if bold else FONT_PATHS_REGULAR
    for p in paths:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def get_type_font(token: str):
    size, bold = TYPE_STYLES.get(token, (22, False))
    return get_font(size, bold=bold)


@lru_cache(maxsize=256)
def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    w, h = size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=max(2, radius), fill=255)
    return mask


def _hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = value.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha


def fit_text_to_width(text: str, font_path: str | None, start_size: int, min_size: int, max_width: int, ellipsis: bool = True, bold: bool = False):
    value = (text or "—").strip() or "—"
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8), (0, 0, 0, 0)), "RGBA")
    for size in range(start_size, min_size - 1, -1):
        font = get_font(size, bold=bold)
        if probe.textbbox((0, 0), value, font=font)[2] <= max_width:
            return value, font
    font = get_font(min_size, bold=bold)
    if not ellipsis:
        return value, font
    for i in range(len(value), 0, -1):
        candidate = f"{value[:i].rstrip()}…"
        if probe.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            return candidate, font
    return "…", font


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
        amount = int(round(float(value)))
    except Exception:
        return "—"
    return f"{amount:,}".replace(",", " ") + " ₽"


def format_percent(value: float | int | None) -> str:
    if value is None:
        return "—"
    try:
        return f"{int(round(float(value) * 100))}%"
    except Exception:
        return "—"


def format_runrate(value: float | int | None) -> tuple[str, tuple[int, int, int, int]]:
    if value is None:
        return "—", TOKENS["TEXT_SECONDARY"]
    try:
        pace = int(round(float(value) * 100))
    except Exception:
        return "—", TOKENS["TEXT_SECONDARY"]
    if pace > 100:
        return f"{pace}%", TOKENS["POSITIVE"]
    if pace < 100:
        return f"{pace}%", TOKENS["NEGATIVE"]
    return f"{pace}%", TOKENS["NEUTRAL"]


def create_aurora_background(width: int, height: int, seed: int = 42) -> Image.Image:
    image = Image.new("RGBA", (width, height), _hex_to_rgba(TOKENS["BG_BASE"]))
    draw = ImageDraw.Draw(image, "RGBA")
    top = _hex_to_rgba(TOKENS["BG_DEEP"])
    bot = _hex_to_rgba(TOKENS["BG_BLUE"])
    for y in range(height):
        t = y / max(height - 1, 1)
        col = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        draw.line((0, y, width, y), fill=col)

    rng = random.Random(seed)
    blobs = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blobs, "RGBA")
    glow_data = [
        ("#49D8FF", 32, (-220, -180, 760, 520)),
        ("#7A6CFF", 26, (300, -130, 1320, 500)),
        ("#45F1C8", 20, (-180, 420, 860, 1080)),
        ("#2D7FFF", 16, (860, 390, 1800, 1120)),
    ]
    for hex_color, alpha, box in glow_data:
        jitter = rng.randint(-20, 20)
        x1, y1, x2, y2 = box
        bd.ellipse((x1 + jitter, y1, x2 + jitter, y2), fill=_hex_to_rgba(hex_color, alpha))
    image.alpha_composite(blobs.filter(ImageFilter.GaussianBlur(120)))
    apply_vignette(image, 0.32)
    add_noise_overlay(image, opacity=5, seed=seed + 17)
    return image


def apply_vignette(image: Image.Image, strength: float = 0.3) -> None:
    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((-w * 0.05, -h * 0.05, w * 1.05, h * 1.03), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(w, h) // 3))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, int(255 * strength)))
    image.paste(dark, (0, 0), ImageOps.invert(mask))


def add_noise_overlay(image: Image.Image, opacity: int = 6, seed: int = 1) -> None:
    rng = random.Random(seed)
    w, h = image.size
    noise = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = noise.load()
    for y in range(h):
        for x in range(w):
            v = rng.randint(0, opacity)
            px[x, y] = (255, 255, 255, v)
    image.alpha_composite(noise)


def draw_glow(image: Image.Image, bbox: tuple[int, int, int, int], color: tuple[int, int, int, int], blur: int = 26, expand: int = 16):
    x1, y1, x2, y2 = bbox
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    d.rounded_rectangle((x1 - expand, y1 - expand, x2 + expand, y2 + expand), radius=34, fill=color)
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def _panel_backdrop(background: Image.Image, box: tuple[int, int, int, int], blur_radius: int) -> Image.Image:
    crop = background.crop(box).filter(ImageFilter.GaussianBlur(blur_radius))
    crop = ImageEnhance.Brightness(crop).enhance(1.07)
    crop = ImageEnhance.Color(crop).enhance(0.84)
    return crop


def draw_glass_card(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], radius: int, material_level: str = "primary", glow_color=None, glow_strength: int = 0, blur_radius: int | None = None, border_bright: bool = False):
    x1, y1, x2, y2 = bbox
    w, h = max(1, x2 - x1), max(1, y2 - y1)
    blur = blur_radius if blur_radius is not None else (22 if material_level != "metric" else 14)

    mask = rounded_mask((w, h), radius)
    panel_backdrop = _panel_backdrop(background, bbox, blur)
    canvas.paste(panel_backdrop, (x1, y1), mask)

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle((x1 + 2, y1 + 8, x2 + 2, y2 + 14), radius=radius, fill=(0, 0, 0, 72 if material_level == "hero" else 56))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16)))

    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card, "RGBA")
    fill = TOKENS["GLASS_FILL_PRIMARY"] if material_level in {"hero", "primary"} else TOKENS["GLASS_FILL_SECONDARY"]
    if material_level == "metric":
        fill = TOKENS["GLASS_FILL_DARK"]
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=fill)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, outline=TOKENS["GLASS_BORDER"] if border_bright else TOKENS["GLASS_BORDER_SOFT"], width=2)
    d.rounded_rectangle((4, 4, w - 5, max(18, h // 2)), radius=max(8, radius - 8), outline=TOKENS["INNER_HIGHLIGHT_TOP"], width=1)
    d.rounded_rectangle((8, h // 2, w - 9, h - 9), radius=max(8, radius - 12), fill=(15, 28, 45, 34))
    canvas.alpha_composite(card, (x1, y1))

    if glow_color and glow_strength > 0:
        draw_glow(canvas, bbox, (glow_color[0], glow_color[1], glow_color[2], glow_strength), blur=30, expand=14)


def draw_glass_pill(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], text: str, font, text_color, tint: tuple[int, int, int, int] | None = None):
    radius = (bbox[3] - bbox[1]) // 2
    draw_glass_card(canvas, background, bbox, radius=radius, material_level="metric", blur_radius=10)
    x1, y1, x2, y2 = bbox
    if tint:
        overlay = Image.new("RGBA", (x2 - x1, y2 - y1), tint)
        canvas.alpha_composite(overlay, (x1, y1))
    d = ImageDraw.Draw(canvas, "RGBA")
    safe_text = truncate_text_to_width(d, text, font, (x2 - x1) - 18)
    b = d.textbbox((0, 0), safe_text, font=font)
    d.text((x1 + ((x2 - x1) - (b[2] - b[0])) / 2, y1 + ((y2 - y1) - (b[3] - b[1])) / 2 - 1), safe_text, fill=text_color, font=font)


def draw_rank_badge(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], rank: int):
    tint = (255, 215, 106, 26) if rank == 1 else (105, 184, 255, 18)
    draw_glass_pill(canvas, background, bbox, f"#{rank}", get_type_font("CHIP_TEXT"), TOKENS["TEXT_PRIMARY"], tint=tint)


def draw_progress_bar(canvas: Image.Image, bbox: tuple[int, int, int, int], progress: float | None):
    x1, y1, x2, y2 = bbox
    h = y2 - y1
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rounded_rectangle(bbox, radius=h // 2, fill=(255, 255, 255, 22), outline=(255, 255, 255, 34), width=1)
    d.rounded_rectangle((x1 + 2, y1 + 2, x2 - 2, y1 + max(5, h // 2)), radius=h // 2, fill=(255, 255, 255, 20))
    if progress is None:
        return
    p = max(0.0, min(1.0, float(progress)))
    fw = max(8, int((x2 - x1 - 4) * p))
    fill = Image.new("RGBA", (fw, h - 4), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill, "RGBA")
    c1 = _hex_to_rgba(TOKENS["ACCENT_CYAN"], 238)
    c2 = _hex_to_rgba(TOKENS["ACCENT_SKY"], 238)
    c3 = _hex_to_rgba(TOKENS["ACCENT_VIOLET"], 238)
    for i in range(fw):
        t = i / max(fw - 1, 1)
        if t < 0.55:
            k = t / 0.55
            col = tuple(int(c1[j] + (c2[j] - c1[j]) * k) for j in range(4))
        else:
            k = (t - 0.55) / 0.45
            col = tuple(int(c2[j] + (c3[j] - c2[j]) * k) for j in range(4))
        fd.line((i, 0, i, h - 4), fill=col)
    canvas.paste(fill, (x1 + 2, y1 + 2), rounded_mask((fw, h - 4), (h - 4) // 2))
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.rounded_rectangle((x1 + 2, y1 + 2, x1 + fw + 4, y2 - 2), radius=h // 2, fill=(105, 230, 255, 54))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(9)))


def draw_metric_box(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], title: str, value: str, value_color=None):
    draw_glass_card(canvas, background, bbox, radius=22, material_level="metric")
    d = ImageDraw.Draw(canvas, "RGBA")
    x1, y1, x2, _ = bbox
    label, label_font = fit_text_to_width(title, None, 25, 17, x2 - x1 - 28, ellipsis=True)
    val, val_font = fit_text_to_width(value, None, 38, 22, x2 - x1 - 28, ellipsis=True, bold=True)
    d.text((x1 + 14, y1 + 14), label, fill=TOKENS["TEXT_MUTED"], font=label_font)
    d.text((x1 + 14, y1 + 52), val, fill=value_color or TOKENS["TEXT_PRIMARY"], font=val_font)


def draw_avatar_circle(canvas: Image.Image, bbox: tuple[int, int, int, int], avatar: Image.Image | None, name: str, border_color=(220, 235, 255, 215)):
    x1, y1, x2, y2 = bbox
    size = min(x2 - x1, y2 - y1)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    if avatar is None:
        av = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ad = ImageDraw.Draw(av, "RGBA")
        c1 = _hex_to_rgba(TOKENS["ACCENT_SKY"], 220)
        c2 = _hex_to_rgba(TOKENS["ACCENT_VIOLET"], 220)
        for y in range(size):
            t = y / max(size - 1, 1)
            col = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(4))
            ad.line((0, y, size, y), fill=col)
        initials = "".join(part[:1] for part in (name or "?").split()[:2]).upper() or "?"
        f = get_font(max(24, size // 3), bold=True)
        bb = ad.textbbox((0, 0), initials, font=f)
        ad.text(((size - (bb[2] - bb[0])) / 2, (size - (bb[3] - bb[1])) / 2 - 1), initials, fill=TOKENS["TEXT_PRIMARY"], font=f)
    else:
        av = ImageOps.fit(avatar.convert("RGBA"), (size, size), method=Image.Resampling.LANCZOS)
    canvas.paste(av, (x1, y1), mask)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.ellipse((x1 - 2, y1 - 2, x1 + size + 2, y1 + size + 2), outline=border_color, width=2)
    draw_glow(canvas, (x1 - 6, y1 - 6, x1 + size + 6, y1 + size + 6), (98, 206, 255, 35), blur=10, expand=2)


def draw_summary_footer(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], items: list[str]):
    draw_glass_card(canvas, background, bbox, radius=22, material_level="metric")
    d = ImageDraw.Draw(canvas, "RGBA")
    x1, y1, x2, _ = bbox
    count = max(1, len(items))
    part_w = (x2 - x1) / count
    for i, item in enumerate(items):
        txt, font = fit_text_to_width(item, None, 24, 16, int(part_w) - 24, ellipsis=True)
        d.text((x1 + i * part_w + 12, y1 + 15), txt, fill=TOKENS["TEXT_SECONDARY"], font=font)


def draw_divider_glow(canvas: Image.Image, x1: int, x2: int, y: int):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    d.line((x1, y, x2, y), fill=(130, 212, 255, 130), width=2)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(4)))
