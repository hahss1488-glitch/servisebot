from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


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
    HEIGHT = 900
    BG = "#0F1722"
    CARD = "#16202B"
    BORDER = "#253242"
    TEXT = "#F3F7FF"
    MUTED = "#9BACBF"
    ACCENT = "#35B8FF"
    GOOD = "#3AD07A"
    WARN = "#F2A546"
    BAD = "#E96363"

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

    def _new_canvas(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        img = Image.new("RGB", (self.width, self.height), self.BG)
        return img, ImageDraw.Draw(img)

    def draw_card(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 24):
        x1, y1, x2, y2 = box
        draw.rounded_rectangle((x1 + 3, y1 + 5, x2 + 3, y2 + 5), radius=radius, fill="#0A1119")
        draw.rounded_rectangle(box, radius=radius, fill=self.CARD, outline=self.BORDER, width=2)

    def draw_header(self, draw: ImageDraw.ImageDraw, title: str, status: str, updated_at: datetime | str | None):
        self.draw_card(draw, (40, 30, self.width - 40, 150), radius=28)
        draw.text((72, 56), title, fill=self.TEXT, font=self._font(52, True))
        draw.text((72, 108), status, fill=self.MUTED, font=self._font(26, False))
        ts = updated_at.strftime("%d.%m.%Y %H:%M") if isinstance(updated_at, datetime) else (str(updated_at or "—"))
        tw = draw.textbbox((0, 0), ts, font=self._font(24))[2]
        draw.text((self.width - 72 - tw, 80), ts, fill=self.MUTED, font=self._font(24))
        draw.ellipse((54, 115, 66, 127), fill=self.GOOD)

    def _runrate_color(self, run_rate: float | None) -> str:
        if run_rate is None:
            return self.MUTED
        pct = run_rate * 100 if run_rate <= 3 else run_rate
        if pct >= 100:
            return self.GOOD
        if pct >= 90:
            return self.WARN
        return self.BAD

    def draw_badge(self, draw: ImageDraw.ImageDraw, x: int, y: int, text: str):
        if not text:
            return
        w = draw.textbbox((0, 0), text, font=self._font(22, True))[2] + 28
        draw.rounded_rectangle((x, y, x + w, y + 36), radius=18, fill="#1F3041", outline=self.BORDER)
        draw.text((x + 14, y + 7), text, fill=self.ACCENT, font=self._font(22, True))

    def draw_progress_bar(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], run_rate: float | None):
        x1, y1, x2, y2 = box
        draw.rounded_rectangle(box, radius=10, fill="#0D141D", outline=self.BORDER)
        if run_rate is None:
            return
        pct = max(0, min(1, (run_rate if run_rate <= 3 else run_rate / 100)))
        fw = int((x2 - x1) * pct)
        if fw > 0:
            draw.rounded_rectangle((x1, y1, x1 + fw, y2), radius=10, fill=self._runrate_color(run_rate))

    def _draw_performance_section(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], block: PerformanceBlock, grid_cols: int):
        self.draw_card(draw, box)
        x1, y1, x2, y2 = box
        draw.text((x1 + 28, y1 + 22), block.title, fill=self.TEXT, font=self._font(34, True))
        self.draw_badge(draw, x2 - 260, y1 + 20, block.badge)
        draw.text((x1 + 28, y1 + 78), f"{block.revenue:,} ₽".replace(",", " "), fill=self.TEXT, font=self._font(72, True))
        draw.text((x1 + 30, y1 + 168), f"Цель: {block.target:,} ₽".replace(",", " "), fill=self.MUTED, font=self._font(28))
        draw.text((x1 + 30, y1 + 202), f"Осталось: {max(block.remaining, 0):,} ₽".replace(",", " "), fill=self.MUTED, font=self._font(28))
        rr = "—" if block.run_rate is None else f"{int(round((block.run_rate * 100) if block.run_rate <= 3 else block.run_rate))}%"
        color = self._runrate_color(block.run_rate)
        draw.text((x1 + 30, y1 + 242), "Run rate", fill=self.MUTED, font=self._font(24))
        draw.text((x1 + 160, y1 + 232), rr, fill=color, font=self._font(44, True))
        self.draw_progress_bar(draw, (x1 + 30, y1 + 286, x2 - 30, y1 + 312), block.run_rate)

        metrics = block.metrics[:6]
        if not metrics:
            return
        gx1, gy1 = x1 + 30, y1 + 336
        gap = 14
        rows = (len(metrics) + grid_cols - 1) // grid_cols
        cw = (x2 - x1 - 60 - gap * (grid_cols - 1)) // grid_cols
        ch = min(96, max(72, (y2 - gy1 - gap * max(0, rows - 1)) // max(1, rows)))
        for i, item in enumerate(metrics):
            c, r = i % grid_cols, i // grid_cols
            cx, cy = gx1 + c * (cw + gap), gy1 + r * (ch + gap)
            self.draw_card(draw, (cx, cy, cx + cw, cy + ch), radius=16)
            draw.text((cx + 12, cy + 14), item.value, fill=self.TEXT, font=self._font(30, True))
            draw.text((cx + 12, cy + 50), item.label, fill=self.MUTED, font=self._font(20))

    def render_main_dashboard(self, data: MainDashboardData) -> Image.Image:
        img, draw = self._new_canvas()
        self.draw_header(draw, data.title, data.status, data.updated_at)
        self._draw_performance_section(draw, (40, 170, self.width - 40, 510), data.shift, grid_cols=2)
        self._draw_performance_section(draw, (40, 530, self.width - 40, self.height - 30), data.decade, grid_cols=3)
        return img

    def render_shift_summary(self, data: ShiftSummaryData) -> Image.Image:
        img, draw = self._new_canvas()
        self.draw_header(draw, data.title, f"{data.date_label} • {data.duration_label}", data.date_label)
        self.draw_card(draw, (40, 170, self.width - 40, 530))
        draw.text((90, 230), f"{data.total:,} ₽".replace(",", " "), fill=self.TEXT, font=self._font(104, True))
        draw.text((90, 355), data.status_message, fill=self.ACCENT, font=self._font(34, True))
        self.draw_card(draw, (40, 550, self.width - 40, self.height - 30))
        for i, item in enumerate(data.metrics[:6]):
            col = i % 3
            row = i // 3
            x = 70 + col * 430
            y = 580 + row * 130
            self.draw_card(draw, (x, y, x + 390, y + 110), radius=16)
            draw.text((x + 14, y + 16), item.value, fill=self.TEXT, font=self._font(34, True))
            draw.text((x + 14, y + 62), item.label, fill=self.MUTED, font=self._font(20))
        draw.text((70, self.height - 70), f"В декаде: {data.decade_total:,} ₽ • До цели: {data.decade_remaining:,} ₽".replace(",", " "), fill=self.MUTED, font=self._font(24))
        return img

    def render_leaderboard(self, data: LeaderboardData) -> Image.Image:
        img, draw = self._new_canvas()
        self.draw_header(draw, data.title, data.subtitle, data.updated_at)
        top3 = data.leaders[:3]
        cards = [(60, 190, 460, 470), (500, 170, 900, 490), (940, 190, 1340, 470)]
        for idx, row in enumerate(top3):
            x1, y1, x2, y2 = cards[idx]
            self.draw_card(draw, (x1, y1, x2, y2), 22)
            draw.text((x1 + 18, y1 + 16), f"#{row.rank}", fill=self.ACCENT, font=self._font(30, True))
            draw.text((x1 + 18, y1 + 58), row.name[:18], fill=self.TEXT, font=self._font(32, True))
            draw.text((x1 + 18, y1 + 104), f"{row.earnings:,} ₽".replace(",", " "), fill=self.TEXT, font=self._font(44, True))

        y = 510
        for row in data.leaders[3:11]:
            self.draw_card(draw, (60, y, 1340, y + 48), radius=14)
            draw.text((76, y + 10), f"#{row.rank}", fill=self.ACCENT, font=self._font(24, True))
            draw.text((170, y + 10), row.name[:24], fill=self.TEXT, font=self._font(24, True))
            draw.text((760, y + 10), f"{row.cars or 0}", fill=self.MUTED, font=self._font(22))
            iph = "—" if row.income_per_hour is None else f"{row.income_per_hour} ₽/ч"
            draw.text((880, y + 10), iph, fill=self.MUTED, font=self._font(22))
            draw.text((1140, y + 10), f"{row.earnings:,} ₽".replace(",", " "), fill=self.TEXT, font=self._font(24, True))
            y += 56
        return img


def to_png_bytes(img: Image.Image, name: str) -> Any:
    from io import BytesIO

    out = BytesIO()
    out.name = name
    img.save(out, format="PNG")
    out.seek(0)
    return out
