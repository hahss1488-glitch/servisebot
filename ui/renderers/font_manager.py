from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FontSpec:
    path: Path
    family: str
    weight: str


CYRILLIC_PROBE_TEXT = "Дашборд Смена Выручка Осталось Обновлено"
_TOFU_PROBE = "□"

# Приоритет: Manrope -> Inter -> DejaVu (гарантированный fallback с кириллицей)
FONT_CANDIDATES: dict[str, list[FontSpec]] = {
    "extrabold": [
        FontSpec(Path("/usr/share/fonts/truetype/manrope/Manrope-ExtraBold.ttf"), "Manrope", "extrabold"),
        FontSpec(Path("/usr/share/fonts/truetype/inter/Inter-ExtraBold.ttf"), "Inter", "extrabold"),
        FontSpec(Path("/usr/share/fonts/truetype/inter/Inter-Bold.ttf"), "Inter", "bold"),
        FontSpec(Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), "DejaVuSans", "bold"),
    ],
    "bold": [
        FontSpec(Path("/usr/share/fonts/truetype/manrope/Manrope-Bold.ttf"), "Manrope", "bold"),
        FontSpec(Path("/usr/share/fonts/truetype/inter/Inter-Bold.ttf"), "Inter", "bold"),
        FontSpec(Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), "DejaVuSans", "bold"),
    ],
    "semibold": [
        FontSpec(Path("/usr/share/fonts/truetype/manrope/Manrope-SemiBold.ttf"), "Manrope", "semibold"),
        FontSpec(Path("/usr/share/fonts/truetype/inter/Inter-SemiBold.ttf"), "Inter", "semibold"),
        FontSpec(Path("/usr/share/fonts/truetype/inter/Inter-Medium.ttf"), "Inter", "medium"),
        FontSpec(Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), "DejaVuSans", "regular"),
    ],
    "medium": [
        FontSpec(Path("/usr/share/fonts/truetype/manrope/Manrope-Medium.ttf"), "Manrope", "medium"),
        FontSpec(Path("/usr/share/fonts/truetype/inter/Inter-Medium.ttf"), "Inter", "medium"),
        FontSpec(Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), "DejaVuSans", "regular"),
    ],
    "regular": [
        FontSpec(Path("/usr/share/fonts/truetype/manrope/Manrope-Regular.ttf"), "Manrope", "regular"),
        FontSpec(Path("/usr/share/fonts/truetype/inter/Inter-Regular.ttf"), "Inter", "regular"),
        FontSpec(Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), "DejaVuSans", "regular"),
    ],
}


def font_supports_text(font: ImageFont.FreeTypeFont, text: str) -> bool:
    """Эвристика: если рендер кириллицы похож на tofu-квадрат, шрифт непригоден."""
    try:
        tofu_bbox = font.getbbox(_TOFU_PROBE)
        tofu_w = (tofu_bbox[2] - tofu_bbox[0]) if tofu_bbox else 0
        for ch in text:
            if ch.isspace():
                continue
            bbox = font.getbbox(ch)
            width = (bbox[2] - bbox[0]) if bbox else 0
            if width == 0:
                return False
            if ch.isalpha() and width == tofu_w and ch in "ДашбордСменаВыручкаОсталосьОбновлено":
                # дополнительная защита от tofu для ключевых кириллических букв
                return False
    except Exception:
        return False
    return True


@lru_cache(maxsize=256)
def get_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    w = weight if weight in FONT_CANDIDATES else "regular"
    for candidate in FONT_CANDIDATES[w]:
        try:
            font = ImageFont.truetype(str(candidate.path), size)
        except OSError:
            continue
        if font_supports_text(font, CYRILLIC_PROBE_TEXT):
            logger.info("font selected family=%s weight=%s path=%s size=%s", candidate.family, candidate.weight, candidate.path, size)
            return font
        logger.warning("font rejected (no cyrillic) path=%s", candidate.path)

    fallback = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    logger.warning("font fallback forced to DejaVuSans size=%s weight=%s", size, weight)
    return fallback
