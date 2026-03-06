from __future__ import annotations

from io import BytesIO
from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 1600, 900
SS = 2

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


def format_money(v: Any) -> str:
    try:
        return f"{int(round(float(v))):,}".replace(",", " ") + " ₽"
    except Exception:
        return "—"


def parse_percent_text(value: Any) -> tuple[str, tuple[int, int, int, int]]:
    raw = str(value or "—")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return "—", TOKENS["TEXT_SECONDARY"]
    n = int(digits)
    c = TOKENS["NEUTRAL"]
    if n > 100:
        c = TOKENS["POSITIVE"]
    elif n < 100:
        c = TOKENS["NEGATIVE"]
    return f"{n}%", c


def background(width: int, height: int):
    img = Image.new("RGBA", (width, height), _hex(TOKENS["BG_BASE"]))
    d = ImageDraw.Draw(img, "RGBA")
    top, bot = _hex(TOKENS["BG_DEEP"]), _hex(TOKENS["BG_BLUE"])
    for y in range(height):
        t = y / max(1, height - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        d.line((0, y, width, y), fill=c)
    g = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g, "RGBA")
    gd.ellipse((-240, -220, width // 2, height // 2), fill=_hex("#49D8FF", 34))
    gd.ellipse((width // 4, -200, width + 120, height // 2), fill=_hex("#7A6CFF", 28))
    gd.ellipse((-160, height // 2 - 80, width // 2 + 100, height + 220), fill=_hex("#45F1C8", 26))
    gd.ellipse((width // 2, height // 2 - 100, width + 260, height + 200), fill=_hex("#2D7FFF", 20))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(140)))
    vign = Image.new("L", (width, height), 0)
    ImageDraw.Draw(vign).ellipse((-width // 10, -height // 10, width + width // 10, height + height // 12), fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(max(width, height) // 3))
    img.paste(Image.new("RGBA", (width, height), (0, 0, 0, 80)), (0, 0), ImageOps.invert(vign))
    return img


def draw_glass_panel(canvas: Image.Image, bg: Image.Image, box: tuple[int, int, int, int], radius: int, tint=(190, 220, 255, 30), border=TOKENS["GLASS_BORDER_SOFT"]):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    m = rounded_mask((w, h), radius)
    crop = bg.crop(box).filter(ImageFilter.GaussianBlur(20))
    crop = ImageEnhance.Brightness(crop).enhance(1.07)
    canvas.paste(crop, (x1, y1), m)
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh, "RGBA").rounded_rectangle((x1 + 2, y1 + 8, x2 + 2, y2 + 12), radius=radius, fill=(0, 0, 0, 70))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card, "RGBA")
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=tint, outline=border, width=2)
    d.rounded_rectangle((4, 4, w - 5, max(18, h // 2)), radius=max(8, radius - 8), outline=TOKENS["INNER_HIGHLIGHT_TOP"], width=1)
    canvas.alpha_composite(card, (x1, y1))


def draw_glass_pill(canvas, bg, box, text, color=TOKENS["TEXT_PRIMARY"], weight="semibold"):
    draw_glass_panel(canvas, bg, box, radius=(box[3]-box[1])//2, tint=TOKENS["GLASS_FILL_DARK"])
    d = ImageDraw.Draw(canvas, "RGBA")
    txt, f = fit_text_to_width(text, 30, 16, box[2]-box[0]-24, weight=weight)
    tw, th = measure(d, txt, f)
    d.text((box[0] + (box[2]-box[0]-tw)/2, box[1] + (box[3]-box[1]-th)/2 - 1), txt, fill=color, font=f)


def draw_progress_bar(canvas, box, completion):
    d = ImageDraw.Draw(canvas, "RGBA")
    x1,y1,x2,y2 = box
    h = y2-y1
    d.rounded_rectangle(box, radius=h//2, fill=(255,255,255,22), outline=(255,255,255,44), width=2)
    if completion is None:
        return
    p = max(0.0, min(1.0, float(completion)))
    fw = int((x2-x1-6)*p)
    if fw <= 0:
        return
    grad = Image.new("RGBA", (fw, h-6), (0,0,0,0))
    gd = ImageDraw.Draw(grad, "RGBA")
    c1,c2,c3 = _hex(TOKENS["ACCENT_CYAN"],240), _hex(TOKENS["ACCENT_SKY"],240), _hex(TOKENS["ACCENT_VIOLET"],240)
    for i in range(fw):
        t = i/max(1,fw-1)
        if t < 0.6:
            k = t/0.6
            c = tuple(int(c1[j]+(c2[j]-c1[j])*k) for j in range(4))
        else:
            k = (t-0.6)/0.4
            c = tuple(int(c2[j]+(c3[j]-c2[j])*k) for j in range(4))
        gd.line((i,0,i,h-6), fill=c)
    canvas.paste(grad, (x1+3,y1+3), rounded_mask((fw,h-6),(h-6)//2))


def draw_avatar(canvas, box, avatar, name):
    x1,y1,x2,y2 = box
    size = min(x2-x1, y2-y1)
    m = Image.new("L", (size,size), 0)
    ImageDraw.Draw(m).ellipse((0,0,size,size), fill=255)
    if avatar is None:
        av = Image.new("RGBA", (size,size), _hex(TOKENS["ACCENT_BLUE"],220))
        initials = "".join(p[:1] for p in str(name or "?").split()[:2]).upper() or "?"
        d = ImageDraw.Draw(av, "RGBA")
        f = font(max(20,size//3), "bold")
        tw,th = measure(d, initials, f)
        d.text(((size-tw)/2,(size-th)/2-1), initials, fill=TOKENS["TEXT_PRIMARY"], font=f)
    else:
        av = ImageOps.fit(avatar.convert("RGBA"), (size,size), method=Image.Resampling.LANCZOS)
    canvas.paste(av, (x1,y1), m)
    ImageDraw.Draw(canvas, "RGBA").ellipse((x1-2,y1-2,x1+size+2,y1+size+2), outline=TOKENS["GLASS_BORDER"], width=2)


def render_dashboard_image_bytes(mode: str, payload: dict) -> BytesIO:
    s = SS
    bg = background(W*s, H*s)
    c = bg.copy()
    d = ImageDraw.Draw(c, "RGBA")
    m = 56*s

    header = (56*s, 52*s, (W-56)*s, (52+130)*s)
    draw_glass_panel(c, bg, header, 28*s)
    d.text((header[0]+32*s, header[1]+20*s), "Дашборд", fill=TOKENS["TEXT_PRIMARY"], font=font(40*s, "bold"))
    st, sf = fit_text_to_width(payload.get("decade_title", "—"), 24*s, 14*s, 900*s, "medium")
    d.text((header[0]+32*s, header[1]+78*s), st, fill=TOKENS["TEXT_SECONDARY"], font=sf)
    draw_glass_pill(c, bg, (header[2]-320*s, header[1]+38*s, header[2]-34*s, header[1]+90*s), "Смена закрыта" if mode == "closed" else "Смена активна")

    hero = (56*s, 214*s, (W-56)*s, 644*s)
    draw_glass_panel(c, bg, hero, 30*s, tint=TOKENS["GLASS_FILL_PRIMARY"])
    lx1 = hero[0] + 34*s
    d.text((lx1, hero[1]+30*s), "Главный KPI", fill=TOKENS["TEXT_PRIMARY"], font=font(30*s, "semibold"))
    ptxt, pf = fit_text_to_width(payload.get("decade_title", "—"), 18*s, 12*s, 760*s, "regular")
    d.text((lx1, hero[1]+78*s), ptxt, fill=TOKENS["TEXT_MUTED"], font=pf)

    earned = payload.get("decade_earned", payload.get("earned", 0))
    goal = payload.get("decade_goal", payload.get("goal", 0))
    d.text((lx1, hero[1]+126*s), format_money(earned), fill=TOKENS["TEXT_PRIMARY"], font=font(62*s, "bold"))
    d.text((lx1, hero[1]+228*s), f"из {format_money(goal)}" if int(goal or 0) > 0 else "из —", fill=TOKENS["TEXT_SECONDARY"], font=font(26*s, "regular"))

    completion = payload.get("completion_percent")
    runrate_text, runrate_color = parse_percent_text(payload.get("pace_text"))
    delta_text = payload.get("pace_delta_text", "—")
    accent = (hero[2]-360*s, hero[1]+34*s, hero[2]-34*s, hero[1]+258*s)
    draw_glass_panel(c, bg, accent, 26*s, tint=(110, 170, 255, 28), border=TOKENS["GLASS_BORDER"])
    comp_text = "—" if completion is None else f"{int(round(float(completion)*100))}%"
    d.text((accent[0]+30*s, accent[1]+20*s), comp_text, fill=TOKENS["TEXT_PRIMARY"], font=font(56*s, "bold"))
    d.text((accent[0]+32*s, accent[1]+112*s), "Выполнение", fill=TOKENS["TEXT_SECONDARY"], font=font(22*s, "semibold"))
    d.text((accent[0]+32*s, accent[1]+152*s), f"Темп: {runrate_text}", fill=runrate_color, font=font(20*s, "medium"))
    dc = TOKENS["TEXT_SECONDARY"] if "—" in str(delta_text) else (TOKENS["POSITIVE"] if str(delta_text).startswith("+") else TOKENS["NEGATIVE"])
    delta_fit, df = fit_text_to_width(str(delta_text), 20*s, 12*s, accent[2]-accent[0]-64*s, "medium")
    d.text((accent[0]+32*s, accent[1]+184*s), delta_fit, fill=dc, font=df)

    draw_progress_bar(c, (hero[0]+34*s, hero[1]+294*s, hero[2]-34*s, hero[1]+324*s), completion)

    metrics = (payload.get("decade_metrics") or payload.get("metrics") or [])[:6]
    cw = ((hero[2]-hero[0]) - 68*s - 2*18*s)//3
    ch = 104*s
    for i in range(6):
        row,col = divmod(i,3)
        bx1 = hero[0] + 34*s + col*(cw + 18*s)
        by1 = hero[1] + 338*s + row*(ch + 18*s)
        draw_glass_panel(c, bg, (bx1,by1,bx1+cw,by1+ch), 18*s, tint=TOKENS["GLASS_FILL_DARK"])
        title, value, clr = (metrics[i] if i < len(metrics) else ("—","—",TOKENS["TEXT_PRIMARY"]))
        t, tf = fit_text_to_width(str(title), 18*s, 12*s, cw-28*s, "medium")
        v, vf = fit_text_to_width(str(value), 26*s, 14*s, cw-28*s, "semibold")
        d.text((bx1+14*s, by1+14*s), t, fill=TOKENS["TEXT_MUTED"], font=tf)
        d.text((bx1+14*s, by1+52*s), v, fill=clr, font=vf)

    mini = payload.get("mini") or []
    footer = (56*s, 760*s, (W-56)*s, 838*s)
    pill_w = (footer[2]-footer[0]-24*s)//3
    for i in range(3):
        x1 = footer[0] + i*(pill_w + 12*s)
        draw_glass_panel(c, bg, (x1, footer[1], x1+pill_w, footer[3]), 20*s, tint=TOKENS["GLASS_FILL_DARK"])
        txt = mini[i] if i < len(mini) else "—"
        t, tf = fit_text_to_width(str(txt), 20*s, 12*s, pill_w-24*s, "medium")
        d.text((x1+14*s, footer[1]+24*s), t, fill=TOKENS["TEXT_SECONDARY"], font=tf)

    out = c.resize((W, H), Image.Resampling.LANCZOS)
    bio = BytesIO(); bio.name = "dashboard.png"; out.convert("RGB").save(bio, format="PNG"); bio.seek(0)
    return bio


def _safe_i(v, d=0):
    try: return int(v)
    except Exception: return d


def render_leaderboard_image_bytes(decade_title: str, decade_leaders: list[dict], highlight_name: str | None = None, top3_avatars: dict[int, object] | None = None) -> BytesIO:
    s = SS
    bg = background(W*s, H*s)
    c = bg.copy()
    d = ImageDraw.Draw(c, "RGBA")
    m = 56*s
    header = (m, 52*s, (W-56)*s, 190*s)
    draw_glass_panel(c, bg, header, 28*s)
    d.text((header[0]+32*s, header[1]+20*s), "ЛИДЕРБОРД", fill=TOKENS["TEXT_PRIMARY"], font=font(40*s, "bold"))
    sub, sf = fit_text_to_width(decade_title or "1-я декада", 24*s, 14*s, 900*s, "medium")
    d.text((header[0]+32*s, header[1]+82*s), sub, fill=TOKENS["TEXT_SECONDARY"], font=sf)
    draw_glass_pill(c, bg, (header[2]-290*s, header[1]+44*s, header[2]-34*s, header[1]+96*s), "Top Heroes")

    avatars = top3_avatars or {}
    top = {2:(56,242,486,527),1:(470,206,1130,546),3:(1114,242,1544,527)}
    for rank in (2,1,3):
        if len(decade_leaders) < rank:
            continue
        row = decade_leaders[rank-1]
        x1,y1,x2,y2 = [v*s for v in top[rank]]
        draw_glass_panel(c, bg, (x1,y1,x2,y2), 28*s, tint=TOKENS["GLASS_FILL_PRIMARY"] if rank==1 else TOKENS["GLASS_FILL_SECONDARY"], border=TOKENS["GLASS_BORDER"])
        draw_glass_pill(c, bg, (x1+20*s,y1+18*s,x1+118*s,y1+62*s), f"#{rank}")
        av_size = (120 if rank==1 else 96)*s
        av_x = x1 + (x2-x1-av_size)//2
        av_y = y1 + (66 if rank==1 else 56)*s
        draw_avatar(c, (av_x,av_y,av_x+av_size,av_y+av_size), avatars.get(_safe_i(row.get("telegram_id"))), row.get("name"))
        name_max = (x2-x1)-60*s
        name, nf = fit_text_to_width(str(row.get("name","—")), 34*s if rank==1 else 28*s, 16*s, name_max, "semibold")
        nw, nh = measure(d, name, nf)
        ny = av_y + av_size + 16*s
        d.text((x1 + (x2-x1-nw)/2, ny), name, fill=TOKENS["TEXT_PRIMARY"], font=nf)
        amt = format_money(row.get("total_amount"))
        af = font(46*s if rank==1 else 34*s, "bold")
        aw, ah = measure(d, amt, af)
        ay = ny + nh + 10*s
        d.text((x1+(x2-x1-aw)/2, ay), amt, fill=TOKENS["TEXT_PRIMARY"], font=af)
        avg = "—" if float(row.get("total_hours") or 0) <= 0 else f"{_safe_i(row.get('avg_per_hour'))} ₽"
        rr, rc = parse_percent_text(row.get("run_rate"))
        shifts = str(_safe_i(row.get("shifts_count")))
        chips = [(f"Avg/ч {avg}", TOKENS["TEXT_SECONDARY"]), (f"Tempo {rr}", rc), (f"Смены {shifts}", TOKENS["TEXT_SECONDARY"])]
        cy1, cy2 = y2 - 50*s, y2 - 16*s
        cw = ((x2-x1)-40*s-2*10*s)//3
        for i,(txt,col) in enumerate(chips):
            px1 = x1 + 20*s + i*(cw+10*s)
            draw_glass_panel(c,bg,(px1,cy1,px1+cw,cy2),14*s,tint=TOKENS["GLASS_FILL_DARK"])
            t,tf = fit_text_to_width(txt, 15*s, 11*s, cw-12*s, "medium")
            tw,th = measure(d,t,tf)
            d.text((px1+(cw-tw)/2, cy1+((cy2-cy1)-th)/2-1), t, fill=col, font=tf)

    rows = decade_leaders[3:]
    row_h, gap, top_y = 72*s, 10*s, 560*s
    max_rows = max(0, ((H*s - 56*s - 58*s) - top_y + gap)//(row_h+gap))
    for idx,row in enumerate(rows[:max_rows], start=4):
        y1 = top_y + (idx-4)*(row_h+gap)
        y2 = y1 + row_h
        draw_glass_panel(c,bg,(56*s,y1,(W-56)*s,y2),18*s,tint=TOKENS["GLASS_FILL_DARK"])
        rx1, rx2 = 56*s, (W-56)*s
        draw_glass_pill(c,bg,(rx1+12*s,y1+15*s,rx1+88*s,y1+57*s), f"#{idx}")
        draw_avatar(c,(rx1+100*s,y1+12*s,rx1+148*s,y1+60*s),None,row.get("name"))
        name, nf = fit_text_to_width(str(row.get("name","—")), 24*s, 12*s, 300*s, "medium")
        d.text((rx1+164*s,y1+24*s), name, fill=TOKENS["TEXT_PRIMARY"], font=nf)
        avg = "—" if float(row.get("total_hours") or 0) <= 0 else f"{_safe_i(row.get('avg_per_hour'))} ₽/ч"
        d.text((rx1+530*s,y1+24*s), avg, fill=TOKENS["TEXT_SECONDARY"], font=font(18*s,"regular"))
        rr, rc = parse_percent_text(row.get("run_rate"))
        d.text((rx1+730*s,y1+24*s), rr if rr != "—" else "—", fill=rc, font=font(18*s,"semibold"))
        d.text((rx1+860*s,y1+24*s), str(_safe_i(row.get("shifts_count"))), fill=TOKENS["TEXT_MUTED"], font=font(18*s,"regular"))
        amt = format_money(row.get("total_amount")); af = font(24*s,"bold"); aw,_ = measure(d,amt,af)
        d.text((rx2-24*s-aw,y1+20*s), amt, fill=TOKENS["TEXT_PRIMARY"], font=af)

    total = sum(_safe_i(x.get("total_amount")) for x in decade_leaders)
    foot = (56*s, 836*s, (W-56)*s, 882*s)
    draw_glass_panel(c,bg,foot,16*s,tint=TOKENS["GLASS_FILL_DARK"])
    parts = [f"Участников: {len(decade_leaders)}", f"Общий объём: {format_money(total)}", "Обновлено сегодня"]
    pw = (foot[2]-foot[0])//3
    for i,t in enumerate(parts):
        tt,tf = fit_text_to_width(t, 18*s, 11*s, pw-20*s, "medium")
        d.text((foot[0]+i*pw+10*s, foot[1]+12*s), tt, fill=TOKENS["TEXT_SECONDARY"], font=tf)

    out = c.resize((W,H), Image.Resampling.LANCZOS)
    bio = BytesIO(); bio.name = "leaderboard.png"; out.convert("RGB").save(bio, format="PNG"); bio.seek(0)
    return bio
