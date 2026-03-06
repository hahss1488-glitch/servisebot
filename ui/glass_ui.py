from __future__ import annotations

import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

TOKENS = {
    "BG_TOP": "#06101C",
    "BG_MID": "#081426",
    "BG_BOTTOM": "#0B1830",
    "CYAN": "#56D7FF",
    "ELECTRIC_BLUE": "#4A7DFF",
    "VIOLET": "#8B6DFF",
    "MAGENTA": "#C86BFF",
    "AQUA": "#5CF2D6",
    "TEXT_PRIMARY": (247, 251, 255, 255),
    "TEXT_SECONDARY": (215, 229, 245, 255),
    "TEXT_MUTED": (142, 166, 194, 255),
    "POSITIVE": (99, 245, 198, 255),
    "NEGATIVE": (255, 115, 155, 255),
    "WARNING": (255, 200, 106, 255),
    "GLASS_FILL_LIGHT": (255, 255, 255, 31),
    "GLASS_FILL_MID": (255, 255, 255, 23),
    "GLASS_FILL_DARK": (255, 255, 255, 15),
    "GLASS_BORDER": (255, 255, 255, 51),
    "GLASS_BORDER_BRIGHT": (255, 255, 255, 71),
    "GLASS_TOP_HIGHLIGHT": (255, 255, 255, 61),
    "GLASS_INNER_HAZE": (255, 255, 255, 13),
}

MATERIALS = {
    "hero": {"fill": TOKENS["GLASS_FILL_LIGHT"], "border": TOKENS["GLASS_BORDER_BRIGHT"], "blur": 30, "shadow": 42},
    "primary": {"fill": TOKENS["GLASS_FILL_MID"], "border": TOKENS["GLASS_BORDER"], "blur": 24, "shadow": 34},
    "metric": {"fill": TOKENS["GLASS_FILL_DARK"], "border": (255, 255, 255, 43), "blur": 18, "shadow": 22},
    "pill": {"fill": (255, 255, 255, 24), "border": (255, 255, 255, 56), "blur": 14, "shadow": 14},
}

TYPE_STYLES = {
    "DISPLAY_TITLE": (72, True),
    "SCREEN_TITLE": (54, True),
    "SECTION_TITLE": (34, True),
    "KPI_XL": (84, True),
    "KPI_L": (64, True),
    "METRIC_VALUE": (44, True),
    "METRIC_LABEL": (24, False),
    "CHIP_TEXT": (21, True),
    "CAPTION": (20, False),
}

FONT_PATHS_BOLD = (
    "/usr/share/fonts/truetype/inter/Inter-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
FONT_PATHS_REGULAR = (
    "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)


@lru_cache(maxsize=128)
def get_font(size: int, bold: bool = False):
    paths = FONT_PATHS_BOLD if bold else FONT_PATHS_REGULAR
    for p in paths:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def get_type_font(token: str):
    size, bold = TYPE_STYLES.get(token, (24, False))
    return get_font(size, bold=bold)


@lru_cache(maxsize=128)
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
        delta = int(round((float(value) - 1.0) * 100))
    except Exception:
        return "—", TOKENS["TEXT_SECONDARY"]
    if delta > 0:
        return f"+{delta}%", TOKENS["POSITIVE"]
    if delta < 0:
        return f"−{abs(delta)}%", TOKENS["NEGATIVE"]
    return "0%", TOKENS["TEXT_SECONDARY"]


def create_aurora_background(width: int, height: int, seed: int = 42) -> Image.Image:
    image = Image.new("RGBA", (width, height), _hex_to_rgba(TOKENS["BG_TOP"]))
    draw = ImageDraw.Draw(image, "RGBA")
    top = _hex_to_rgba(TOKENS["BG_TOP"])
    mid = _hex_to_rgba(TOKENS["BG_MID"])
    bot = _hex_to_rgba(TOKENS["BG_BOTTOM"])
    for y in range(height):
        t = y / max(height - 1, 1)
        if t < 0.55:
            k = t / 0.55
            col = tuple(int(top[i] + (mid[i] - top[i]) * k) for i in range(3)) + (255,)
        else:
            k = (t - 0.55) / 0.45
            col = tuple(int(mid[i] + (bot[i] - mid[i]) * k) for i in range(3)) + (255,)
        draw.line((0, y, width, y), fill=col)

    rng = random.Random(seed)
    blob_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blob_layer, "RGBA")
    colors = [TOKENS["CYAN"], TOKENS["ELECTRIC_BLUE"], TOKENS["VIOLET"], TOKENS["MAGENTA"], TOKENS["AQUA"]]
    for _ in range(rng.randint(4, 5)):
        color = _hex_to_rgba(rng.choice(colors), rng.randint(40, 74))
        bw = rng.randint(width // 3, width)
        bh = rng.randint(height // 3, int(height * 0.85))
        x = rng.randint(-int(width * 0.25), int(width * 0.9))
        y = rng.randint(-int(height * 0.2), int(height * 0.85))
        bd.ellipse((x, y, x + bw, y + bh), fill=color)
    blob_layer = blob_layer.filter(ImageFilter.GaussianBlur(135))
    image.alpha_composite(blob_layer)
    apply_vignette(image, 0.31)
    add_noise_overlay(image, opacity=8, seed=seed + 99)
    return image


def apply_vignette(image: Image.Image, strength: float = 0.3) -> None:
    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((-w * 0.08, -h * 0.05, w * 1.08, h * 1.02), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(w, h) // 4))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, int(255 * strength)))
    image.paste(dark, (0, 0), ImageOps.invert(mask))


def add_noise_overlay(image: Image.Image, opacity: int = 8, seed: int = 1) -> None:
    rng = random.Random(seed)
    w, h = image.size
    noise = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = noise.load()
    for y in range(h):
        for x in range(w):
            v = rng.randint(0, opacity)
            px[x, y] = (255, 255, 255, v)
    image.alpha_composite(noise)


def draw_glow(image: Image.Image, bbox: tuple[int, int, int, int], color: tuple[int, int, int, int], blur: int = 24, expand: int = 14):
    x1, y1, x2, y2 = bbox
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    d.rounded_rectangle((x1 - expand, y1 - expand, x2 + expand, y2 + expand), radius=34, fill=color)
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def draw_soft_reflection(target: Image.Image, radius: int = 6):
    w, h = target.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    for y in range(max(12, h // 3)):
        a = int(40 * (1 - y / max(h // 3, 1)))
        d.line((10, y + 8, w - 10, y + 8), fill=(255, 255, 255, a))
    target.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius)))


def draw_glass_card(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], radius: int, material_level: str = "primary", glow_color=None, glow_strength: int = 0, blur_radius: int | None = None, border_bright: bool = False):
    x1, y1, x2, y2 = bbox
    w, h = max(1, x2 - x1), max(1, y2 - y1)
    m = MATERIALS.get(material_level, MATERIALS["primary"])
    br = blur_radius if blur_radius is not None else m["blur"]

    backdrop = background.crop((x1, y1, x2, y2)).filter(ImageFilter.GaussianBlur(br))
    mask = rounded_mask((w, h), radius)
    canvas.paste(backdrop, (x1, y1), mask)

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle((x1 + 2, y1 + 8, x2 + 2, y2 + 14), radius=radius, fill=(0, 0, 0, m["shadow"]))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16)))

    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card, "RGBA")
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=m["fill"])
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, outline=(TOKENS["GLASS_BORDER_BRIGHT"] if border_bright else m["border"]), width=2)
    d.rounded_rectangle((3, 3, w - 4, max(10, h // 2)), radius=max(8, radius - 8), outline=TOKENS["GLASS_TOP_HIGHLIGHT"], width=1)
    d.rounded_rectangle((4, h // 2, w - 5, h - 5), radius=max(8, radius - 10), fill=TOKENS["GLASS_INNER_HAZE"])
    draw_soft_reflection(card)
    canvas.alpha_composite(card, (x1, y1))

    if glow_color and glow_strength > 0:
        draw_glow(canvas, bbox, (glow_color[0], glow_color[1], glow_color[2], glow_strength), blur=24, expand=12)


def draw_glass_pill(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], text: str, font, text_color, tint: tuple[int, int, int, int] | None = None):
    draw_glass_card(canvas, background, bbox, radius=(bbox[3] - bbox[1]) // 2, material_level="pill")
    x1, y1, x2, y2 = bbox
    if tint:
        overlay = Image.new("RGBA", (x2 - x1, y2 - y1), tint)
        canvas.alpha_composite(overlay, (x1, y1))
    d = ImageDraw.Draw(canvas, "RGBA")
    b = d.textbbox((0, 0), text, font=font)
    d.text((x1 + ((x2 - x1) - (b[2] - b[0])) / 2, y1 + ((y2 - y1) - (b[3] - b[1])) / 2 - 1), text, fill=text_color, font=font)


def draw_rank_badge(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], rank: int):
    rank_text = f"#{rank}"
    tint = (255, 210, 130, 24) if rank == 1 else None
    draw_glass_pill(canvas, background, bbox, rank_text, get_type_font("CHIP_TEXT"), TOKENS["TEXT_PRIMARY"], tint=tint)


def draw_progress_bar(canvas: Image.Image, bbox: tuple[int, int, int, int], progress: float | None):
    x1, y1, x2, y2 = bbox
    h = y2 - y1
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rounded_rectangle(bbox, radius=h // 2, fill=(255, 255, 255, 22), outline=(255, 255, 255, 43), width=1)
    d.rounded_rectangle((x1 + 2, y1 + 2, x2 - 2, y1 + max(4, h // 2)), radius=h // 2, fill=(255, 255, 255, 30))
    if progress is None:
        return
    p = max(0.0, min(1.0, float(progress)))
    fw = max(10, int((x2 - x1 - 4) * p))
    fill = Image.new("RGBA", (fw, h - 4), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill, "RGBA")
    c1 = _hex_to_rgba(TOKENS["CYAN"], 240)
    c2 = _hex_to_rgba(TOKENS["ELECTRIC_BLUE"], 240)
    c3 = _hex_to_rgba(TOKENS["VIOLET"], 240)
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
    gd.rounded_rectangle((x1 + 1, y1 + 1, x1 + fw + 3, y2 + 1), radius=h // 2, fill=(86, 215, 255, 72))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(8)))


def draw_metric_box(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], title: str, value: str, value_color=None):
    draw_glass_card(canvas, background, bbox, radius=26, material_level="metric")
    x1, y1, _, _ = bbox
    d = ImageDraw.Draw(canvas, "RGBA")
    d.text((x1 + 24, y1 + 18), title, fill=TOKENS["TEXT_MUTED"], font=get_type_font("METRIC_LABEL"))
    d.text((x1 + 24, y1 + 58), value or "—", fill=value_color or TOKENS["TEXT_PRIMARY"], font=get_type_font("METRIC_VALUE"))


def draw_avatar_circle(canvas: Image.Image, bbox: tuple[int, int, int, int], avatar: Image.Image | None, name: str, border_color=(220, 235, 255, 225)):
    x1, y1, x2, y2 = bbox
    size = min(x2 - x1, y2 - y1)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    if avatar is None:
        av = Image.new("RGBA", (size, size), (26, 40, 66, 255))
        ad = ImageDraw.Draw(av, "RGBA")
        for y in range(size):
            t = y / max(size - 1, 1)
            r = int(40 + 70 * t)
            g = int(78 + 90 * t)
            b = int(110 + 120 * t)
            ad.line((0, y, size, y), fill=(r, g, b, 210))
        initials = "".join([part[:1] for part in (name or "?").split()[:2]]).upper() or "?"
        f = get_font(max(24, size // 3), bold=True)
        bb = ad.textbbox((0, 0), initials, font=f)
        ad.text(((size - (bb[2] - bb[0])) / 2, (size - (bb[3] - bb[1])) / 2 - 1), initials, fill=TOKENS["TEXT_PRIMARY"], font=f)
    else:
        av = ImageOps.fit(avatar.convert("RGBA"), (size, size), method=Image.Resampling.LANCZOS)
    canvas.paste(av, (x1, y1), mask)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.ellipse((x1 - 2, y1 - 2, x1 + size + 2, y1 + size + 2), outline=border_color, width=3)
    draw_glow(canvas, (x1 - 6, y1 - 6, x1 + size + 6, y1 + size + 6), (96, 187, 255, 42), blur=12, expand=2)


def draw_summary_footer(canvas: Image.Image, background: Image.Image, bbox: tuple[int, int, int, int], items: list[str]):
    draw_glass_card(canvas, background, bbox, radius=22, material_level="metric")
    d = ImageDraw.Draw(canvas, "RGBA")
    x1, y1, x2, _ = bbox
    gap = (x2 - x1) // max(1, len(items))
    for i, item in enumerate(items):
        tx = x1 + i * gap + 20
        d.text((tx, y1 + 14), item, fill=TOKENS["TEXT_SECONDARY"], font=get_type_font("CAPTION"))


def draw_divider_glow(canvas: Image.Image, x1: int, x2: int, y: int):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    d.line((x1, y, x2, y), fill=(140, 220, 255, 170), width=2)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(4)))
