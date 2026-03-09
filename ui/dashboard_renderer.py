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
    """Premium dark analytics renderer.

    Composition uses a strict 1600x900 canvas with a 48 px outer margin and
    24 px internal spacing. Main numbers dominate visual hierarchy, while cards,
    badges and list rows reuse the same primitives for consistent style.
    """

    WIDTH = 1600
    HEIGHT = 900
    MARGIN = 48
    GAP = 24

    COLORS = {
        "bg": (7, 17, 31, 255),
        "bg_deep": (11, 18, 32, 255),
        "card": (15, 27, 45, 255),
        "surface": (19, 34, 56, 255),
        "text": (243, 247, 255, 255),
        "text_secondary": (159, 176, 199, 255),
        "text_muted": (111, 129, 155, 255),
        "border": (255, 255, 255, 30),
        "shadow": (1, 6, 14, 180),
        "success": (91, 231, 169, 255),
        "warning": (246, 199, 96, 255),
        "danger": (255, 107, 122, 255),
        "info": (111, 168, 255, 255),
        "gold": (239, 198, 110, 255),
        "silver": (176, 193, 214, 255),
        "bronze": (208, 154, 104, 255),
    }

    _avatar_cache: dict[tuple[str, int], Image.Image] = {}

    def __init__(self, width: int = WIDTH, height: int = HEIGHT) -> None:
        self.width = width
        self.height = height

    @staticmethod
    @lru_cache(maxsize=256)
    def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
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
        return f"{self._safe_int(value):,} ₽".replace(",", " ")

    def _tone_for_status(self, text: str) -> tuple[int, int, int, int]:
        t = (text or "").lower()
        if "выполн" in t or "лидер" in t or "топ" in t:
            return self.COLORS["success"]
        if "почти" in t or "близко" in t:
            return self.COLORS["warning"]
        if "до цели" in t or "отстав" in t:
            return self.COLORS["danger"]
        return self.COLORS["info"]

    def _draw_background(self, image: Image.Image) -> None:
        draw = ImageDraw.Draw(image)
        for y in range(self.height):
            p = y / max(self.height - 1, 1)
            r = int(self.COLORS["bg"][0] * (1 - p) + self.COLORS["bg_deep"][0] * p)
            g = int(self.COLORS["bg"][1] * (1 - p) + self.COLORS["bg_deep"][1] * p)
            b = int(self.COLORS["bg"][2] * (1 - p) + self.COLORS["bg_deep"][2] * p)
            draw.line((0, y, self.width, y), fill=(r, g, b, 255))

    def draw_rounded_card(self, image: Image.Image, box: tuple[int, int, int, int], radius: int = 26, surface: bool = False) -> None:
        x1, y1, x2, y2 = box
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((x1 + 2, y1 + 8, x2 + 2, y2 + 10), radius=radius, fill=self.COLORS["shadow"])
        fill = self.COLORS["surface"] if surface else self.COLORS["card"]
        d.rounded_rectangle(box, radius=radius, fill=fill, outline=self.COLORS["border"], width=1)
        image.alpha_composite(layer)

    def draw_badge(self, draw: ImageDraw.ImageDraw, right_x: int, y: int, text: str, tone: tuple[int, int, int, int]) -> None:
        font = self._font(24, True)
        text_w = draw.textbbox((0, 0), text, font=font)[2]
        h = 44
        x = right_x - text_w - 34
        draw.rounded_rectangle((x, y, right_x, y + h), radius=999, fill=(16, 27, 43, 240), outline=(255, 255, 255, 28), width=1)
        draw.text((x + 16, y + 10), text, fill=tone, font=font)

    def draw_avatar_initials_circle(self, image: Image.Image, row: LeaderRow, center: tuple[int, int], size: int, tone: tuple[int, int, int, int] | None = None) -> None:
        avatar = self._resolve_avatar(row, size, tone=tone)
        image.alpha_composite(avatar, (center[0] - size // 2, center[1] - size // 2))

    def draw_progress_bar(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], progress: float | None, tone: tuple[int, int, int, int]) -> None:
        x1, y1, x2, y2 = box
        draw.rounded_rectangle(box, radius=999, fill=(8, 16, 30, 255), outline=(255, 255, 255, 26), width=1)
        if progress is None:
            return
        p = max(0.0, min(1.0, progress if progress <= 3 else progress / 100.0))
        fill_w = int((x2 - x1 - 4) * p)
        if fill_w < 8:
            return
        fx2 = x1 + 2 + fill_w
        draw.rounded_rectangle((x1 + 2, y1 + 2, fx2, y2 - 2), radius=999, fill=tone)

    def draw_main_metric_block(self, image: Image.Image, box: tuple[int, int, int, int], block: PerformanceBlock) -> None:
        x1, y1, x2, y2 = box
        tone = self._tone_for_status(block.badge)
        self.draw_rounded_card(image, box, radius=28)
        glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((x1 + 390, y1 + 92, x2 - 390, y1 + 260), fill=(tone[0], tone[1], tone[2], 52))
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(36)))

        draw = ImageDraw.Draw(image)
        draw.text((x1 + 32, y1 + 30), block.title, fill=self.COLORS["text"], font=self._font(34, True))
        self.draw_badge(draw, x2 - 32, y1 + 28, block.badge, tone)

        amount = self.format_money(block.revenue)
        amount_font = self._font(82, True)
        amount_w = draw.textbbox((0, 0), amount, font=amount_font)[2]
        draw.text((x1 + (x2 - x1 - amount_w) // 2, y1 + 106), amount, fill=self.COLORS["text"], font=amount_font)

        cars = next((m.value for m in block.metrics if "маш" in m.label.lower()), "—")
        avg = next((m.value for m in block.metrics if "чек" in m.label.lower()), "—")
        info_text = f"{cars} машин • средний чек {avg}"
        info_w = draw.textbbox((0, 0), info_text, font=self._font(27))[2]
        draw.text((x1 + (x2 - x1 - info_w) // 2, y1 + 212), info_text, fill=self.COLORS["text_secondary"], font=self._font(27))

        self.draw_progress_bar(draw, (x1 + 34, y1 + 268, x2 - 34, y1 + 306), block.run_rate, tone)

        labels = [
            ("Цель", self.format_money(block.target), self.COLORS["text_secondary"]),
            ("Осталось", self.format_money(max(block.remaining, 0)), tone if block.remaining > 0 else self.COLORS["success"]),
            ("Выполнение", f"{(max(0.0, min(1.0, (block.run_rate or 0.0 if block.target else 0.0 if block.run_rate is None else block.run_rate)) if block.run_rate is not None else 0.0) * 100):.0f}%", self.COLORS["text_secondary"]),
        ]
        col_w = (x2 - x1 - 64) // 3
        for i, (label, value, color) in enumerate(labels):
            xx = x1 + 32 + i * col_w
            draw.text((xx, y1 + 326), label, fill=self.COLORS["text_muted"], font=self._font(20))
            draw.text((xx, y1 + 354), value, fill=color, font=self._font(30, True))

    def draw_small_kpi_card(self, image: Image.Image, box: tuple[int, int, int, int], title: str, value: str, tone: tuple[int, int, int, int] | None = None) -> None:
        self.draw_rounded_card(image, box, radius=24, surface=True)
        draw = ImageDraw.Draw(image)
        x1, y1, x2, _ = box
        draw.text((x1 + 24, y1 + 22), title, fill=self.COLORS["text_muted"], font=self._font(20))
        draw.text((x1 + 24, y1 + 54), value, fill=tone or self.COLORS["text"], font=self._font(38, True))
        if tone:
            draw.rounded_rectangle((x1 + 24, y1 + 98, x2 - 24, y1 + 103), radius=999, fill=(tone[0], tone[1], tone[2], 130))

    def draw_leaderboard_row(self, image: Image.Image, box: tuple[int, int, int, int], row: LeaderRow, highlight: bool = False) -> None:
        self.draw_rounded_card(image, box, radius=22, surface=highlight)
        draw = ImageDraw.Draw(image)
        x1, y1, x2, _ = box
        if highlight:
            draw.rounded_rectangle((x1 + 10, y1 + 10, x1 + 15, y1 + 88), radius=6, fill=self.COLORS["info"])
        draw.text((x1 + 30, y1 + 26), f"#{row.rank}", fill=self.COLORS["text_secondary"], font=self._font(30, True))
        self.draw_avatar_initials_circle(image, row, (x1 + 148, y1 + 48), 64)
        draw.text((x1 + 194, y1 + 18), row.name, fill=self.COLORS["text"], font=self._font(31, True))
        draw.text((x1 + 194, y1 + 56), f"{row.shifts} смен • {row.cars} машин", fill=self.COLORS["text_muted"], font=self._font(22))
        money = self.format_money(row.earnings)
        mw = draw.textbbox((0, 0), money, font=self._font(36, True))[2]
        draw.text((x2 - mw - 30, y1 + 30), money, fill=self.COLORS["text"], font=self._font(36, True))
        if highlight:
            self.draw_badge(draw, x2 - 30, y1 + 14, "Вы", self.COLORS["info"])

    def draw_top_podium_card(
        self,
        image: Image.Image,
        box: tuple[int, int, int, int],
        row: LeaderRow,
        rank_tone: tuple[int, int, int, int],
        badge_text: str,
        big: bool = False,
    ) -> None:
        self.draw_rounded_card(image, box, radius=26)
        x1, y1, x2, _ = box
        draw = ImageDraw.Draw(image)
        draw.text((x1 + 24, y1 + 20), f"#{row.rank}", fill=rank_tone, font=self._font(34 if big else 30, True))
        self.draw_avatar_initials_circle(image, row, (x1 + 66, y1 + 96), 76 if big else 68, tone=rank_tone)
        draw.text((x1 + 118, y1 + 72), row.name, fill=self.COLORS["text"], font=self._font(30 if big else 27, True))
        money_font = self._font(56 if big else 46, True)
        draw.text((x1 + 24, y1 + 148), self.format_money(row.earnings), fill=self.COLORS["text"], font=money_font)
        draw.text((x1 + 24, y1 + 226), f"{row.shifts} смен • {row.cars} машин", fill=self.COLORS["text_secondary"], font=self._font(24))
        self.draw_badge(draw, x2 - 24, y1 + 18, badge_text, rank_tone)

    def _draw_header(self, image: Image.Image, title: str, subtitle: str, updated: datetime | str | None, status: str) -> None:
        box = (self.MARGIN, self.MARGIN, self.width - self.MARGIN, 178)
        self.draw_rounded_card(image, box, radius=28)
        draw = ImageDraw.Draw(image)
        draw.text((box[0] + 30, box[1] + 30), title, fill=self.COLORS["text"], font=self._font(52, True))
        draw.text((box[0] + 30, box[1] + 94), subtitle, fill=self.COLORS["text_secondary"], font=self._font(29))
        timestamp = updated.strftime("%d.%m.%Y %H:%M") if isinstance(updated, datetime) else str(updated or "—")
        tw = draw.textbbox((0, 0), timestamp, font=self._font(24))[2]
        draw.text((box[2] - 32 - tw, box[1] + 34), timestamp, fill=self.COLORS["text_secondary"], font=self._font(24))
        self.draw_badge(draw, box[2] - 30, box[1] + 84, status, self._tone_for_status(status))

    def render_main_dashboard(self, data: MainDashboardData) -> Image.Image:
        image = Image.new("RGBA", (self.width, self.height), self.COLORS["bg"])
        self._draw_background(image)
        subtitle = f"{data.status}"
        self._draw_header(image, "Смена закрыта", subtitle, data.updated_at, "Закрыто")

        main_box = (self.MARGIN, 202, self.width - self.MARGIN, 592)
        self.draw_main_metric_block(image, main_box, data.shift)

        row_y = 616
        half_w = (self.width - self.MARGIN * 2 - self.GAP) // 2
        left_box = (self.MARGIN, row_y, self.MARGIN + half_w, 782)
        right_box = (self.MARGIN + half_w + self.GAP, row_y, self.width - self.MARGIN, 782)
        self.draw_rounded_card(image, left_box, radius=24)
        self.draw_rounded_card(image, right_box, radius=24)

        draw = ImageDraw.Draw(image)
        draw.text((left_box[0] + 24, left_box[1] + 20), "Текущая декада", fill=self.COLORS["text"], font=self._font(30, True))
        draw.text((left_box[0] + 24, left_box[1] + 56), "1–10 марта", fill=self.COLORS["text_muted"], font=self._font(22))
        draw.text((left_box[0] + 24, left_box[1] + 92), self.format_money(data.decade.revenue), fill=self.COLORS["text"], font=self._font(52, True))
        self.draw_progress_bar(draw, (left_box[0] + 24, left_box[1] + 158, left_box[2] - 24, left_box[1] + 188), data.decade.run_rate, self.COLORS["info"])
        draw.text((left_box[0] + 24, left_box[1] + 196), f"Цель {self.format_money(data.decade.target)} • Осталось {self.format_money(data.decade.remaining)}", fill=self.COLORS["text_secondary"], font=self._font(20))

        rank_value = next((m.value for m in data.decade.metrics if "пози" in m.label.lower()), "#1")
        rank_info = next((m.value for m in data.decade.metrics if "участ" in m.label.lower()), "из 12 участников")
        delta = next((m.value for m in data.decade.metrics if "дельта" in m.label.lower()), "+1 с прошлого обновления")
        draw.text((right_box[0] + 24, right_box[1] + 20), "Позиция в рейтинге", fill=self.COLORS["text"], font=self._font(30, True))
        draw.text((right_box[0] + 24, right_box[1] + 92), rank_value, fill=self.COLORS["success"], font=self._font(76, True))
        draw.text((right_box[0] + 24, right_box[1] + 172), rank_info, fill=self.COLORS["text_secondary"], font=self._font(24))
        draw.text((right_box[0] + 24, right_box[1] + 202), delta, fill=self.COLORS["info"], font=self._font(22, True))
        self.draw_badge(draw, right_box[2] - 24, right_box[1] + 20, "Лидер", self.COLORS["success"])

        kpi_titles = ["Машин", "Средний чек", "Смен за декаду", "Осталось до цели"]
        metrics = {m.label.lower(): m.value for m in data.shift.metrics + data.decade.metrics}
        kpi_values = [
            str(metrics.get("машин", "131")),
            str(metrics.get("средний чек", "336 ₽")),
            str(metrics.get("смен", "8")),
            self.format_money(data.shift.remaining),
        ]
        kpi_tones = [None, None, self.COLORS["info"], self._tone_for_status(data.shift.badge)]
        kpi_w = (self.width - self.MARGIN * 2 - self.GAP * 3) // 4
        y = 802
        for i in range(4):
            box = (self.MARGIN + i * (kpi_w + self.GAP), y, self.MARGIN + i * (kpi_w + self.GAP) + kpi_w, 888)
            self.draw_small_kpi_card(image, box, kpi_titles[i], kpi_values[i], kpi_tones[i])

        return image.convert("RGB")

    def render_shift_summary(self, data: ShiftSummaryData) -> Image.Image:
        cars = next((m.value for m in data.metrics if "маш" in m.label.lower()), "131")
        avg = next((m.value for m in data.metrics if "чек" in m.label.lower()), "336 ₽")
        target = data.total + max(data.decade_remaining, 0)
        run_rate = data.total / max(target, 1)
        shift = PerformanceBlock(
            title="Итоги смены",
            badge=data.status_message,
            revenue=data.total,
            target=target,
            remaining=max(data.decade_remaining, 0),
            run_rate=run_rate,
            metrics=[MetricItem("машин", cars), MetricItem("средний чек", avg), MetricItem("смен", "8")],
        )
        decade = PerformanceBlock(
            title="Текущая декада",
            badge="Обновлено",
            revenue=data.decade_total,
            target=target,
            remaining=max(data.decade_remaining, 0),
            run_rate=run_rate,
            metrics=[MetricItem("позиция", "#1"), MetricItem("участники", "из 12 участников"), MetricItem("дельта", "+1 с прошлого обновления")],
        )
        return self.render_main_dashboard(MainDashboardData(data.title, f"{data.date_label} • итог за день", data.date_label, shift, decade))

    def render_leaderboard(self, data: LeaderboardData) -> Image.Image:
        image = Image.new("RGBA", (self.width, self.height), self.COLORS["bg"])
        self._draw_background(image)
        self._draw_header(image, "Лидерборд", data.subtitle, data.updated_at, "Обновлено")

        top = {r.rank: r for r in data.leaders[:3]}
        self.draw_top_podium_card(image, (self.MARGIN + 120, 220, 620, 500), top.get(2, LeaderRow(2, "—", 0)), self.COLORS["silver"], "Стабильно")
        self.draw_top_podium_card(image, (560, 196, 1040, 532), top.get(1, LeaderRow(1, "—", 0)), self.COLORS["gold"], "Лидер", big=True)
        self.draw_top_podium_card(image, (980, 230, self.width - self.MARGIN - 120, 500), top.get(3, LeaderRow(3, "—", 0)), self.COLORS["bronze"], "Топ-3")

        y = 540
        for row in data.leaders[3:8]:
            is_me = bool(data.highlight_name and row.name.strip().lower() == data.highlight_name.strip().lower())
            self.draw_leaderboard_row(image, (self.MARGIN, y, self.width - self.MARGIN, y + 98), row, highlight=is_me)
            y += 108

        return image.convert("RGB")

    def _resolve_avatar(self, row: LeaderRow, size: int, tone: tuple[int, int, int, int] | None = None) -> Image.Image:
        if row.avatar_path:
            key = (row.avatar_path, size)
            cached = self._avatar_cache.get(key)
            if cached is not None:
                return cached
            try:
                p = Path(row.avatar_path)
                if p.exists() and p.is_file() and p.stat().st_size > 32:
                    image = Image.open(p).convert("RGBA")
                    s = min(*image.size)
                    image = image.crop(((image.width - s) // 2, (image.height - s) // 2, (image.width + s) // 2, (image.height + s) // 2))
                    image = image.resize((size, size), Image.Resampling.LANCZOS)
                    mask = Image.new("L", (size, size), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
                    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                    out.paste(image, (0, 0), mask)
                    self._avatar_cache[key] = out
                    return out
            except Exception:
                pass

        initials = "".join(part[:1] for part in row.name.split()[:2]).upper() or "?"
        base_tone = tone or self.COLORS["info"]
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(out)
        d.ellipse((0, 0, size - 1, size - 1), fill=(25, 42, 66, 255), outline=(base_tone[0], base_tone[1], base_tone[2], 130), width=2)
        font = self._font(max(20, size // 3), True)
        bbox = d.textbbox((0, 0), initials, font=font)
        d.text(((size - (bbox[2] - bbox[0])) / 2, (size - (bbox[3] - bbox[1])) / 2), initials, fill=self.COLORS["text"], font=font)
        return out


def to_png_bytes(img: Image.Image, name: str) -> Any:
    from io import BytesIO

    out = BytesIO()
    out.name = name
    img.save(out, format="PNG")
    out.seek(0)
    return out
