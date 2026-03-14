from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from config import validate_car_number
from database import DatabaseManager

logger = logging.getLogger(__name__)

ALIAS_RE = re.compile(r"^[a-zа-я0-9_-]{2,16}$", re.IGNORECASE)


@dataclass(slots=True)
class FastInputParse:
    car_number: str | None
    combo_id: int | None
    service_ids: list[int]
    unknown_tokens: list[str]
    error_message: str = ""


def normalize_alias(value: str) -> str:
    return (value or "").strip().lower()


def is_valid_alias(value: str) -> bool:
    return bool(ALIAS_RE.fullmatch(normalize_alias(value)))


def parse_fast_input(text: str, user_id: int, service_aliases: dict[int, list[str]]) -> FastInputParse:
    tokens = [p.strip(" ,.;:!").lower() for p in text.split() if p.strip()]
    if not tokens:
        return FastInputParse(None, None, [], [], "Пустой ввод")

    ok, number, err = validate_car_number(tokens[0])
    if not ok:
        return FastInputParse(None, None, [], [], err)

    combos = DatabaseManager.get_user_combos(user_id)
    combo_aliases = {
        normalize_alias(str(c.get("alias") or "")): int(c["id"])
        for c in combos
        if normalize_alias(str(c.get("alias") or ""))
    }

    service_alias_map: dict[str, int] = {}
    for sid, aliases in service_aliases.items():
        for alias in aliases:
            service_alias_map[normalize_alias(alias)] = sid

    conflicts = sorted(set(combo_aliases.keys()) & set(service_alias_map.keys()))
    if conflicts:
        logger.warning("alias conflict user_id=%s aliases=%s", user_id, conflicts)
        return FastInputParse(number, None, [], [], f"Конфликт alias: {', '.join(conflicts)}")

    combo_ids: list[int] = []
    service_ids: list[int] = []
    unknown: list[str] = []

    for token in tokens[1:]:
        norm = normalize_alias(token)
        if norm in combo_aliases:
            combo_ids.append(combo_aliases[norm])
            continue

        service_id = service_alias_map.get(norm)
        if service_id:
            service_ids.append(service_id)
        else:
            unknown.append(token)

    if len(combo_ids) > 1:
        return FastInputParse(number, None, service_ids, unknown, "Поддерживается только одно комбо в строке")

    combo_id = combo_ids[0] if combo_ids else None
    if combo_id:
        combo = DatabaseManager.get_combo(combo_id, user_id)
        if combo:
            service_ids = list(combo.get("service_ids", [])) + service_ids

    if not service_ids:
        return FastInputParse(number, combo_id, [], unknown, "Не распознал услуги или комбо")

    logger.info(
        "fast input parsed user_id=%s number=%s combo_id=%s services=%s unknown=%s",
        user_id,
        number,
        combo_id,
        service_ids,
        unknown,
    )
    return FastInputParse(number, combo_id, service_ids, unknown)
