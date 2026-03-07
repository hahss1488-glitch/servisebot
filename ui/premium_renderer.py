from __future__ import annotations

from datetime import datetime
from io import BytesIO
from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 1600, 900
SS = 2

TOKENS = {
    "BG_BASE": "#081423",
    "BG_DEEP": "#04101D",
    "BG_MID": "#0C2238",
    "BG_VIOLET": "#1A1F44",
    "GLASS_FILL_MAIN": (220, 235, 255, 41),
    "GLASS_FILL_LIGHT": (235, 245, 255, 51),
    "GLASS_FILL_SOFT": (190, 220, 255, 25),
    "GLASS_FILL_DARK": (30, 40, 70, 46),
    "GLASS_BORDER_MAIN": (255, 255, 255, 56),
    "GLASS_BORDER_SOFT": (255, 255, 255, 30),
    "GLASS_TOP_HIGHLIGHT": (255, 255, 255, 66),
    "GLASS_EDGE_GLOW": (180, 220, 255, 46),
    "TEXT_PRIMARY": (247, 251, 255, 255),
    "TEXT_SECONDARY": (214, 228, 245, 255),
    "TEXT_MUTED": (175, 195, 217, 255),
    "TEXT_DARK_ON_LIGHT": (27, 36, 48, 255),
    "POSITIVE": (99, 245, 210, 255),
    "NEGATIVE": (255, 141, 168, 255),
    "WARNING": (255, 211, 107, 255),
}


def _hex(v: str, a: int = 255):
    v = v.lstrip("#")
    return (int(v[:2], 16), int(v[2:4], 16), int(v[4:6], 16), a)


FONT_PATHS = {
    "bold": ["/usr/share/fonts/truetype/inter/Inter-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "semibold": ["/usr/share/fonts/truetype/inter/Inter-SemiBold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "medium": ["/usr/share/fonts/truetype/inter/Inter-Medium.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "regular": ["/usr/share/fonts/truetype/inter/Inter-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


@lru_cache(maxsize=512)
def font(size: int, weight: str = "regular"):
    for p in FONT_PATHS.get(weight, FONT_PATHS["regular"]):
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


@lru_cache(maxsize=256)
def rounded_mask(size: tuple[int, int], radius: int):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return m


def measure(draw: ImageDraw.ImageDraw, text: str, f):
    b = draw.textbbox((0, 0), text, font=f)
    return b[2] - b[0], b[3] - b[1]


def fit_text_to_width(text: str, start_size: int, min_size: int, max_width: int, weight: str = "regular", ellipsis: bool = True):
    text = (text or "—").strip() or "—"
    d = ImageDraw.Draw(Image.new("RGBA", (16, 16), (0, 0, 0, 0)), "RGBA")
    for s in range(start_size, min_size - 1, -1):
        f = font(s, weight)
        if measure(d, text, f)[0] <= max_width:
            return text, f
    f = font(min_size, weight)
    if not ellipsis:
        return text, f
    for i in range(len(text), 0, -1):
        t = text[:i].rstrip() + "…"
        if measure(d, t, f)[0] <= max_width:
            return t, f
    return "…", f


def _safe_i(v, d=0):
    try:
        return int(v)
    except Exception:
        return d


def format_money(v: Any) -> str:
    try:
        return f"{int(round(float(v))):,}".replace(",", " ") + " ₽"
    except Exception:
        return "—"


def format_update_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y в %H:%M")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime("%d.%m.%Y в %H:%M")
        except Exception:
            pass
    return datetime.now().strftime("%d.%m.%Y в %H:%M")


def format_tempo(value: Any) -> tuple[str, tuple[int, int, int, int]]:
    if value is None or value == "":
        return "—", TOKENS["TEXT_SECONDARY"]
    try:
        v = float(value)
        pct = int(round(v * 100)) if v <= 3.0 else int(round(v))
    except Exception:
        t = str(value).strip().replace("%", "")
        if not t:
            return "—", TOKENS["TEXT_SECONDARY"]
        try:
            pct = int(float(t))
        except Exception:
            return "—", TOKENS["TEXT_SECONDARY"]
    pct = max(0, min(250, pct))
    if pct >= 102:
        c = TOKENS["POSITIVE"]
    elif pct <= 97:
        c = TOKENS["NEGATIVE"]
    else:
        c = TOKENS["TEXT_SECONDARY"]
    return f"{pct}%", c


THEME = {
    "BG_1": "#08111F",
    "BG_2": "#0B1424",
    "BG_3": "#101A2C",
    "BG_4": "#172235",
    "TEXT_PRIMARY": _hex("#F4F8FF"),
    "TEXT_SECONDARY": _hex("#B8C4DA"),
    "TEXT_MUTED": _hex("#8D99B4"),
    "GLASS_FILL_MAIN": (22, 30, 50, 173),
    "GLASS_FILL_SOFT": (24, 34, 56, 148),
    "GLASS_FILL_LIGHT": (255, 255, 255, 11),
    "BORDER_SOFT": (255, 255, 255, 26),
    "BORDER_MAIN": (180, 215, 255, 56),
    "BORDER_BRIGHT": (215, 235, 255, 87),
    "CYAN_1": _hex("#45E6FF"),
    "CYAN_2": _hex("#78F2FF"),
    "BLUE_1": _hex("#2F8CFF"),
    "BLUE_2": _hex("#5A7DFF"),
    "VIOLET_1": _hex("#7B61FF"),
    "VIOLET_2": _hex("#A78BFF"),
    "GREEN_1": _hex("#24D977"),
    "GREEN_2": _hex("#51F5A2"),
    "GOLD_1": _hex("#FFB648"),
    "GOLD_2": _hex("#FFD36E"),
    "GOLD_3": _hex("#FF9F1C"),
    "STATUS_ACTIVE_DOT": _hex("#22E27A"),
    "STATUS_ACTIVE_GLOW": (34, 226, 122, 102),
    "GLOW_CYAN": (69, 230, 255, 86),
    "GLOW_BLUE": (47, 140, 255, 76),
    "GLOW_VIOLET": (123, 97, 255, 71),
    "GLOW_GREEN": (36, 217, 119, 71),
    "GLOW_GOLD": (255, 182, 72, 76),
}


@lru_cache(maxsize=8)
def background(width: int, height: int):
    """Legacy background for leaderboard renderer."""
    img = Image.new("RGBA", (width, height), _hex(TOKENS["BG_BASE"]))
    d = ImageDraw.Draw(img, "RGBA")
    top, bot = _hex(TOKENS["BG_DEEP"]), _hex(TOKENS["BG_MID"])
    for y in range(height):
        t = y / max(1, height - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        d.line((0, y, width, y), fill=c)

    g = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g, "RGBA")
    glows = [
        ((-260, -250, width // 2, height // 2), "#63DFFF", 56),
        ((width // 3, -180, width + 180, height // 2), "#8C7CFF", 52),
        ((-180, height // 2 - 130, width // 2 + 160, height + 230), "#73FFD8", 46),
    ]
    for box, col, a in glows:
        gd.ellipse(box, fill=_hex(col, a))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(150)))
    return img


def draw_glow(canvas: Image.Image, box: tuple[int, int, int, int], color: tuple[int, int, int, int], blur: int):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer, "RGBA")
    ld.rounded_rectangle(box, radius=max(8, min((box[2] - box[0]) // 4, (box[3] - box[1]) // 2)), fill=color)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def draw_inner_highlight(card: Image.Image, radius: int):
    w, h = card.size
    d = ImageDraw.Draw(card, "RGBA")
    d.line((22, 14, w - 24, 14), fill=(255, 255, 255, 26), width=2)
    d.rounded_rectangle((1, 1, w - 2, h - 2), radius=max(8, radius - 2), outline=(255, 255, 255, 9), width=1)


def draw_glass_card(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int],
    border: tuple[int, int, int, int],
    shadow_alpha: int = 86,
    shadow_blur: int = 34,
    shadow_offset_y: int = 16,
    glow: tuple[tuple[int, int, int, int], int] | None = None,
):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1

    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh, "RGBA")
    sd.rounded_rectangle((x1, y1 + shadow_offset_y, x2, y2 + shadow_offset_y), radius=radius, fill=(0, 0, 0, shadow_alpha))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(shadow_blur)))
    if glow:
        draw_glow(canvas, (x1 + 10, y1 + 10, x2 - 10, y2 - 2), glow[0], glow[1])

    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card, "RGBA")
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=fill, outline=border, width=1)

    top_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td = ImageDraw.Draw(top_overlay, "RGBA")
    for y in range(h):
        a = int(max(0, 26 * (1 - y / max(1, h - 1))))
        if a:
            td.line((0, y, w, y), fill=(255, 255, 255, a))
    card.alpha_composite(top_overlay)
    draw_inner_highlight(card, radius)
    canvas.alpha_composite(card, (x1, y1))


def draw_premium_glass_card(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    glow: tuple[tuple[int, int, int, int], int] | None = None,
    fill: tuple[int, int, int, int] = (18, 26, 44, 194),
    border_outer: tuple[int, int, int, int] = (190, 220, 255, 46),
    border_inner: tuple[int, int, int, int] = (255, 255, 255, 10),
    shadow_alpha: int = 80,
    shadow_blur: int = 34,
    shadow_offset_y: int = 14,
):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1

    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh, "RGBA")
    sd.rounded_rectangle((x1, y1 + shadow_offset_y, x2, y2 + shadow_offset_y), radius=radius, fill=(0, 0, 0, shadow_alpha))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(shadow_blur)))

    if glow:
        draw_glow(canvas, (x1 + 10, y1 + 10, x2 - 10, y2 - 2), glow[0], glow[1])

    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card, "RGBA")
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=fill, outline=border_outer, width=1)
    d.rounded_rectangle((2, 2, w - 3, h - 3), radius=max(8, radius - 2), outline=border_inner, width=1)

    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad, "RGBA")
    for y in range(h):
        a = int(18 * max(0.0, 1 - y / max(1, h - 1)))
        if a > 0:
            gd.line((0, y, w, y), fill=(255, 255, 255, a))
    card.alpha_composite(grad)
    ImageDraw.Draw(card, "RGBA").line((int(22), int(10), int(w - 24), int(10)), fill=(255, 255, 255, 30), width=2)
    canvas.alpha_composite(card, (x1, y1))


def _progress_ratio(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        p = float(value)
    except Exception:
        return 0.0
    if p > 1.0:
        p = p / 100.0
    return max(0.0, min(1.0, p))


def draw_progress_bar(canvas: Image.Image, box: tuple[int, int, int, int], completion: Any):
    x1, y1, x2, y2 = box
    h = y2 - y1
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rounded_rectangle(box, radius=h // 2, fill=(9, 16, 30, 160), outline=(190, 220, 255, 42), width=2)
    d.rounded_rectangle((x1 + 2, y1 + 2, x2 - 2, y2 - 2), radius=h // 2, outline=(255, 255, 255, 12), width=1)
    d.line((x1 + 10, y1 + 5, x2 - 10, y1 + 5), fill=(255, 255, 255, 28), width=2)

    p = _progress_ratio(completion)
    fw = int((x2 - x1) * p)
    if fw < 10:
        return

    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.rounded_rectangle((x1 + 2, y1 + 1, x1 + fw - 2, y2 - 1), radius=h // 2, fill=(69, 230, 255, 56))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(24)))

    fill = Image.new("RGBA", (fw, h - 6), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill, "RGBA")
    c1, c2, c3 = THEME["CYAN_1"], THEME["BLUE_1"], THEME["VIOLET_1"]
    for i in range(fw):
        t = i / max(1, fw - 1)
        if t < 0.5:
            k = t / 0.5
            c = tuple(int(c1[j] + (c2[j] - c1[j]) * k) for j in range(3)) + (255,)
        else:
            k = (t - 0.5) / 0.5
            c = tuple(int(c2[j] + (c3[j] - c2[j]) * k) for j in range(3)) + (255,)
        fd.line((i, 0, i, h - 6), fill=c)
    fd.line((10, 3, max(10, fw - 10), 3), fill=(255, 255, 255, 62), width=2)
    canvas.paste(fill, (x1, y1 + 3), rounded_mask((fw, h - 6), (h - 6) // 2))

    ex = x1 + fw
    cap = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(cap, "RGBA")
    cd.ellipse((ex - 18, y1 - 4, ex + 18, y2 + 4), fill=(123, 97, 255, 62))
    cd.ellipse((ex - 10, y1 + 2, ex + 10, y2 - 2), fill=(205, 216, 255, 58))
    canvas.alpha_composite(cap.filter(ImageFilter.GaussianBlur(18)))


def draw_progress_ring(canvas: Image.Image, center: tuple[int, int], outer_d: int, thickness: int, completion: Any):
    cx, cy = center
    r = outer_d // 2
    box = (cx - r, cy - r, cx + r, cy + r)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.arc(box, start=-90, end=270, fill=(255, 255, 255, 32), width=thickness)

    inner = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(inner, "RGBA").ellipse((cx - r + thickness + 8, cy - r + thickness + 8, cx + r - thickness - 8, cy + r - thickness - 8), fill=(0, 0, 0, 55))
    canvas.alpha_composite(inner.filter(ImageFilter.GaussianBlur(8)))

    p = _progress_ratio(completion)
    if p <= 0:
        return
    end = -90 + int(360 * p)

    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.arc(box, start=-90, end=end, fill=(69, 230, 255, 108), width=thickness)
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))

    steps = max(80, int(outer_d * 1.8))
    for i in range(steps):
        t0 = i / steps
        t1 = (i + 1) / steps
        a0 = -90 + int((end + 90) * t0)
        a1 = -90 + int((end + 90) * t1)
        if a0 >= end:
            break
        if t0 < 0.52:
            k = t0 / 0.52
            c1, c2 = THEME["CYAN_1"], THEME["BLUE_1"]
        else:
            k = (t0 - 0.52) / 0.48
            c1, c2 = THEME["BLUE_1"], THEME["VIOLET_1"]
        col = tuple(int(c1[j] + (c2[j] - c1[j]) * k) for j in range(3)) + (255,)
        d.arc(box, start=a0, end=min(a1, end), fill=col, width=thickness)


def _lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _draw_soft_glow(canvas: Image.Image, box: tuple[int, int, int, int], color: tuple[int, int, int, int], blur: int, radius: int):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer, "RGBA").rounded_rectangle(box, radius=radius, fill=color)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def _draw_liquid_panel(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    base_fill: tuple[int, int, int, int] = (18, 26, 44, 189),
    glow: tuple[tuple[int, int, int, int], int] | None = None,
):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow, "RGBA").rounded_rectangle((x1, y1 + 14, x2, y2 + 14), radius=radius, fill=(0, 0, 0, 82))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(34)))

    if glow:
        _draw_soft_glow(canvas, (x1 + 10, y1 + 8, x2 - 10, y2 - 2), glow[0], glow[1], max(12, radius - 8))

    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel, "RGBA")
    pd.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=base_fill)

    top_grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td = ImageDraw.Draw(top_grad, "RGBA")
    for y in range(h):
        t = y / max(1, h - 1)
        a = int(20 * max(0.0, (1 - t * 1.5)))
        td.line((0, y, w, y), fill=(255, 255, 255, a))
    panel.alpha_composite(top_grad)

    pd.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, outline=(185, 220, 255, 46), width=1)
    pd.rounded_rectangle((2, 2, w - 3, h - 3), radius=max(4, radius - 2), outline=(255, 255, 255, 10), width=1)
    pd.line((24, 12, w - 24, 12), fill=(255, 255, 255, 26), width=1)
    canvas.alpha_composite(panel, (x1, y1))


@lru_cache(maxsize=8)
def _draw_dashboard_background(width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (width, height), _hex("#07101D"))
    d = ImageDraw.Draw(img, "RGBA")
    c1, c2, c3, c4 = _hex("#07101D"), _hex("#0B1424"), _hex("#101A2C"), _hex("#172235")
    for y in range(height):
        t = y / max(1, height - 1)
        if t < 0.42:
            col = _lerp_color(c1[:3], c2[:3], t / 0.42)
        elif t < 0.76:
            col = _lerp_color(c2[:3], c3[:3], (t - 0.42) / 0.34)
        else:
            col = _lerp_color(c3[:3], c4[:3], (t - 0.76) / 0.24)
        d.line((0, y, width, y), fill=col + (255,))

    hero_glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hero_glow, "RGBA")
    hd.ellipse((300 * SS, 170 * SS, 1220 * SS, 740 * SS), fill=(66, 232, 255, 22))
    hd.ellipse((860 * SS, 120 * SS, 1500 * SS, 680 * SS), fill=(122, 97, 255, 20))
    img.alpha_composite(hero_glow.filter(ImageFilter.GaussianBlur(70 * SS)))

    vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette, "RGBA")
    vd.rectangle((0, 0, width, height), fill=(0, 0, 0, 35))
    vd.rounded_rectangle((80 * SS, 60 * SS, width - 80 * SS, height - 50 * SS), radius=220 * SS, fill=(0, 0, 0, 0))
    img.alpha_composite(vignette.filter(ImageFilter.GaussianBlur(90 * SS)))
    return img


def _draw_ring(canvas: Image.Image, center: tuple[int, int], diameter: int, width: int, completion: Any):
    cx, cy = center
    r = diameter // 2
    box = (cx - r, cy - r, cx + r, cy + r)
    d = ImageDraw.Draw(canvas, "RGBA")
    d.arc(box, start=-90, end=270, fill=(80, 105, 150, 170), width=width)

    p = _progress_ratio(completion)
    end = -90 + int(360 * p)
    if p <= 0:
        return

    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.arc(box, start=-90, end=end, fill=(66, 232, 255, 140), width=width + 2)
    gd.arc((box[0] - 6, box[1] - 6, box[2] + 6, box[3] + 6), start=-90, end=end, fill=(176, 108, 255, 80), width=6)
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))

    steps = max(180, int(diameter * 2.5))
    c1, c2, c3, c4 = (66, 232, 255), (47, 140, 255), (123, 97, 255), (176, 108, 255)
    for i in range(steps):
        t0 = i / steps
        a0 = -90 + int((end + 90) * t0)
        a1 = -90 + int((end + 90) * (i + 1) / steps)
        if a0 >= end:
            break
        if t0 < 0.35:
            col = _lerp_color(c1, c2, t0 / 0.35)
        elif t0 < 0.72:
            col = _lerp_color(c2, c3, (t0 - 0.35) / 0.37)
        else:
            col = _lerp_color(c3, c4, (t0 - 0.72) / 0.28)
        d.arc(box, start=a0, end=min(a1, end), fill=col + (255,), width=width)


def _draw_progress_bar(canvas: Image.Image, box: tuple[int, int, int, int], completion: Any):
    x1, y1, x2, y2 = box
    h = y2 - y1
    radius = h // 2
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rounded_rectangle(box, radius=radius, fill=(9, 17, 34, 190), outline=(185, 220, 255, 45), width=1)
    d.rounded_rectangle((x1 + 2, y1 + 2, x2 - 3, y2 - 3), radius=radius - 2, outline=(255, 255, 255, 12), width=1)

    p = _progress_ratio(completion)
    fw = int((x2 - x1 - 4) * p)
    if fw <= 0:
        return

    fill_box = (x1 + 2, y1 + 2, x1 + 2 + fw, y2 - 2)
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    gd.rounded_rectangle(fill_box, radius=radius - 2, fill=(66, 232, 255, 118))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(16)))

    grad = Image.new("RGBA", (max(1, fw), h - 4), (0, 0, 0, 0))
    g = ImageDraw.Draw(grad, "RGBA")
    c1, c2, c3 = (66, 232, 255), (47, 140, 255), (123, 97, 255)
    for i in range(max(1, fw)):
        t = i / max(1, fw - 1)
        col = _lerp_color(c1, c2, t / 0.55) if t < 0.55 else _lerp_color(c2, c3, (t - 0.55) / 0.45)
        g.line((i, 0, i, h - 5), fill=col + (255,))
    g.line((8, 4, max(10, fw - 8), 4), fill=(255, 255, 255, 84), width=2)
    canvas.paste(grad, (x1 + 2, y1 + 2), rounded_mask((max(1, fw), h - 4), max(2, radius - 2)))

    ex = x1 + 2 + fw
    cap = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(cap, "RGBA")
    cd.ellipse((ex - 12, y1 - 2, ex + 12, y2 + 2), fill=(176, 108, 255, 138))
    canvas.alpha_composite(cap.filter(ImageFilter.GaussianBlur(10)))


def _draw_coin_cluster(canvas: Image.Image, anchor: tuple[int, int]):
    ax, ay = anchor
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    coins = [(-78, 22, 58), (-42, 12, 54), (-2, 6, 60), (40, 8, 56), (74, 22, 50), (-20, -10, 52), (22, -18, 48), (58, -8, 46)]
    for dx, dy, r in coins:
        cx, cy = ax + dx, ay + dy
        d.ellipse((cx - r, cy - r * 0.46, cx + r, cy + r * 0.46), fill=(255, 182, 72, 72), outline=(255, 211, 110, 245), width=3)
        d.ellipse((cx - r * 0.72, cy - r * 0.29, cx + r * 0.72, cy + r * 0.29), outline=(255, 236, 178, 180), width=2)
        d.text((cx, cy - 1), "₽", fill=(255, 246, 201, 210), font=font(26 * SS, "bold"), anchor="mm")
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow, "RGBA").ellipse((ax - 180, ay - 120, ax + 180, ay + 120), fill=(255, 182, 72, 90))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(26)))
    canvas.alpha_composite(layer)


def _draw_calendar_icon(canvas: Image.Image, box: tuple[int, int, int, int]):
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    d.rounded_rectangle((x1, y1, x2, y2), radius=22 * SS, fill=(42, 104, 255, 45), outline=(143, 179, 255, 220), width=3)
    d.rounded_rectangle((x1 + 10 * SS, y1 + 18 * SS, x2 - 10 * SS, y2 - 10 * SS), radius=16 * SS, outline=(198, 212, 255, 120), width=2)
    d.line((x1 + 16 * SS, y1 + 38 * SS, x2 - 16 * SS, y1 + 38 * SS), fill=(168, 205, 255, 220), width=3)
    for i in range(3):
        for j in range(2):
            cx = x1 + (24 + i * 24) * SS
            cy = y1 + (56 + j * 22) * SS
            d.ellipse((cx - 3 * SS, cy - 3 * SS, cx + 3 * SS, cy + 3 * SS), fill=(168, 205, 255, 210))
    d.ellipse((x2 - 32 * SS, y2 - 30 * SS, x2 - 6 * SS, y2 - 4 * SS), fill=(64, 130, 255, 90), outline=(180, 208, 255, 220), width=2)
    d.line((x2 - 19 * SS, y2 - 17 * SS, x2 - 19 * SS, y2 - 24 * SS), fill=(223, 235, 255, 230), width=2)
    d.line((x2 - 19 * SS, y2 - 17 * SS, x2 - 13 * SS, y2 - 14 * SS), fill=(223, 235, 255, 230), width=2)
    canvas.alpha_composite(layer)


def _draw_trend_icon(canvas: Image.Image, box: tuple[int, int, int, int]):
    x1, y1, x2, y2 = box
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow, "RGBA").ellipse((x1 - 50 * SS, y1 - 28 * SS, x2 + 30 * SS, y2 + 24 * SS), fill=(34, 226, 122, 95))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(26)))

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    pts = [
        (x1 + 8 * SS, y2 - 14 * SS),
        (x1 + 36 * SS, y1 + 36 * SS),
        (x1 + 70 * SS, y1 + 44 * SS),
        (x2 - 34 * SS, y1 + 16 * SS),
    ]
    d.line(pts, fill=(82, 247, 165, 245), width=7, joint="curve")
    d.line((pts[0][0], pts[0][1], pts[1][0], pts[1][1]), fill=(198, 255, 225, 90), width=3)
    d.polygon([(x2 - 40 * SS, y1 + 10 * SS), (x2 - 12 * SS, y1 + 16 * SS), (x2 - 28 * SS, y1 + 34 * SS)], fill=(82, 247, 165, 250))
    canvas.alpha_composite(layer)


def _render_dashboard_footer_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
        except Exception:
            return value
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def render_dashboard_image_bytes(mode: str, payload: dict) -> BytesIO:
    s = SS
    c = _draw_dashboard_background(W * s, H * s).copy()
    d = ImageDraw.Draw(c, "RGBA")

    header = (56 * s, 40 * s, 1544 * s, 152 * s)
    hero = (56 * s, 170 * s, 1544 * s, 520 * s)
    cards = [
        (56 * s, 538 * s, 529 * s, 698 * s),
        (563 * s, 538 * s, 1036 * s, 698 * s),
        (1071 * s, 538 * s, 1544 * s, 698 * s),
    ]
    stats = (56 * s, 714 * s, 1544 * s, 806 * s)

    _draw_liquid_panel(c, header, 40 * s, glow=((66, 232, 255, 48), 24 * s))
    _draw_liquid_panel(c, hero, 42 * s, glow=((66, 232, 255, 58), 34 * s))
    _draw_liquid_panel(c, cards[0], 32 * s, glow=((255, 182, 72, 72), 28 * s))
    _draw_liquid_panel(c, cards[1], 32 * s, glow=((90, 125, 255, 80), 30 * s))
    _draw_liquid_panel(c, cards[2], 32 * s, glow=((34, 226, 122, 80), 30 * s))
    _draw_liquid_panel(c, stats, 32 * s, glow=((80, 130, 255, 36), 18 * s))

    title = payload.get("title") or "Дашборд"
    subtitle = payload.get("decade_title") or "1-я декада: 1-10 марта · 01.03-10.03"
    d.text((94 * s, 90 * s), title, fill=_hex("#F5F9FF"), font=font(52 * s, "bold"), anchor="ls")
    d.text((94 * s, 132 * s), subtitle, fill=_hex("#B9C7DB"), font=font(27 * s, "medium"), anchor="ls")

    status_text = payload.get("shift_status") or "Смена активна"
    sp = (1244 * s, 68 * s, 1512 * s, 128 * s)
    _draw_liquid_panel(c, sp, 30 * s, base_fill=(20, 46, 38, 172), glow=((34, 226, 122, 90), 18 * s))
    d.ellipse((1268 * s, 86 * s, 1288 * s, 106 * s), fill=_hex("#22E27A"), outline=(200, 255, 220, 255), width=1)
    dot_glow = Image.new("RGBA", c.size, (0, 0, 0, 0))
    ImageDraw.Draw(dot_glow, "RGBA").ellipse((1258 * s, 76 * s, 1298 * s, 116 * s), fill=(34, 226, 122, 110))
    c.alpha_composite(dot_glow.filter(ImageFilter.GaussianBlur(10)))
    d.text((1300 * s, 98 * s), status_text, fill=_hex("#D8FFE9"), font=font(24 * s, "semibold"), anchor="lm")

    earned = _safe_i(payload.get("decade_earned", payload.get("earned", 0)))
    goal = _safe_i(payload.get("decade_goal", payload.get("goal", 0)))
    main_value = payload.get("current_amount") or format_money(earned)
    target_value = payload.get("target_amount") or format_money(goal)
    completion = payload.get("completion_percent")

    d.text((170 * s, 262 * s), payload.get("revenue_label") or "Выручка", fill=_hex("#B9C7DB"), font=font(30 * s, "medium"), anchor="ls")
    d.text((170 * s, 350 * s), main_value, fill=_hex("#F5F9FF"), font=font(92 * s, "bold"), anchor="ls")
    d.text((170 * s, 410 * s), f"из {target_value}", fill=_hex("#C6D5EA"), font=font(34 * s, "semibold"), anchor="ls")

    _draw_progress_bar(c, (170 * s, 458 * s, 1000 * s, 492 * s), completion)

    ring_center = (1260 * s, 344 * s)
    _draw_ring(c, ring_center, 216 * s, 23 * s, completion)
    pct = f"{int(round(_progress_ratio(completion) * 100))}%"
    d.text((ring_center[0], ring_center[1] - 16 * s), pct, fill=_hex("#F5F9FF"), font=font(58 * s, "bold"), anchor="mm")
    d.text((ring_center[0], ring_center[1] + 32 * s), "Выполнено", fill=_hex("#B9C7DB"), font=font(24 * s, "semibold"), anchor="mm")

    remaining_text = payload.get("remaining_amount") or payload.get("remaining_text") or "—"
    if remaining_text == "—" and goal:
        remaining_text = format_money(max(goal - earned, 0))
    d.text((1170 * s, 462 * s), f"Осталось {remaining_text}", fill=_hex("#B9C7DB"), font=font(28 * s, "semibold"), anchor="ls")

    metric_rows = payload.get("decade_metrics") or payload.get("metrics") or []
    metric_map = {str(row[0]).lower(): str(row[1]) for row in metric_rows if isinstance(row, (list, tuple)) and len(row) >= 2}
    shifts_left = payload.get("shifts_left") or metric_map.get("осталось смен") or metric_map.get("смен осталось") or "—"
    per_shift_needed = payload.get("per_shift_needed") or metric_map.get("нужно в смену") or "—"

    kpi_data = [
        (cards[0], "Осталось до плана", str(remaining_text), _hex("#FFD36E")),
        (cards[1], "Смен осталось", str(shifts_left), _hex("#AFC4FF")),
        (cards[2], "Нужно в смену", str(per_shift_needed), _hex("#9FFFCB")),
    ]
    for box, label, value, accent in kpi_data:
        bx1, by1, bx2, by2 = box
        d.text((bx1 + 28 * s, by1 + 58 * s), label, fill=accent, font=font(28 * s, "medium"), anchor="ls")
        vtxt, vf = fit_text_to_width(value, 62 * s, 42 * s, int((bx2 - bx1) * 0.54), "bold", ellipsis=False)
        d.text((bx1 + 28 * s, by1 + 124 * s), vtxt, fill=_hex("#F5F9FF"), font=vf, anchor="ls")

    _draw_coin_cluster(c, (460 * s, 648 * s))
    _draw_calendar_icon(c, (938 * s, 578 * s, 1030 * s, 684 * s))
    _draw_trend_icon(c, (1372 * s, 578 * s, 1516 * s, 686 * s))

    mini = payload.get("mini") or []
    g1 = mini[0] if len(mini) > 0 else f"Смен: {payload.get('shifts_done', '—')}"
    g2 = mini[1] if len(mini) > 1 else f"Машин: {payload.get('cars_done', '—')}"
    g3 = mini[2] if len(mini) > 2 else f"Средний чек: {payload.get('average_check', '—')}"
    g4 = mini[3] if len(mini) > 3 else payload.get("delta_badge", "+12% к прошлой декаде")

    wrappers = [(92 * s, 734 * s, 360 * s, 786 * s), (478 * s, 734 * s, 744 * s, 786 * s), (860 * s, 734 * s, 1170 * s, 786 * s)]
    for wb in wrappers:
        _draw_liquid_panel(c, wb, 22 * s, base_fill=(20, 31, 52, 148))
    d.text((120 * s, 760 * s), g1, fill=_hex("#D0DEEF"), font=font(24 * s, "semibold"), anchor="lm")
    d.text((506 * s, 760 * s), g2, fill=_hex("#D0DEEF"), font=font(24 * s, "semibold"), anchor="lm")
    d.text((888 * s, 760 * s), g3, fill=_hex("#D0DEEF"), font=font(24 * s, "semibold"), anchor="lm")

    badge = (1190 * s, 730 * s, 1510 * s, 790 * s)
    _draw_liquid_panel(c, badge, 26 * s, base_fill=(26, 74, 58, 164), glow=((34, 226, 122, 74), 16 * s))
    d.text((1208 * s, 760 * s), g4, fill=_hex("#8AFFC2"), font=font(22 * s, "semibold"), anchor="lm")

    footer_text = f"Обновлено: {_render_dashboard_footer_dt(payload.get('updated_at'))}"
    d.text((730 * s, 856 * s), "◦", fill=_hex("#8B97B1"), font=font(20 * s, "semibold"), anchor="mm")
    d.text((800 * s, 856 * s), footer_text, fill=_hex("#8B97B1"), font=font(24 * s, "medium"), anchor="mm")

    out = c.resize((W, H), Image.Resampling.LANCZOS)
    bio = BytesIO()
    bio.name = "dashboard.png"
    out.convert("RGB").save(bio, format="PNG")
    bio.seek(0)
    return bio




def draw_avatar(canvas, box, avatar, name):
    x1, y1, x2, y2 = box
    size = min(x2 - x1, y2 - y1)
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size, size), fill=255)
    if avatar is None:
        av = Image.new("RGBA", (size, size), _hex("#5C7CFF", 220))
        initials = "".join(p[:1] for p in str(name or "?").split()[:2]).upper() or "?"
        dd = ImageDraw.Draw(av, "RGBA")
        f = font(max(26, size // 3), "bold")
        tw, th = measure(dd, initials, f)
        dd.text(((size - tw) / 2, (size - th) / 2 - 1), initials, fill=TOKENS["TEXT_PRIMARY"], font=f)
    else:
        av = ImageOps.fit(avatar.convert("RGBA"), (size, size), method=Image.Resampling.LANCZOS)
    canvas.paste(av, (x1, y1), m)
    ImageDraw.Draw(canvas, "RGBA").ellipse((x1 - 3, y1 - 3, x1 + size + 3, y1 + size + 3), outline=TOKENS["GLASS_BORDER_MAIN"], width=3)


def draw_glass_panel(canvas: Image.Image, bg: Image.Image, box: tuple[int, int, int, int], radius: int, tint=(220, 235, 255, 40), border=TOKENS["GLASS_BORDER_SOFT"], glow: tuple[int, int, int, int] | None = None):
    draw_glass_card(canvas, box, radius, tint, border, glow=((glow or (80, 140, 255, 62)), 24))


def draw_glass_pill(canvas, bg, box, text, color=TOKENS["TEXT_PRIMARY"], weight="semibold"):
    draw_glass_panel(canvas, bg, box, radius=(box[3] - box[1]) // 2, tint=TOKENS["GLASS_FILL_DARK"])
    d = ImageDraw.Draw(canvas, "RGBA")
    txt, f = fit_text_to_width(text, 34, 18, box[2] - box[0] - 28, weight=weight)
    tw, th = measure(d, txt, f)
    d.text((box[0] + (box[2] - box[0] - tw) / 2, box[1] + (box[3] - box[1] - th) / 2 - 1), txt, fill=color, font=f)


def render_leaderboard_image_bytes(decade_title: str, decade_leaders: list[dict], highlight_name: str | None = None, top3_avatars: dict[int, object] | None = None, updated_at: Any | None = None) -> BytesIO:
    s = SS
    bg = background(W * s, H * s).copy()
    c = bg.copy()
    d = ImageDraw.Draw(c, "RGBA")

    header = (52 * s, 42 * s, (W - 52) * s, 200 * s)
    draw_glass_panel(c, bg, header, 32 * s, tint=TOKENS["GLASS_FILL_MAIN"])
    d.text((header[0] + 34 * s, header[1] + 18 * s), "ЛИДЕРБОРД", fill=TOKENS["TEXT_PRIMARY"], font=font(52 * s, "bold"))
    sub, sf = fit_text_to_width(decade_title or "1-я декада", 30 * s, 17 * s, 960 * s, "medium")
    d.text((header[0] + 34 * s, header[1] + 92 * s), sub, fill=TOKENS["TEXT_SECONDARY"], font=sf)
    draw_glass_pill(c, bg, (header[2] - 310 * s, header[1] + 50 * s, header[2] - 34 * s, header[1] + 112 * s), "Top Heroes")

    avatars = top3_avatars or {}
    top = {2: (56, 242, 486, 538), 1: (450, 206, 1150, 574), 3: (1114, 242, 1544, 538)}
    rank_tints = {1: (120, 150, 255, 48), 2: (110, 200, 255, 44), 3: (130, 160, 255, 44)}
    rank_glow = {1: (120, 130, 255, 96), 2: (95, 205, 255, 70), 3: (120, 150, 255, 62)}
    for rank in (2, 1, 3):
        if len(decade_leaders) < rank:
            continue
        row = decade_leaders[rank - 1]
        x1, y1, x2, y2 = [v * s for v in top[rank]]
        draw_glass_panel(c, bg, (x1, y1, x2, y2), 30 * s, tint=rank_tints[rank], border=TOKENS["GLASS_BORDER_MAIN"], glow=rank_glow[rank])
        draw_glass_pill(c, bg, (x1 + 20 * s, y1 + 18 * s, x1 + 132 * s, y1 + 72 * s), f"#{rank}")
        av_size = (136 if rank == 1 else 110) * s
        av_x = x1 + (x2 - x1 - av_size) // 2
        av_y = y1 + (72 if rank == 1 else 58) * s
        draw_avatar(c, (av_x, av_y, av_x + av_size, av_y + av_size), avatars.get(_safe_i(row.get("telegram_id"))), row.get("name"))
        name, nf = fit_text_to_width(str(row.get("name", "—")), 42 * s if rank == 1 else 34 * s, 20 * s, (x2 - x1) - 60 * s, "semibold")
        nw, nh = measure(d, name, nf)
        ny = av_y + av_size + 18 * s
        d.text((x1 + (x2 - x1 - nw) / 2, ny), name, fill=TOKENS["TEXT_PRIMARY"], font=nf)

        amt = format_money(row.get("total_amount"))
        af = font(56 * s if rank == 1 else 42 * s, "bold")
        aw, ah = measure(d, amt, af)
        ay = ny + nh + 12 * s
        d.text((x1 + (x2 - x1 - aw) / 2, ay), amt, fill=TOKENS["TEXT_PRIMARY"], font=af)

        avg = "—" if float(row.get("total_hours") or 0) <= 0 else f"{_safe_i(row.get('avg_per_hour'))} ₽/ч"
        rr, rc = format_tempo(row.get("run_rate"))
        shifts = str(_safe_i(row.get("shifts_count", row.get("shift_count"))))
        chips = [(f"Avg {avg}", TOKENS["TEXT_SECONDARY"]), (f"Tempo {rr}", rc), (f"Смены {shifts}", TOKENS["TEXT_SECONDARY"])]
        cy1, cy2 = y2 - 54 * s, y2 - 14 * s
        cw = ((x2 - x1) - 42 * s - 2 * 10 * s) // 3
        for i, (txt, col) in enumerate(chips):
            px1 = x1 + 20 * s + i * (cw + 10 * s)
            draw_glass_panel(c, bg, (px1, cy1, px1 + cw, cy2), 16 * s, tint=TOKENS["GLASS_FILL_DARK"])
            t, tf = fit_text_to_width(txt, 18 * s, 12 * s, cw - 12 * s, "medium")
            tw, th = measure(d, t, tf)
            d.text((px1 + (cw - tw) / 2, cy1 + ((cy2 - cy1) - th) / 2 - 1), t, fill=col, font=tf)

    rows = decade_leaders[3:]
    row_h, gap, top_y = 82 * s, 12 * s, 592 * s
    max_rows = max(0, ((H * s - 56 * s - 72 * s) - top_y + gap) // (row_h + gap))
    for idx, row in enumerate(rows[:max_rows], start=4):
        y1 = top_y + (idx - 4) * (row_h + gap)
        y2 = y1 + row_h
        draw_glass_panel(c, bg, (56 * s, y1, (W - 56) * s, y2), 20 * s, tint=TOKENS["GLASS_FILL_DARK"])
        rx1, rx2 = 56 * s, (W - 56) * s
        draw_glass_pill(c, bg, (rx1 + 14 * s, y1 + 16 * s, rx1 + 100 * s, y1 + 64 * s), f"#{idx}")
        draw_avatar(c, (rx1 + 116 * s, y1 + 12 * s, rx1 + 174 * s, y1 + 70 * s), None, row.get("name"))
        name, nf = fit_text_to_width(str(row.get("name", "—")), 30 * s, 15 * s, 430 * s, "medium")
        d.text((rx1 + 194 * s, y1 + 24 * s), name, fill=TOKENS["TEXT_PRIMARY"], font=nf)
        avg = "—" if float(row.get("total_hours") or 0) <= 0 else f"{_safe_i(row.get('avg_per_hour'))} ₽/ч"
        rr, rc = format_tempo(row.get("run_rate"))
        shifts_txt = str(_safe_i(row.get("shifts_count", row.get("shift_count"))))
        d.text((rx1 + 700 * s, y1 + 24 * s), avg, fill=TOKENS["TEXT_SECONDARY"], font=font(24 * s, "regular"))
        d.text((rx1 + 930 * s, y1 + 24 * s), rr, fill=rc, font=font(24 * s, "semibold"))
        d.text((rx1 + 1070 * s, y1 + 24 * s), shifts_txt, fill=TOKENS["TEXT_MUTED"], font=font(24 * s, "regular"))
        amt = format_money(row.get("total_amount"))
        af = font(34 * s, "bold")
        aw, _ = measure(d, amt, af)
        d.text((rx2 - 28 * s - aw, y1 + 20 * s), amt, fill=TOKENS["TEXT_PRIMARY"], font=af)

    total = sum(_safe_i(x.get("total_amount")) for x in decade_leaders)
    foot = (56 * s, 836 * s, (W - 56) * s, 888 * s)
    draw_glass_panel(c, bg, foot, 16 * s, tint=TOKENS["GLASS_FILL_DARK"])
    parts = [f"Участников: {len(decade_leaders)}", f"Общий объём: {format_money(total)}", f"Обновлено: {format_update_dt(updated_at)}"]
    pw = (foot[2] - foot[0]) // 3
    for i, t in enumerate(parts):
        tt, tf = fit_text_to_width(t, 22 * s, 13 * s, pw - 20 * s, "medium")
        d.text((foot[0] + i * pw + 10 * s, foot[1] + 12 * s), tt, fill=TOKENS["TEXT_SECONDARY"], font=tf)

    out = c.resize((W, H), Image.Resampling.LANCZOS)
    bio = BytesIO(); bio.name = "leaderboard.png"; out.convert("RGB").save(bio, format="PNG"); bio.seek(0)
    return bio
