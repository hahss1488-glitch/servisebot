from __future__ import annotations

import logging
from dataclasses import dataclass

from config import validate_car_number
from database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FastInputParse:
    car_number: str | None
    combo_id: int | None
    service_ids: list[int]
    unknown_tokens: list[str]
    error_message: str = ""


def parse_fast_input(text: str, user_id: int, service_aliases: dict[int, list[str]]) -> FastInputParse:
    tokens = [p.strip(" ,.;:!").lower() for p in text.split() if p.strip()]
    if not tokens:
        return FastInputParse(None, None, [], [], "Пустой ввод")

    ok, number, err = validate_car_number(tokens[0])
    if not ok:
        return FastInputParse(None, None, [], [], err)

    combos = DatabaseManager.get_user_combos(user_id)
    combo_aliases = {str(c.get('alias') or '').strip().lower(): int(c['id']) for c in combos if str(c.get('alias') or '').strip()}
    service_alias_map = {}
    for sid, aliases in service_aliases.items():
        for a in aliases:
            service_alias_map[a] = sid

    conflicts = sorted(set(combo_aliases.keys()) & set(service_alias_map.keys()))
    if conflicts:
        logger.warning("alias conflict user_id=%s aliases=%s", user_id, conflicts)
        return FastInputParse(number, None, [], [], f"Конфликт alias: {', '.join(conflicts)}")

    combo_ids = []
    service_ids = []
    unknown = []
    for t in tokens[1:]:
        if t in combo_aliases:
            combo_ids.append(combo_aliases[t])
            continue
        sid = service_alias_map.get(t)
        if sid:
            service_ids.append(sid)
        else:
            unknown.append(t)

    if len(combo_ids) > 1:
        return FastInputParse(number, None, service_ids, unknown, "Поддерживается только одно комбо в строке")

    combo_id = combo_ids[0] if combo_ids else None
    if combo_id:
        combo = DatabaseManager.get_combo(combo_id, user_id)
        if combo:
            service_ids = list(combo.get("service_ids", [])) + service_ids

    if not service_ids:
        return FastInputParse(number, combo_id, [], unknown, "Не распознал услуги или комбо")

    logger.info("fast input parsed user_id=%s number=%s combo_id=%s services=%s unknown=%s", user_id, number, combo_id, service_ids, unknown)
    return FastInputParse(number, combo_id, service_ids, unknown)
