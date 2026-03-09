from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


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
    cars: int | None = None
    income_per_hour: int | None = None
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
    BG = "#0C1119"
    CARD = "#141C27"
    CARD_2 = "#182231"
    BORDER = "#263243"
    TEXT = "#F4F8FF"
    MUTED = "#8EA3B9"
    CYAN = "#54B8FF"
    GOOD = "#46D487"
    WARN = "#E8A64D"
    BAD = "#E16060"
    _avatar_cache: dict[tuple[str, int], Image.Image] = {}

    def __init__(self, width: int = WIDTH, height: int = HEIGHT) -> None:
        self.width = width
        self.height = height

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

    def _format_money(self, value: Any, zero_default: str = "0 ₽") -> str:
        n = self._safe_int(value, default=0)
        return f"{n:,} ₽".replace(",", " ") if n or zero_default == "0 ₽" else zero_default

    def _draw_card(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 24, fill: str | None = None, border: str | None = None):
        x1, y1, x2, y2 = box
        draw.rounded_rectangle((x1 + 2, y1 + 4, x2 + 2, y2 + 4), radius=radius, fill="#090E14")
        draw.rounded_rectangle(box, radius=radius, fill=fill or self.CARD, outline=border or self.BORDER, width=2)

    def _draw_header(self, draw: ImageDraw.ImageDraw, title: str, subtitle: str, updated_at: datetime | str | None):
        self._draw_card(draw, (36, 24, self.width - 36, 140), radius=24)
        draw.text((64, 50), title, fill=self.TEXT, font=self._font(44, True))
        draw.text((64, 98), subtitle, fill=self.MUTED, font=self._font(24))
        ts = updated_at.strftime("%d.%m.%Y %H:%M") if isinstance(updated_at, datetime) else str(updated_at or "—")
        tw = draw.textbbox((0, 0), ts, font=self._font(22))[2]
        draw.text((self.width - 64 - tw, 74), ts, fill=self.MUTED, font=self._font(22))

    def _runrate_color(self, run_rate: float | None) -> str:
        if run_rate is None:
            return self.MUTED
        pct = run_rate * 100 if run_rate <= 3 else run_rate
        if pct >= 100:
            return self.GOOD
        if pct >= 90:
            return self.WARN
        return self.BAD

    def _badge(self, draw: ImageDraw.ImageDraw, x_right: int, y: int, text: str, color: str):
        if not text:
            return
        w = draw.textbbox((0, 0), text, font=self._font(20, True))[2] + 28
        x = x_right - w
        draw.rounded_rectangle((x, y, x + w, y + 34), radius=16, fill="#1B2A39", outline=self.BORDER, width=1)
        draw.text((x + 14, y + 7), text, fill=color, font=self._font(20, True))

    def _progress_bar(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], run_rate: float | None):
        x1, y1, x2, y2 = box
        draw.rounded_rectangle(box, radius=8, fill="#0B1119", outline=self.BORDER, width=1)
        if run_rate is None:
            return
        pct = max(0.0, min(1.0, run_rate if run_rate <= 3 else run_rate / 100.0))
        fw = int((x2 - x1 - 2) * pct)
        if fw > 0:
            draw.rounded_rectangle((x1 + 1, y1 + 1, x1 + 1 + fw, y2 - 1), radius=8, fill=self._runrate_color(run_rate))

    def _avatar_placeholder(self, size: int, initials: str = "?") -> Image.Image:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((0, 0, size - 1, size - 1), fill="#213043", outline="#334B63", width=2)
        text = (initials or "?")[:2].upper()
        b = d.textbbox((0, 0), text, font=self._font(max(14, size // 3), True))
        d.text(((size - (b[2] - b[0])) / 2, (size - (b[3] - b[1])) / 2), text, fill="#D9E6F7", font=self._font(max(14, size // 3), True))
        return img

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
        return self._avatar_placeholder(size, initials)

    def _draw_perf_card(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], block: PerformanceBlock):
        x1, y1, x2, y2 = box
        self._draw_card(draw, box, radius=24)
        run_color = self._runrate_color(block.run_rate)
        self._badge(draw, x2 - 26, y1 + 20, block.badge, run_color if block.badge else self.CYAN)
        draw.text((x1 + 28, y1 + 24), block.title, fill=self.TEXT, font=self._font(32, True))
        draw.text((x1 + 28, y1 + 78), self._format_money(block.revenue), fill=self.TEXT, font=self._font(64, True))

        draw.text((x1 + 30, y1 + 156), f"Цель: {self._format_money(block.target)}", fill=self.MUTED, font=self._font(24))
        draw.text((x1 + 30, y1 + 186), f"Осталось: {self._format_money(max(self._safe_int(block.remaining), 0))}", fill=self.MUTED, font=self._font(24))
        rr = "—" if block.run_rate is None else f"{int(round((block.run_rate * 100) if block.run_rate <= 3 else block.run_rate))}%"
        draw.text((x1 + 30, y1 + 216), "Темп", fill=self.MUTED, font=self._font(24))
        draw.text((x1 + 110, y1 + 208), rr, fill=run_color, font=self._font(36, True))
        self._progress_bar(draw, (x1 + 28, y1 + 254, x2 - 28, y1 + 276), block.run_rate)

        metrics = (block.metrics or [])[:4]
        if not metrics:
            return
        gap = 12
        cw = (x2 - x1 - 56 - gap) // 2
        ch = 86
        for i, item in enumerate(metrics):
            c = i % 2
            r = i // 2
            cx = x1 + 28 + c * (cw + gap)
            cy = y1 + 294 + r * (ch + gap)
            self._draw_card(draw, (cx, cy, cx + cw, cy + ch), radius=14, fill=self.CARD_2)
            draw.text((cx + 12, cy + 14), str(item.value or "—"), fill=self.TEXT, font=self._font(28, True))
            draw.text((cx + 12, cy + 50), str(item.label or "—"), fill=self.MUTED, font=self._font(18))

    def render_main_dashboard(self, data: MainDashboardData) -> Image.Image:
        img = Image.new("RGB", (self.width, self.height), self.BG)
        draw = ImageDraw.Draw(img)
        self._draw_header(draw, data.title, data.status, data.updated_at)
        self._draw_perf_card(draw, (36, 164, self.width - 36, 528), data.shift)
        self._draw_perf_card(draw, (36, 548, self.width - 36, self.height - 28), data.decade)
        return img

    def render_shift_summary(self, data: ShiftSummaryData) -> Image.Image:
        img = Image.new("RGB", (self.width, self.height), self.BG)
        draw = ImageDraw.Draw(img)
        self._draw_header(draw, data.title, f"{data.date_label} • {data.duration_label}", data.date_label)
        self._draw_card(draw, (36, 164, self.width - 36, 398), radius=24)
        draw.text((74, 208), self._format_money(data.total), fill=self.TEXT, font=self._font(96, True))

        status = (data.status_message or "Итог смены").strip()
        lc = status.lower()
        status_color = self.GOOD if ("выполн" in lc or "+" in status) else self.BAD if ("отстав" in lc or "-" in status) else self.WARN
        self._draw_card(draw, (74, 318, 820, 378), radius=16, fill="#1A2432")
        draw.text((94, 334), status, fill=status_color, font=self._font(30, True))

        self._draw_card(draw, (36, 416, self.width - 36, 846), radius=24)
        metrics = (data.metrics or [])[:6]
        gap = 14
        cols = 3
        cw = (self.width - 72 - 40 - gap * (cols - 1)) // cols
        ch = 124
        for i, item in enumerate(metrics):
            col = i % cols
            row = i // cols
            x = 56 + col * (cw + gap)
            y = 448 + row * (ch + gap)
            self._draw_card(draw, (x, y, x + cw, y + ch), radius=16, fill=self.CARD_2)
            draw.text((x + 14, y + 18), str(item.value or "—"), fill=self.TEXT, font=self._font(34, True))
            draw.text((x + 14, y + 72), str(item.label or "—"), fill=self.MUTED, font=self._font(20))

        self._draw_card(draw, (36, 864, self.width - 36, self.height - 28), radius=18, fill="#111924")
        footer = f"В декаде: {self._format_money(data.decade_total)}   •   До цели: {self._format_money(max(0, self._safe_int(data.decade_remaining)))}"
        draw.text((62, 895), footer, fill=self.MUTED, font=self._font(28, True))
        return img

    def render_leaderboard(self, data: LeaderboardData) -> Image.Image:
        img = Image.new("RGB", (self.width, self.height), self.BG)
        draw = ImageDraw.Draw(img)
        self._draw_header(draw, data.title, data.subtitle, data.updated_at)

        accents = {1: "#BFA05F", 2: "#8EA6C0", 3: "#9D7657"}
        slots = {
            2: (68, 208, 466, 504),
            1: (500, 182, 900, 530),
            3: (934, 208, 1332, 504),
        }
        rows = {row.rank: row for row in data.leaders[:3]}
        for rank in (2, 1, 3):
            row = rows.get(rank)
            if not row:
                continue
            x1, y1, x2, y2 = slots[rank]
            accent = accents[rank]
            self._draw_card(draw, (x1, y1, x2, y2), radius=24)
            draw.rounded_rectangle((x1 + 2, y1 + 2, x2 - 2, y1 + 16), radius=10, fill=accent)
            draw.text((x1 + 18, y1 + 22), f"#{rank}", fill=accent, font=self._font(24, True))
            av_size = 98 if rank == 1 else 86
            avatar = self._resolve_avatar(row, av_size)
            img.paste(avatar, (x1 + 22, y1 + 58), avatar)
            draw.text((x1 + 132, y1 + 68), (row.name or "—")[:20], fill=self.TEXT, font=self._font(34 if rank == 1 else 30, True))
            draw.text((x1 + 24, y1 + 180), self._format_money(row.earnings), fill=self.TEXT, font=self._font(56 if rank == 1 else 46, True))

            self._draw_card(draw, (x1 + 22, y2 - 100, x1 + (x2 - x1) // 2 - 8, y2 - 20), radius=12, fill="#182232")
            self._draw_card(draw, (x1 + (x2 - x1) // 2 + 8, y2 - 100, x2 - 22, y2 - 20), radius=12, fill="#182232")
            draw.text((x1 + 36, y2 - 90), "Смен", fill=self.MUTED, font=self._font(18))
            draw.text((x1 + 36, y2 - 58), str(self._safe_int(row.cars, 0)), fill=self.TEXT, font=self._font(28, True))
            draw.text((x1 + (x2 - x1) // 2 + 22, y2 - 90), "₽/ч", fill=self.MUTED, font=self._font(18))
            iph = self._safe_int(row.income_per_hour, 0)
            draw.text((x1 + (x2 - x1) // 2 + 22, y2 - 58), f"{iph:,}".replace(",", " "), fill=self.TEXT, font=self._font(28, True))

        y = 546
        for row in data.leaders[3:11]:
            self._draw_card(draw, (52, y, self.width - 52, y + 66), radius=16, fill="#131D2A")
            draw.text((72, y + 20), f"#{row.rank}", fill=self.CYAN, font=self._font(24, True))
            avatar = self._resolve_avatar(row, 40)
            img.paste(avatar, (156, y + 13), avatar)
            draw.text((206, y + 20), (row.name or "—")[:28], fill=self.TEXT, font=self._font(24, True))
            draw.text((658, y + 20), f"{self._safe_int(row.cars, 0)} смен", fill=self.MUTED, font=self._font(22))
            iph = self._safe_int(row.income_per_hour, 0)
            draw.text((880, y + 20), f"{iph:,} ₽/ч".replace(",", " "), fill=self.MUTED, font=self._font(22))
            draw.text((1110, y + 18), self._format_money(row.earnings), fill=self.TEXT, font=self._font(28, True))
            y += 76
        return img


def to_png_bytes(img: Image.Image, name: str) -> Any:
    from io import BytesIO

    out = BytesIO()
    out.name = name
    img.save(out, format="PNG")
    out.seek(0)
    return out
