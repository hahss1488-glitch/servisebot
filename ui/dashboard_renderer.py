from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


@dataclass(slots=True)
class MetricItem:
    label: str
    value: str


@dataclass(slots=True)
class PerformanceBlock:
    title: str
    badge: str
    revenue: int
    target: int
    remaining: int
    run_rate: float | None
    metrics: list[MetricItem] = field(default_factory=list)


@dataclass(slots=True)
class MainDashboardData:
    title: str
    status: str
    updated_at: datetime | str | None
    shift: PerformanceBlock
    decade: PerformanceBlock


@dataclass(slots=True)
class ShiftSummaryData:
    title: str
    date_label: str
    duration_label: str
    total: int
    status_message: str
    metrics: list[MetricItem]
    decade_total: int
    decade_remaining: int


@dataclass(slots=True)
class LeaderRow:
    rank: int
    name: str
    earnings: int
    shifts: int = 0
    cars: int = 0
    avatar_path: str | None = None


@dataclass(slots=True)
class LeaderboardData:
    title: str
    subtitle: str
    updated_at: datetime | str | None
    leaders: list[LeaderRow]
    highlight_name: str | None = None
    top3_avatars: dict[int, Image.Image] = field(default_factory=dict)


class DashboardRenderer:
    WIDTH = 1400
    HEIGHT = 980
    MARGIN = 32

    def __init__(self, width: int = WIDTH, height: int = HEIGHT) -> None:
        self.width = width
        self.height = height

    COLORS = {
        "bg": (8, 17, 31, 255),
        "bg_depth": (11, 20, 36, 255),
        "glass": (20, 30, 46, 184),
        "glass_overlay": (255, 255, 255, 9),
        "glass_border": (255, 255, 255, 20),
        "white": (245, 247, 251, 255),
        "secondary": (168, 180, 199, 255),
        "muted": (127, 141, 163, 255),
        "gold": (231, 196, 106, 255),
        "silver": (184, 196, 214, 255),
        "bronze": (199, 146, 98, 255),
        "blue": (121, 184, 255, 255),
        "green": (87, 211, 140, 255),
        "red": (255, 122, 122, 255),
        "pink": (255, 159, 176, 255),
    }
    _avatar_cache: dict[tuple[str, int], Image.Image] = {}

    @staticmethod
    @lru_cache(maxsize=256)
    def _font(size: int, bold: bool = False):
        paths = (
            "/usr/share/fonts/truetype/inter/Inter-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ) if bold else (
            "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
        for path in paths:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(round(float(value)))
        except Exception:
            return default

    def format_money(self, value: Any) -> str:
        return f"{self._safe_int(value, 0):,} ₽".replace(",", " ")

    def draw_glow(self, img: Image.Image, center: tuple[int, int], size: tuple[int, int], color: tuple[int, int, int, int], blur: int = 42, alpha: int = 110) -> None:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        x, y = center
        w, h = size
        d.ellipse((x - w // 2, y - h // 2, x + w // 2, y + h // 2), fill=(color[0], color[1], color[2], alpha))
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))

    def draw_glass_card(self, img: Image.Image, box: tuple[int, int, int, int], radius: int = 24, accent: tuple[int, int, int, int] | None = None) -> None:
        x1, y1, x2, y2 = box
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((x1 + 2, y1 + 6, x2 + 2, y2 + 8), radius=radius, fill=(3, 7, 14, 170))
        d.rounded_rectangle(box, radius=radius, fill=self.COLORS["glass"], outline=self.COLORS["glass_border"], width=2)
        d.rounded_rectangle((x1 + 2, y1 + 2, x2 - 2, y1 + (y2 - y1) // 3), radius=radius, fill=self.COLORS["glass_overlay"])
        if accent is not None:
            d.rounded_rectangle((x1 + 18, y1 + 10, x2 - 18, y1 + 14), radius=999, fill=accent)
        img.alpha_composite(layer)

    def draw_rank_badge(self, draw: ImageDraw.ImageDraw, pos: tuple[int, int], rank: int, tone: tuple[int, int, int, int]) -> None:
        x, y = pos
        text = f"#{rank}"
        tw = draw.textbbox((0, 0), text, font=self._font(20, True))[2]
        draw.rounded_rectangle((x, y, x + tw + 28, y + 36), radius=999, fill=(17, 27, 42, 230), outline=(255, 255, 255, 24), width=1)
        draw.text((x + 14, y + 7), text, fill=tone, font=self._font(20, True))

    def fit_text(self, draw: ImageDraw.ImageDraw, text: str, max_width: int, max_size: int, min_size: int = 20, bold: bool = True) -> tuple[str, ImageFont.FreeTypeFont]:
        size = max_size
        while size >= min_size:
            font = self._font(size, bold)
            if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
                return text, font
            size -= 1
        font = self._font(min_size, bold)
        cut = text
        while len(cut) > 1 and draw.textbbox((0, 0), cut + "…", font=font)[2] > max_width:
            cut = cut[:-1]
        return (cut + "…") if cut else "…", font

    def draw_avatar_or_initials(self, img: Image.Image, row: LeaderRow, center: tuple[int, int], size: int) -> None:
        avatar = self._resolve_avatar(row, size)
        img.alpha_composite(avatar, (center[0] - size // 2, center[1] - size // 2))

    def draw_status_pill(self, draw: ImageDraw.ImageDraw, right_x: int, y: int, text: str, tone: tuple[int, int, int, int]) -> None:
        tw = draw.textbbox((0, 0), text, font=self._font(22, True))[2]
        x = right_x - tw - 34
        for i in range(42):
            k = i / 41
            r = int(16 * (1 - k) + tone[0] * 0.22 * k)
            g = int(27 * (1 - k) + tone[1] * 0.22 * k)
            b = int(42 * (1 - k) + tone[2] * 0.22 * k)
            draw.line((x + 1, y + i, right_x - 1, y + i), fill=(r, g, b, 238))
        draw.rounded_rectangle((x, y, right_x, y + 42), radius=999, outline=(255, 255, 255, 28), width=1)
        draw.text((x + 16, y + 10), text, fill=tone, font=self._font(22, True))

    def _resolve_avatar(self, row: LeaderRow, size: int) -> Image.Image:
        if row.avatar_path:
            key = (row.avatar_path, size)
            cached = self._avatar_cache.get(key)
            if cached is not None:
                return cached
            try:
                p = Path(row.avatar_path)
                if p.exists() and p.is_file() and p.stat().st_size > 32:
                    img = Image.open(p).convert("RGBA")
                    w, h = img.size
                    s = min(w, h)
                    img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((size, size), Image.Resampling.LANCZOS)
                    mask = Image.new("L", (size, size), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
                    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                    out.paste(img, (0, 0), mask)
                    self._avatar_cache[key] = out
                    return out
            except Exception:
                pass
        initials = "".join(part[:1] for part in (row.name or "?").split()[:2]).upper() or "?"
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(out)
        d.ellipse((0, 0, size - 1, size - 1), fill=(30, 47, 70, 240), outline=(255, 255, 255, 60), width=2)
        font = self._font(max(18, size // 3), True)
        bbox = d.textbbox((0, 0), initials, font=font)
        d.text(((size - (bbox[2] - bbox[0])) / 2, (size - (bbox[3] - bbox[1])) / 2), initials, fill=self.COLORS["white"], font=font)
        return out

    def _draw_background(self, img: Image.Image) -> None:
        d = ImageDraw.Draw(img)
        for y in range(self.height):
            t = y / max(1, self.height - 1)
            r = int(self.COLORS["bg"][0] * (1 - t) + self.COLORS["bg_depth"][0] * t)
            g = int(self.COLORS["bg"][1] * (1 - t) + self.COLORS["bg_depth"][1] * t)
            b = int(self.COLORS["bg"][2] * (1 - t) + self.COLORS["bg_depth"][2] * t)
            d.line((0, y, self.width, y), fill=(r, g, b, 255))

    def _format_datetime(self, dt: datetime | str | None) -> str:
        if isinstance(dt, datetime):
            return dt.strftime("%d.%m.%Y %H:%M")
        return str(dt or "—")

    def _status_tone(self, status: str) -> tuple[int, int, int, int]:
        s = (status or "").lower()
        if "выше" in s or "в темпе" in s or "опереж" in s:
            return self.COLORS["green"]
        if "ниже" in s or "отстав" in s:
            return self.COLORS["red"]
        return self.COLORS["blue"]

    def _draw_header(self, img: Image.Image, title: str, subtitle: str, updated_at: datetime | str | None) -> None:
        self.draw_glass_card(img, (self.MARGIN, self.MARGIN, self.width - self.MARGIN, 170), radius=28)
        d = ImageDraw.Draw(img)
        d.text((self.MARGIN + 28, self.MARGIN + 28), title, fill=self.COLORS["white"], font=self._font(52, True))
        d.text((self.MARGIN + 28, self.MARGIN + 92), subtitle, fill=self.COLORS["secondary"], font=self._font(28))
        ts = self._format_datetime(updated_at)
        tw = d.textbbox((0, 0), ts, font=self._font(24))[2]
        d.text((self.width - self.MARGIN - 28 - tw, self.MARGIN + 74), ts, fill=self.COLORS["secondary"], font=self._font(24))

    def _draw_dashboard_card(self, img: Image.Image, box: tuple[int, int, int, int], block: PerformanceBlock, glow: tuple[int, int, int, int]) -> None:
        x1, y1, x2, y2 = box
        self.draw_glow(img, ((x1 + x2) // 2, y1 + 120), (460, 180), glow, blur=38, alpha=86)
        self.draw_glass_card(img, box, radius=26)
        d = ImageDraw.Draw(img)
        d.text((x1 + 26, y1 + 24), block.title, fill=self.COLORS["white"], font=self._font(34, True))
        self.draw_glow(img, (x2 - 180, y1 + 44), (240, 80), glow, blur=24, alpha=30)
        self.draw_status_pill(d, x2 - 26, y1 + 22, block.badge, self._status_tone(block.badge))

        money_text = self.format_money(block.revenue)
        money_font = self._font(52, True)
        money_w = d.textbbox((0, 0), money_text, font=money_font)[2]
        money_x = x1 + ((x2 - x1 - money_w) // 2)
        self.draw_glow(img, ((x1 + x2) // 2, y1 + 142), (520, 130), glow, blur=36, alpha=52)
        d.text((money_x, y1 + 102), money_text, fill=self.COLORS["white"], font=money_font)

        secondary_font = self._font(20)
        left_secondary = f"Цель: {self.format_money(block.target)}"
        right_secondary = f"Осталось: {self.format_money(max(0, block.remaining))}"
        d.text((x1 + 26, y1 + 188), left_secondary, fill=self.COLORS["secondary"], font=secondary_font)
        right_w = d.textbbox((0, 0), right_secondary, font=secondary_font)[2]
        d.text((x2 - 26 - right_w, y1 + 188), right_secondary, fill=self.COLORS["secondary"], font=secondary_font)

        progress_box = (x1 + 26, y1 + 228, x2 - 26, y1 + 252)
        self.draw_glow(img, ((x1 + x2) // 2, y1 + 240), (600, 44), glow, blur=26, alpha=30)
        self.draw_progress_bar(d, progress_box, block.run_rate, self._status_tone(block.badge))

        stats = " • ".join(f"{m.value} {m.label}" for m in block.metrics[:2] if m.value)
        if stats:
            stats_w = d.textbbox((0, 0), stats, font=self._font(16))[2]
            d.text((x1 + ((x2 - x1 - stats_w) // 2), y1 + 276), stats, fill=self.COLORS["muted"], font=self._font(16))

    def draw_progress_bar(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], progress: float | None, tone: tuple[int, int, int, int]) -> None:
        x1, y1, x2, y2 = box
        draw.rounded_rectangle(box, radius=999, fill=(8, 14, 24, 255), outline=(255, 255, 255, 22), width=1)
        if progress is None:
            return
        pct = max(0.0, min(1.0, progress if progress <= 3 else progress / 100.0))
        fw = int((x2 - x1 - 4) * pct)
        if fw < 6:
            return
        fx2 = x1 + 2 + fw
        for i in range(max(1, fx2 - (x1 + 2))):
            k = i / max(1, fx2 - (x1 + 2) - 1)
            r = int(70 * (1 - k) + tone[0] * k)
            g = int(130 * (1 - k) + tone[1] * k)
            b = int(220 * (1 - k) + tone[2] * k)
            draw.line((x1 + 2 + i, y1 + 2, x1 + 2 + i, y2 - 2), fill=(r, g, b, 255))
        draw.rounded_rectangle((x1 + 2, y1 + 2, fx2, y2 - 2), radius=999, outline=(255, 255, 255, 34), width=1)

    def render_main_dashboard(self, data: MainDashboardData) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height), self.COLORS["bg"])
        self._draw_background(img)
        self._draw_header(img, data.title, data.status, data.updated_at)
        self._draw_dashboard_card(img, (self.MARGIN, 202, self.width - self.MARGIN, 548), data.shift, self._status_tone(data.shift.badge))
        self._draw_dashboard_card(img, (self.MARGIN, 580, self.width - self.MARGIN, self.height - self.MARGIN), data.decade, self._status_tone(data.decade.badge))
        return img.convert("RGB")

    def render_shift_summary(self, data: ShiftSummaryData) -> Image.Image:
        shift_block = PerformanceBlock(
            title="Итоги смены",
            badge=data.status_message,
            revenue=data.total,
            target=0,
            remaining=0,
            run_rate=None,
            metrics=[MetricItem("машин", str(next((m.value for m in data.metrics if "маш" in m.label.lower()), "0"))), MetricItem("средний чек", str(next((m.value for m in data.metrics if "чек" in m.label.lower()), "—")))],
        )
        decade_block = PerformanceBlock(
            title="Текущая декада",
            badge="Обновлено",
            revenue=data.decade_total,
            target=data.decade_total + max(0, data.decade_remaining),
            remaining=max(0, data.decade_remaining),
            run_rate=None,
            metrics=[MetricItem("осталось", self.format_money(max(0, data.decade_remaining))), MetricItem("статус", "закрыто")],
        )
        return self.render_main_dashboard(MainDashboardData(data.title, f"{data.date_label} • {data.duration_label}", data.date_label, shift_block, decade_block))

    def _draw_top_card(self, img: Image.Image, row: LeaderRow, box: tuple[int, int, int, int], tone: tuple[int, int, int, int], glow_alpha: int) -> None:
        x1, y1, x2, y2 = box
        self.draw_glow(img, ((x1 + x2) // 2, y1 + 120), (400, 210), tone, blur=40, alpha=glow_alpha)
        self.draw_glass_card(img, box, radius=26, accent=tone)
        d = ImageDraw.Draw(img)
        self.draw_rank_badge(d, (x1 + 24, y1 + 22), row.rank, tone)
        self.draw_avatar_or_initials(img, row, (x1 + 78, y1 + 100), 84)
        name_text, name_font = self.fit_text(d, row.name or "—", x2 - x1 - 150, 34, 24, True)
        d.text((x1 + 140, y1 + 80), name_text, fill=self.COLORS["white"], font=name_font)
        d.text((x1 + 24, y1 + 148), self.format_money(row.earnings), fill=self.COLORS["white"], font=self._font(58 if row.rank == 1 else 50, True))
        d.text((x1 + 24, y2 - 54), f"{row.shifts} смен • {row.cars} машин", fill=self.COLORS["secondary"], font=self._font(24))

    def render_leaderboard(self, data: LeaderboardData) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height), self.COLORS["bg"])
        self._draw_background(img)
        self._draw_header(img, data.title, data.subtitle, data.updated_at)

        rows = {r.rank: r for r in data.leaders}
        self._draw_top_card(img, rows.get(2, LeaderRow(2, "—", 0)), (76, 260, 468, 560), self.COLORS["silver"], 68)
        self._draw_top_card(img, rows.get(1, LeaderRow(1, "—", 0)), (504, 226, 896, 572), self.COLORS["gold"], 88)
        self._draw_top_card(img, rows.get(3, LeaderRow(3, "—", 0)), (932, 260, 1324, 560), self.COLORS["bronze"], 68)

        d = ImageDraw.Draw(img)
        y = 602
        for row in data.leaders[3:10]:
            self.draw_glass_card(img, (self.MARGIN, y, self.width - self.MARGIN, y + 74), radius=20)
            self.draw_rank_badge(d, (self.MARGIN + 16, y + 19), row.rank, self.COLORS["blue"])
            self.draw_avatar_or_initials(img, row, (self.MARGIN + 178, y + 37), 44)
            name_text, name_font = self.fit_text(d, row.name or "—", 520, 30, 22, True)
            d.text((self.MARGIN + 210, y + 13), name_text, fill=self.COLORS["white"], font=name_font)
            d.text((self.MARGIN + 210, y + 43), f"{row.shifts} смен • {row.cars} машин", fill=self.COLORS["muted"], font=self._font(20))
            money = self.format_money(row.earnings)
            mw = d.textbbox((0, 0), money, font=self._font(32, True))[2]
            d.text((self.width - self.MARGIN - 22 - mw, y + 22), money, fill=self.COLORS["white"], font=self._font(32, True))
            y += 84
        return img.convert("RGB")


def to_png_bytes(img: Image.Image, name: str) -> Any:
    from io import BytesIO

    out = BytesIO()
    out.name = name
    img.save(out, format="PNG")
    out.seek(0)
    return out
