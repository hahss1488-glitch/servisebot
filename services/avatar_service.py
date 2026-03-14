from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from PIL import Image

from database import DatabaseManager

logger = logging.getLogger(__name__)


def save_custom_avatar(user_id: int, payload: bytes, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    out = directory / f"{user_id}.jpg"
    with Image.open(BytesIO(payload)) as src:
        img = src.convert("RGB")
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        square = img.crop((left, top, left + side, top + side)).resize((512, 512), Image.Resampling.LANCZOS)
        square.save(out, format="JPEG", quality=90, optimize=True)
    DatabaseManager.set_custom_avatar(user_id, str(out))
    logger.info("avatar saved user_id=%s path=%s", user_id, out)
    return out


def get_effective_avatar(user_id: int) -> str:
    settings = DatabaseManager.get_avatar_settings(user_id)
    source = settings.get("avatar_source", "telegram")
    custom = Path(settings.get("custom_avatar_path", "")) if settings.get("custom_avatar_path") else None
    tg = Path(settings.get("telegram_avatar_path", "")) if settings.get("telegram_avatar_path") else None
    if source == "custom" and custom and custom.exists():
        return str(custom)
    if tg and tg.exists():
        return str(tg)
    return ""


def reset_avatar(user_id: int) -> None:
    DatabaseManager.reset_avatar_source(user_id)
    logger.info("avatar reset user_id=%s", user_id)


def build_avatar_preview(path: str) -> bytes | None:
    p = Path(path)
    if not p.exists():
        return None
    return p.read_bytes()
