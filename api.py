import logging
import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator

from config import BOT_TOKEN, SERVICES
from database import DatabaseManager, get_connection, init_database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ServiceBot API", version="1.0.0")

FAST_SERVICE_ALIASES = {
    1: ["проверка", "пров", "провер", "чек"],
    2: ["заправка", "запр", "топливо", "бенз"],
    3: ["омыв", "омывка", "омывайка", "зали", "зо", "заливка"],
    14: ["перепарковка", "перепарк", "парковка", "некорректная", "некк", "нек", "некорр"],
}


class TaskPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chat_id: int
    car_id: str
    task_type: str | int
    timestamp: int
    device_key: str | None = None

    @field_validator("car_id")
    @classmethod
    def validate_car_id(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("car_id_required")
        return normalized


def plain_service_name(name: str) -> str:
    return re.sub(r"^[^0-9A-Za-zА-Яа-я]+\s*", "", name).strip()


def resolve_service_id(task_type: str | int) -> int | None:
    if isinstance(task_type, int):
        return task_type if task_type in SERVICES else None

    normalized = str(task_type).strip().lower()
    if not normalized:
        return None

    if normalized.isdigit():
        numeric = int(normalized)
        return numeric if numeric in SERVICES else None

    for service_id, aliases in FAST_SERVICE_ALIASES.items():
        if normalized in aliases:
            return service_id

    for service_id, service in SERVICES.items():
        clean_name = plain_service_name(service.get("name", "")).lower()
        if normalized in clean_name or clean_name in normalized:
            return service_id

    return None


def is_duplicate_recent(car_id: int, service_id: int, ttl_hours: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT 1
        FROM car_services
        WHERE car_id = ?
          AND service_id = ?
          AND datetime(created_at) >= datetime('now', ?)
        LIMIT 1""",
        (car_id, service_id, f"-{ttl_hours} hours"),
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def maybe_notify_telegram(chat_id: int, car_number: str, service_name: str, price: int) -> None:
    if os.getenv("NOTIFY_TELEGRAM", "0") != "1":
        return
    if not BOT_TOKEN:
        logger.warning("NOTIFY_TELEGRAM=1, but BOT_TOKEN is empty")
        return

    text = f"✅ Добавлена услуга: {service_name}\n🚗 {car_number}\n💰 {price}₽"
    payload = urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    try:
        urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=payload, timeout=3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram notify failed: %s", exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    reason = "invalid_payload"
    if exc.errors():
        reason = str(exc.errors()[0].get("msg", reason))
    return JSONResponse(status_code=422, content={"status": "error", "reason": reason})


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error: %s", exc)
    return JSONResponse(status_code=500, content={"status": "error", "reason": "internal_error"})


@app.on_event("startup")
def on_startup() -> None:
    init_database()


@app.post("/api/task")
async def create_task(payload: TaskPayload) -> JSONResponse:
    required_device_key = os.getenv("DEVICE_KEY")
    if required_device_key and payload.device_key != required_device_key:
        return JSONResponse(status_code=401, content={"status": "error", "reason": "unauthorized"})

    user = DatabaseManager.get_user(payload.chat_id)
    if not user:
        return JSONResponse(status_code=404, content={"status": "error", "reason": "user_not_registered"})

    shift = DatabaseManager.get_active_shift(user["id"])
    if not shift:
        if os.getenv("AUTO_START_SHIFT", "0") == "1":
            shift_id = DatabaseManager.start_shift(user["id"])
            shift = DatabaseManager.get_shift(shift_id)
        else:
            return JSONResponse(status_code=409, content={"status": "error", "reason": "no_active_shift"})

    car_number = payload.car_id
    shift_cars = DatabaseManager.get_shift_cars(shift["id"])
    car = next((item for item in shift_cars if str(item.get("car_number", "")).strip().upper() == car_number), None)
    if car:
        car_db_id = int(car["id"])
    else:
        car_db_id = DatabaseManager.add_car(shift["id"], car_number)

    service_id = resolve_service_id(payload.task_type)
    if service_id is None:
        return JSONResponse(status_code=422, content={"status": "error", "reason": "unknown_task_type"})

    ttl_hours = max(1, int(os.getenv("DEDUPE_TTL_HOURS", "6")))
    if is_duplicate_recent(car_db_id, service_id, ttl_hours):
        return JSONResponse(status_code=200, content={"status": "ok", "dedup": True})

    service = SERVICES[service_id]
    service_name = plain_service_name(service.get("name", ""))
    price_mode = DatabaseManager.get_price_mode(user["id"])
    price_key = "night_price" if price_mode == "night" else "day_price"
    price = int(service.get(price_key, 0) or 0)

    DatabaseManager.add_service_to_car(car_db_id, service_id, service_name, price)
    maybe_notify_telegram(payload.chat_id, car_number, service_name, price)

    return JSONResponse(status_code=200, content={"status": "ok"})
