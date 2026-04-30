"""Лёгкая версия Telegram-бота учёта услуг."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import BOT_TOKEN, SERVICES, validate_car_number
from database import DatabaseManager, init_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("servicebot")
LOCAL_TZ = ZoneInfo("Europe/Moscow")


def _money(v: int) -> str:
    return f"{int(v):,} ₽".replace(",", " ")


def _decade_index(day: int) -> int:
    return 1 if day <= 10 else 2 if day <= 20 else 3


def _service_price(service_id: int, mode: str = "day") -> int:
    service = SERVICES.get(service_id, {})
    return int(service.get("night_price" if mode == "night" else "day_price", 0))


def _main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["🟢 Начать смену", "🔴 Закрыть смену"], ["🚗 Добавить машину", "📊 Дашборд"], ["🏆 Лидерборд", "📅 Декада"]],
        resize_keyboard=True,
    )


def _services_keyboard() -> InlineKeyboardMarkup:
    rows = []
    ordered = sorted(
        [(sid, s) for sid, s in SERVICES.items() if s.get("kind") != "group" and not s.get("hidden") and s.get("day_price") is not None],
        key=lambda x: (x[1].get("priority", 99), x[1].get("order", 99), x[0]),
    )
    for sid, service in ordered:
        rows.append([InlineKeyboardButton(f"{service['name']} · {_money(_service_price(sid))}", callback_data=f"svc:{sid}")])
    rows.append([InlineKeyboardButton("✅ Готово", callback_data="svc:done")])
    return InlineKeyboardMarkup(rows)


async def _ensure_user(update: Update) -> dict:
    tg_user = update.effective_user
    assert tg_user is not None
    db_user = DatabaseManager.get_user(tg_user.id)
    if db_user:
        return db_user
    name = (" ".join(filter(None, [tg_user.first_name, tg_user.last_name])).strip() or tg_user.username or "Пользователь")
    DatabaseManager.register_user(tg_user.id, name)
    return DatabaseManager.get_user(tg_user.id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ensure_user(update)
    await update.message.reply_text("Бот перезапущен в облегчённой версии. Выберите действие.", reply_markup=_main_kb())


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    db_user = await _ensure_user(update)

    if text == "🟢 Начать смену":
        active = DatabaseManager.get_active_shift(db_user["id"])
        if active:
            await update.message.reply_text("Смена уже активна.", reply_markup=_main_kb())
            return
        shift_id = DatabaseManager.start_shift(db_user["id"])
        await update.message.reply_text(f"Смена #{shift_id} открыта.", reply_markup=_main_kb())
        return

    if text == "🔴 Закрыть смену":
        active = DatabaseManager.get_active_shift(db_user["id"])
        if not active:
            await update.message.reply_text("Нет активной смены.", reply_markup=_main_kb())
            return
        DatabaseManager.close_shift(active["id"])
        total = DatabaseManager.get_shift_total(active["id"])
        await update.message.reply_text(f"Смена закрыта. Итого: {_money(total)}", reply_markup=_main_kb())
        return

    if text == "🚗 Добавить машину":
        context.user_data["awaiting_car"] = True
        await update.message.reply_text("Введите номер авто (например: А123ВС777)")
        return

    if text == "📊 Дашборд":
        await send_dashboard(update, db_user)
        return

    if text == "🏆 Лидерборд":
        await send_leaderboard(update)
        return

    if text == "📅 Декада":
        await send_decade(update, db_user)
        return

    if context.user_data.get("awaiting_car"):
        await handle_car_input(update, context, db_user, text)
        return

    await update.message.reply_text("Команда не распознана. Используйте меню.", reply_markup=_main_kb())


async def handle_car_input(update: Update, context: ContextTypes.DEFAULT_TYPE, db_user: dict, text: str) -> None:
    ok, normalized, err = validate_car_number(text)
    if not ok:
        await update.message.reply_text(f"Ошибка номера: {err}")
        return
    active = DatabaseManager.get_active_shift(db_user["id"])
    if not active:
        await update.message.reply_text("Сначала начните смену.", reply_markup=_main_kb())
        return
    car_id = DatabaseManager.add_car(active["id"], normalized)
    context.user_data["awaiting_car"] = False
    context.user_data["active_car_id"] = car_id
    await update.message.reply_text(f"Машина {normalized} добавлена. Выберите услуги:", reply_markup=_services_keyboard())


async def services_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    car_id = int(context.user_data.get("active_car_id") or 0)
    if not car_id:
        await query.edit_message_text("Сначала добавьте машину.")
        return
    if data == "svc:done":
        car = DatabaseManager.get_car(car_id)
        await query.edit_message_text(f"Готово. Машина: {car.get('car_number')} · Сумма: {_money(car.get('total_amount', 0))}")
        return

    sid = int(data.split(":", 1)[1])
    service = SERVICES.get(sid)
    if not service:
        await query.answer("Услуга не найдена", show_alert=True)
        return
    price = _service_price(sid)
    DatabaseManager.add_service_to_car(car_id, sid, service["name"], price)
    car = DatabaseManager.get_car(car_id)
    await query.edit_message_text(
        f"Добавлено: {service['name']} (+{_money(price)})\nТекущая сумма: {_money(car.get('total_amount', 0))}",
        reply_markup=_services_keyboard(),
    )


async def send_dashboard(update: Update, db_user: dict) -> None:
    active = DatabaseManager.get_active_shift(db_user["id"])
    month = datetime.now(LOCAL_TZ).strftime("%Y-%m")
    days = DatabaseManager.get_days_for_month(db_user["id"], month)
    month_total = sum(int(d.get("total", 0)) for d in days)
    today_total = next((int(d.get("total", 0)) for d in days if d.get("day") == datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")), 0)
    text = ["📊 Текстовый дашборд", f"Сегодня: {_money(today_total)}", f"За месяц: {_money(month_total)}"]
    if active:
        text.append(f"Активная смена: #{active['id']} · {_money(DatabaseManager.get_shift_total(active['id']))}")
    await update.message.reply_text("\n".join(text), reply_markup=_main_kb())


async def send_leaderboard(update: Update) -> None:
    rows = DatabaseManager.get_active_leaderboard(limit=10)
    if not rows:
        await update.message.reply_text("Пока нет данных по лидерборду.")
        return
    lines = ["🏆 Лидерборд (текущая декада)"]
    for i, row in enumerate(rows, start=1):
        lines.append(f"{i}. {row.get('name', '—')} — {_money(row.get('total_amount', 0))}")
    await update.message.reply_text("\n".join(lines), reply_markup=_main_kb())


async def send_decade(update: Update, db_user: dict) -> None:
    now = datetime.now(LOCAL_TZ)
    idx = _decade_index(now.day)
    rows = DatabaseManager.get_days_for_decade(db_user["id"], now.year, now.month, idx)
    if not rows:
        await update.message.reply_text("За текущую декаду данных нет.")
        return
    total = sum(int(r.get("total", 0)) for r in rows)
    lines = [f"📅 Декада {idx} ({now.strftime('%m.%Y')})", f"Итого: {_money(total)}", "По дням:"]
    for row in rows:
        lines.append(f"• {row.get('day')}: {_money(row.get('total', 0))}")
    await update.message.reply_text("\n".join(lines), reply_markup=_main_kb())


def main() -> None:
    init_database()
    if not BOT_TOKEN:
        raise RuntimeError("SERVICEBOT_TOKEN не задан")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(services_callback, pattern=r"^svc:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    logger.info("ServiceBot Lite started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
