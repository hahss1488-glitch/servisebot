"""
🤖 БОТ ДЛЯ УЧЁТА УСЛУГ - УПРОЩЕННАЯ ВЕРСИЯ
Просто работает
"""

import logging
from datetime import datetime, date, timedelta
import csv
import os
import shutil
import calendar
from typing import List, Optional, Dict

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    CallbackContext,
    filters,
)

from config import BOT_TOKEN, SERVICES, validate_car_number
from database import DatabaseManager, init_database, DB_PATH

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
init_database()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def get_current_price(service_id: int, mode: str) -> int:
    """Получение цены по выбранному прайсу"""
    service = SERVICES.get(service_id)
    if not service:
        return 0
    if mode == "night":
        return service.get("night_price", 0)
    return service.get("day_price", 0)

def format_money(amount: int) -> str:
    """Форматирование денежной суммы"""
    return f"{amount:,}₽".replace(",", " ")

# ========== КЛАВИАТУРЫ ==========

MENU_OPEN_SHIFT = "📅 Открыть смену"
MENU_ADD_CAR = "🚗 Добавить машину"
MENU_CURRENT_SHIFT = "📊 Текущая смена"
MENU_HISTORY = "📜 История смен"
MENU_SETTINGS = "⚙️ Настройки"
MENU_LEADERBOARD = "🏆 Лидеры смены"
MENU_DECADE = "📆 Зарплата (декады)"
MENU_STATS = "📈 Статистика"

def create_main_reply_keyboard(has_active_shift: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню под полем ввода"""
    keyboard = []

    if has_active_shift:
        keyboard.append([KeyboardButton(MENU_ADD_CAR), KeyboardButton(MENU_CURRENT_SHIFT)])
    else:
        keyboard.append([KeyboardButton(MENU_OPEN_SHIFT)])

    keyboard.append([KeyboardButton(MENU_HISTORY), KeyboardButton(MENU_LEADERBOARD)])
    keyboard.append([KeyboardButton(MENU_DECADE), KeyboardButton(MENU_STATS)])
    keyboard.append([KeyboardButton(MENU_SETTINGS)])

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие ниже"
    )

def get_service_order() -> List[int]:
    services = []
    for service_id, service in SERVICES.items():
        if service.get("hidden"):
            continue
        services.append((service.get("priority", 99), service.get("order", 99), service_id))
    services.sort()
    return [service_id for _, _, service_id in services]

def chunk_buttons(buttons: List[InlineKeyboardButton], columns: int) -> List[List[InlineKeyboardButton]]:
    return [buttons[i:i + columns] for i in range(0, len(buttons), columns)]

def create_services_keyboard(
    car_id: int,
    page: int = 0,
    is_edit_mode: bool = False,
    price_mode: str = "day",
    group_id: Optional[int] = None
) -> InlineKeyboardMarkup:
    """Клавиатура выбора услуг (с колонками и перелистыванием)"""
    if group_id:
        group = SERVICES.get(group_id, {})
        service_ids = group.get("children", [])
    else:
        service_ids = get_service_order()

    per_page = 6
    max_page = max((len(service_ids) - 1) // per_page, 0)
    page = max(0, min(page, max_page))

    start = page * per_page
    end = start + per_page
    page_ids = service_ids[start:end]

    buttons = []
    for service_id in page_ids:
        service = SERVICES[service_id]
        if service.get("kind") == "group":
            text = f"▶️ {service['name']}"
            buttons.append(InlineKeyboardButton(text, callback_data=f"open_group_{service_id}_{car_id}_{page}"))
            continue
        if service.get("kind") == "distance":
            text = f"{service['name']} (по км)"
            buttons.append(InlineKeyboardButton(text, callback_data=f"distance_{service_id}_{car_id}_{page}"))
            continue
        price = get_current_price(service_id, price_mode)
        text = f"{service['name']} ({price}₽)"
        buttons.append(InlineKeyboardButton(text, callback_data=f"service_{service_id}_{car_id}_{page}"))

    keyboard = chunk_buttons(buttons, 2)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"service_page_{car_id}_{page - 1}_{group_id or 0}"))
    nav_buttons.append(InlineKeyboardButton(f"Стр {page + 1}/{max_page + 1}", callback_data="noop"))
    if page < max_page:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"service_page_{car_id}_{page + 1}_{group_id or 0}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    price_buttons = []
    day_active = "✅" if price_mode == "day" else ""
    night_active = "✅" if price_mode == "night" else ""
    price_buttons.append(
        InlineKeyboardButton(f"☀️ Прайс день {day_active}".strip(), callback_data=f"price_day_{car_id}_{page}_{group_id or 0}")
    )
    price_buttons.append(
        InlineKeyboardButton(f"🌙 Прайс ночь {night_active}".strip(), callback_data=f"price_night_{car_id}_{page}_{group_id or 0}")
    )
    keyboard.insert(0, price_buttons)

    if group_id:
        keyboard.append([InlineKeyboardButton("⬅️ Назад к списку", callback_data=f"close_group_{car_id}_{page}")])

    edit_text = "✅ Готово" if is_edit_mode else "✏️ Редактировать"
    keyboard.append([
        InlineKeyboardButton(edit_text, callback_data=f"toggle_edit_{car_id}_{page}"),
        InlineKeyboardButton("🗑️ Очистить всё", callback_data=f"clear_{car_id}_{page}"),
        InlineKeyboardButton("💾 Сохранить", callback_data=f"save_{car_id}")
    ])

    return InlineKeyboardMarkup(keyboard)

def parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
    return None

def get_goal_text(user_id: int) -> str:
    goal = DatabaseManager.get_daily_goal(user_id)
    if goal <= 0:
        return "🎯 Цель дня не задана."

    today_total = DatabaseManager.get_user_total_for_date(user_id, datetime.now().strftime("%Y-%m-%d"))
    percent = min(int((today_total / goal) * 100) if goal else 0, 100)
    return (
        f"🎯 Цель дня: {format_money(goal)}\n"
        f"Сделано: {format_money(today_total)} ({percent}%)"
    )

def get_edit_mode(context: CallbackContext, car_id: int) -> bool:
    return context.user_data.get(f"edit_mode_{car_id}", False)

def toggle_edit_mode(context: CallbackContext, car_id: int) -> bool:
    new_value = not context.user_data.get(f"edit_mode_{car_id}", False)
    context.user_data[f"edit_mode_{car_id}"] = new_value
    return new_value

def get_price_mode(context: CallbackContext) -> str:
    return context.user_data.get("price_mode", "day")

def set_price_mode(context: CallbackContext, mode: str):
    context.user_data["price_mode"] = mode

def build_decade_summary(user_id: int) -> str:
    today = date.today()
    decads = build_decade_ranges(today, 6)
    lines = ["📆 ЗАРПЛАТА ПО ДЕКАДАМ\n"]
    for item in decads:
        total = DatabaseManager.get_user_total_between_dates(
            user_id, item["start"].isoformat(), item["end"].isoformat()
        )
        marker = "✅ " if item["is_current"] else ""
        lines.append(f"{marker}{item['label']}: {format_money(total)}")
    return "\n".join(lines)

def build_stats_summary(user_id: int) -> str:
    services = DatabaseManager.get_service_stats(user_id)
    cars = DatabaseManager.get_car_stats(user_id)

    message = "📈 СТАТИСТИКА\n\n"
    if services:
        message += "Топ услуг:\n"
        for item in services:
            message += (
                f"• {item['service_name']} — {item['total_count']} шт. "
                f"({format_money(item['total_amount'])})\n"
            )
    else:
        message += "Топ услуг: пока нет данных.\n"

    message += "\n"
    if cars:
        message += "Топ машин:\n"
        for item in cars:
            message += (
                f"• {item['car_number']} — {item['visits']} раз "
                f"({format_money(item['total_amount'])})\n"
            )
    else:
        message += "Топ машин: пока нет данных.\n"

    return message

def build_history_keyboard(shifts: List[Dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for shift in shifts:
        start_time = parse_datetime(shift['start_time'])
        label = start_time.strftime("%d.%m %H:%M") if start_time else "Смена"
        keyboard.append([InlineKeyboardButton(f"📝 {label}", callback_data=f"edit_shift_{shift['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def build_decade_ranges(anchor_date: date, count: int) -> List[Dict[str, object]]:
    month_names = {
        1: "января",
        2: "февраля",
        3: "марта",
        4: "апреля",
        5: "мая",
        6: "июня",
        7: "июля",
        8: "августа",
        9: "сентября",
        10: "октября",
        11: "ноября",
        12: "декабря",
    }
    decads = []
    current = anchor_date
    for _ in range(count):
        year = current.year
        month = current.month
        day = current.day
        if day <= 10:
            start_day, end_day = 1, 10
        elif day <= 20:
            start_day, end_day = 11, 20
        else:
            start_day = 21
            end_day = calendar.monthrange(year, month)[1]
        start = date(year, month, start_day)
        end = date(year, month, end_day)
        label = f"Декада {start_day}–{end_day} {month_names[month]}"
        decads.append({"start": start, "end": end, "label": label, "is_current": _ == 0})
        current = start - timedelta(days=1)
    return decads

def build_csv_report(user_id: int) -> str:
    rows = DatabaseManager.get_shift_report_rows(user_id)
    if not rows:
        return ""

    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    path = os.path.join(reports_dir, filename)

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["shift_id", "start_time", "end_time", "car_number", "services", "total_amount"])
        for row in rows:
            writer.writerow([
                row.get("shift_id"),
                row.get("start_time"),
                row.get("end_time") or "",
                row.get("car_number") or "",
                row.get("services") or "",
                row.get("total_amount") or 0,
            ])
    return path

def create_db_backup() -> str:
    if not os.path.exists(DB_PATH):
        return ""
    backups_dir = "backups"
    os.makedirs(backups_dir, exist_ok=True)
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    path = os.path.join(backups_dir, filename)
    shutil.copy2(DB_PATH, path)
    return path

async def send_goal_status(update: Update, context: CallbackContext, user_id: int):
    """Отправить и попытаться закрепить цель дня"""
    if update.message:
        await send_goal_status_from_chat(context, update.message.chat_id, user_id)
    elif update.callback_query and update.callback_query.message:
        await send_goal_status_from_chat(context, update.callback_query.message.chat_id, user_id)

async def send_goal_status_from_chat(context: CallbackContext, chat_id: int, user_id: int):
    goal_text = get_goal_text(user_id)
    try:
        message = await context.bot.send_message(chat_id=chat_id, text=goal_text)
    except Exception:
        return
    try:
        await context.bot.pin_chat_message(
            chat_id=message.chat_id,
            message_id=message.message_id,
            disable_notification=True
        )
    except Exception:
        pass

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

async def start_command(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    user = update.effective_user
    
    if update.message:
        # Автоматическая регистрация
        db_user = DatabaseManager.get_user(user.id)
        context.user_data.setdefault("price_mode", "day")
        
        if not db_user:
            name = user.first_name or user.username or "Пользователь"
            DatabaseManager.register_user(user.id, name)
        
        # Простое приветствие
        has_active = False
        if db_user:
            has_active = DatabaseManager.get_active_shift(db_user['id']) is not None

        await update.message.reply_text(
            f"👋 Привет!\n"
            f"Я бот для учёта услуг на СТО.\n\n"
            f"Выберите действие:",
            reply_markup=create_main_reply_keyboard(has_active)
        )
        await send_goal_status(update, context, db_user['id'])

async def menu_command(update: Update, context: CallbackContext):
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await update.message.reply_text("❌ Пользователь не найден. Напишите /start")
        return
    context.user_data.setdefault("price_mode", "day")
    has_active = DatabaseManager.get_active_shift(db_user['id']) is not None
    await update.message.reply_text(
        "Меню открыто.",
        reply_markup=create_main_reply_keyboard(has_active)
    )

async def handle_message(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений"""
    user = update.effective_user
    text = update.message.text.strip()

    # Если ожидаем номер машины, но пользователь нажал меню — отменяем ввод
    if context.user_data.get('awaiting_car_number') and text in {
        MENU_OPEN_SHIFT,
        MENU_ADD_CAR,
        MENU_CURRENT_SHIFT,
        MENU_HISTORY,
        MENU_SETTINGS,
        MENU_LEADERBOARD,
        MENU_DECADE,
        MENU_STATS,
    }:
        context.user_data.pop('awaiting_car_number', None)
        await update.message.reply_text("Ок, ввод номера отменён.")
        # Продолжаем обработку выбранного пункта меню

    # Ожидание номера машины
    if context.user_data.get('awaiting_car_number'):
        # Проверяем валидность номера
        is_valid, normalized_number, error_msg = validate_car_number(text)
        
        if not is_valid:
            await update.message.reply_text(
                f"❌ Ошибка: {error_msg}\n\n"
                f"Введите номер ещё раз:"
            )
            return
        
        # Получаем активную смену
        db_user = DatabaseManager.get_user(user.id)
        if not db_user:
            await update.message.reply_text("❌ Пользователь не найден. Напишите /start")
            context.user_data.pop('awaiting_car_number', None)
            return
        active_shift = DatabaseManager.get_active_shift(db_user['id'])
        
        if not active_shift:
            await update.message.reply_text(
                "❌ Нет активной смены! Сначала откройте смену."
            )
            context.user_data.pop('awaiting_car_number', None)
            await update.message.reply_text(
                "Выберите действие:",
                reply_markup=create_main_reply_keyboard(False)
            )
            return
        
        # Добавляем машину
        car_id = DatabaseManager.add_car(active_shift['id'], normalized_number)
        
        context.user_data.pop('awaiting_car_number', None)
        context.user_data['current_car'] = car_id
        
        await update.message.reply_text(
            f"🚗 Машина: {normalized_number}\n"
            f"Выберите услуги:",
            reply_markup=create_services_keyboard(
                car_id,
                0,
                False,
                get_price_mode(context)
            )
        )
        # Обновляем закреп цели дня, если он есть
        if db_user:
            await send_goal_status_from_chat(context, update.message.chat_id, db_user['id'])
        return

    if context.user_data.get('awaiting_distance'):
        raw_value = text.replace(" ", "").replace("км", "")
        if not raw_value.isdigit():
            await update.message.reply_text("❌ Введите километраж цифрами. Например: 45")
            return
        km = int(raw_value)
        payload = context.user_data.pop('awaiting_distance')
        car_id = payload["car_id"]
        service_id = payload["service_id"]
        page = payload["page"]
        service = SERVICES.get(service_id)
        if not service:
            await update.message.reply_text("❌ Услуга не найдена.")
            return
        price = km * service.get("rate_per_km", 0)
        price_mode = get_price_mode(context)
        service_name = f"{service['name']} — {km} км"
        DatabaseManager.add_service_to_car(car_id, service_id, service_name, price)
        group_id = context.user_data.get(f"group_{car_id}")
        message, keyboard = render_car_services(context, car_id, page, group_id)
        if message:
            await update.message.reply_text(message, reply_markup=keyboard)
        return

    # Ожидание цели дня
    if context.user_data.get('awaiting_goal'):
        raw_value = text.replace(" ", "").replace("₽", "")
        if not raw_value.isdigit():
            await update.message.reply_text("❌ Введите сумму цифрами. Например: 5000")
            return
        goal_value = int(raw_value)
        db_user = DatabaseManager.get_user(user.id)
        if not db_user:
            await update.message.reply_text("❌ Пользователь не найден. Напишите /start")
            return
        DatabaseManager.set_daily_goal(db_user['id'], goal_value)
        context.user_data.pop('awaiting_goal', None)
        has_active = DatabaseManager.get_active_shift(db_user['id']) is not None
        await update.message.reply_text(
            f"✅ Цель дня обновлена: {format_money(goal_value)}\n\n{get_goal_text(db_user['id'])}",
            reply_markup=create_main_reply_keyboard(has_active)
        )
        await send_goal_status(update, context, db_user['id'])
        return

    # Обработка кнопок главного меню (reply клавиатура)
    if text in {
        MENU_OPEN_SHIFT,
        MENU_ADD_CAR,
        MENU_CURRENT_SHIFT,
        MENU_HISTORY,
        MENU_SETTINGS,
        MENU_LEADERBOARD,
        MENU_DECADE,
        MENU_STATS,
    }:
        if text == MENU_OPEN_SHIFT:
            await open_shift_message(update, context)
        elif text == MENU_ADD_CAR:
            await add_car_message(update, context)
        elif text == MENU_CURRENT_SHIFT:
            await current_shift_message(update, context)
        elif text == MENU_HISTORY:
            await history_message(update, context)
        elif text == MENU_SETTINGS:
            await settings_message(update, context)
        elif text == MENU_LEADERBOARD:
            await leaderboard_message(update, context)
        elif text == MENU_DECADE:
            await decade_message(update, context)
        elif text == MENU_STATS:
            await stats_message(update, context)
        return
    
    await update.message.reply_text(
        "Используйте кнопки меню для работы с ботом.\n"
        "Напишите /start для начала."
    )

# ========== ОБРАБОТЧИКИ КНОПОК ==========

async def handle_callback(update: Update, context: CallbackContext):
    """Главный обработчик callback-кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    logger.info(f"Callback: {data} from {user.id}")
    
    # Основные действия
    if data == "open_shift":
        await open_shift(query, context)
    elif data == "add_car":
        await add_car(query, context)
    elif data == "current_shift":
        await current_shift(query, context)
    elif data == "history_0":
        await history(query, context)
    elif data == "settings":
        await settings(query, context)
    elif data.startswith("service_"):
        await add_service(query, context, data)
    elif data.startswith("service_page_"):
        await change_services_page(query, context, data)
    elif data.startswith("price_day_") or data.startswith("price_night_"):
        await change_price_mode(query, context, data)
    elif data.startswith("open_group_"):
        await open_group(query, context, data)
    elif data.startswith("close_group_"):
        await close_group(query, context, data)
    elif data.startswith("distance_"):
        await request_distance(query, context, data)
    elif data.startswith("clear_"):
        await clear_services(query, context, data)
    elif data.startswith("save_"):
        await save_car(query, context, data)
    elif data == "change_goal":
        await change_goal(query, context)
    elif data == "leaderboard":
        await leaderboard(query, context)
    elif data == "decade":
        await decade_callback(query, context)
    elif data == "stats":
        await stats_callback(query, context)
    elif data == "export_csv":
        await export_csv(query, context)
    elif data == "backup_db":
        await backup_db(query, context)
    elif data == "reset_data":
        await reset_data(query, context)
    elif data == "cancel_add_car":
        await cancel_add_car(query, context)
    elif data == "cancel_distance":
        await cancel_distance(query, context)
    elif data.startswith("toggle_edit_"):
        await toggle_edit(query, context, data)
    elif data.startswith("edit_shift_"):
        await edit_shift(query, context, data)
    elif data.startswith("edit_car_"):
        await edit_car(query, context, data)
    elif data.startswith("delete_car_"):
        await delete_car(query, context, data)
    elif data == "back_shift":
        await back_to_shift(query, context)
    elif data == "noop":
        return
    elif data.startswith("close_"):
        await close_shift(query, context, data)
    elif data == "back":
        await go_back(query, context)
    else:
        await query.edit_message_text("❌ Неизвестная команда")

async def open_shift(query, context):
    """Открытие смены"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден")
        return
    
    # Проверяем активную смену
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    if active_shift:
        start_time = parse_datetime(active_shift['start_time'])
        time_text = start_time.strftime('%H:%M %d.%m') if start_time else "неизвестно"
        await query.edit_message_text(
            f"❌ У вас уже есть активная смена!\n"
            f"Начата: {time_text}"
        )
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=create_main_reply_keyboard(True)
        )
        return
    
    # Создаём новую смену
    shift_id = DatabaseManager.start_shift(db_user['id'])
    
    await query.edit_message_text(
        f"✅ Смена открыта!\n"
        f"Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
        f"Теперь можно добавлять машины."
    )
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=create_main_reply_keyboard(True)
    )

async def add_car(query, context):
    """Добавление машины"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден")
        return
    
    # Проверяем активную смену
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    if not active_shift:
        await query.edit_message_text(
            "❌ Нет активной смены!\n"
            "Сначала откройте смену."
        )
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=create_main_reply_keyboard(False)
        )
        return
    
    context.user_data['awaiting_car_number'] = True
    
    await query.edit_message_text(
        f"Введите номер машины:\n\n"
        f"Примеры правильных номеров:\n"
        f"• А123ВС777\n"
        f"• Х340РУ797\n"
        f"• В567ТХ799\n\n"
        f"Можно вводить русскими или английскими буквами.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_car")]]
        )
    )

async def current_shift(query, context):
    """Текущая смена"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден")
        return
    
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    
    if not active_shift:
        await query.edit_message_text(
            "📭 Нет активной смены.\n"
            "Откройте смену для начала работы."
        )
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=create_main_reply_keyboard(False)
        )
        return
    
    cars = DatabaseManager.get_shift_cars(active_shift['id'])
    total = DatabaseManager.get_shift_total(active_shift['id'])
    
    start_time = parse_datetime(active_shift['start_time'])
    start_text = start_time.strftime('%H:%M %d.%m.%Y') if start_time else "неизвестно"
    message = (
        f"📊 ТЕКУЩАЯ СМЕНА\n\n"
        f"Начата: {start_text}\n"
        f"Машин: {len(cars)}\n"
        f"Сумма: {format_money(total)}\n\n"
    )
    
    if cars:
        message += "Машины в смене:\n"
        for car in cars:
            message += f"• {car['car_number']} - {format_money(car['total_amount'])}\n"
    
    keyboard = [
        [InlineKeyboardButton("🚗 Добавить машину", callback_data="add_car")],
        [InlineKeyboardButton("🔚 Закрыть смену", callback_data=f"close_{active_shift['id']}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def history(query, context):
    """История смен"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден")
        return
    
    shifts = DatabaseManager.get_user_shifts(db_user['id'], limit=10)
    
    if not shifts:
        await query.edit_message_text(
            "📜 У вас ещё нет смен.\n"
            "Откройте первую смену!"
        )
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=create_main_reply_keyboard(False)
        )
        return
    
    message = "📜 ИСТОРИЯ СМЕН\n\n"
    
    for shift in shifts:
        start_time = parse_datetime(shift['start_time'])
        end_time = parse_datetime(shift['end_time']) if shift['end_time'] else None
        date_str = start_time.strftime("%d.%m") if start_time else "??.??"
        start_str = start_time.strftime("%H:%M") if start_time else "??:??"

        if end_time:
            end_str = end_time.strftime("%H:%M")
            time_str = f"{start_str}-{end_str}"
            status = "✅"
        else:
            time_str = f"{start_str}"
            status = "🟢"
        
        total = shift.get('total_amount', 0)
        message += f"{status} {date_str} {time_str} - {format_money(total)}\n"
    
    keyboard = build_history_keyboard(shifts)
    await query.edit_message_text(message, reply_markup=keyboard)

async def settings(query, context):
    """Настройки"""
    keyboard = [
        [InlineKeyboardButton("🎯 Цель дня", callback_data="change_goal")],
        [InlineKeyboardButton("📆 Зарплата (декады)", callback_data="decade")],
        [InlineKeyboardButton("📈 Статистика", callback_data="stats")],
        [InlineKeyboardButton("📤 Экспорт CSV", callback_data="export_csv")],
        [InlineKeyboardButton("🗄️ Резервная копия", callback_data="backup_db")],
        [InlineKeyboardButton("🗑️ Сбросить данные", callback_data="reset_data")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    
    await query.edit_message_text(
        "⚙️ НАСТРОЙКИ\n\n"
        "Выберите параметр:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def add_service(query, context, data):
    """Добавление услуги"""
    parts = data.split('_')
    if len(parts) < 4:
        return
    
    service_id = int(parts[1])
    car_id = int(parts[2])
    page = int(parts[3])
    
    service = SERVICES.get(service_id)
    if not service:
        return
    
    price = get_current_price(service_id, get_price_mode(context))

    if get_edit_mode(context, car_id):
        DatabaseManager.remove_service_from_car(car_id, service_id)
    else:
        # Добавляем услугу
        DatabaseManager.add_service_to_car(car_id, service_id, service['name'], price)

    group_id = context.user_data.get(f"group_{car_id}")
    await show_car_services(query, context, car_id, page, group_id)

async def clear_services(query, context, data):
    """Очистка услуг"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    car_id = int(parts[1])
    page = int(parts[2])
    
    # Очищаем услуги
    DatabaseManager.clear_car_services(car_id)
    context.user_data.pop(f"edit_mode_{car_id}", None)
    
    context.user_data.pop(f"group_{car_id}", None)
    await show_car_services(query, context, car_id, page)

async def change_services_page(query, context, data):
    """Перелистывание услуг"""
    parts = data.split('_')
    if len(parts) < 5:
        return
    car_id = int(parts[2])
    page = int(parts[3])
    group_id = int(parts[4])
    group_value = group_id or None
    if group_value:
        context.user_data[f"group_{car_id}"] = group_value
    await show_car_services(query, context, car_id, page, group_value)

async def toggle_edit(query, context, data):
    parts = data.split('_')
    if len(parts) < 4:
        return
    car_id = int(parts[2])
    page = int(parts[3])
    toggle_edit_mode(context, car_id)
    group_id = context.user_data.get(f"group_{car_id}")
    await show_car_services(query, context, car_id, page, group_id)

async def change_price_mode(query, context, data):
    parts = data.split('_')
    if len(parts) < 5:
        return
    mode = "day" if parts[1] == "day" else "night"
    car_id = int(parts[2])
    page = int(parts[3])
    group_id = int(parts[4])
    set_price_mode(context, mode)
    group_value = group_id or None
    if group_value:
        context.user_data[f"group_{car_id}"] = group_value
    await show_car_services(query, context, car_id, page, group_value)

async def open_group(query, context, data):
    parts = data.split('_')
    if len(parts) < 5:
        return
    group_id = int(parts[2])
    car_id = int(parts[3])
    page = int(parts[4])
    context.user_data[f"group_{car_id}"] = group_id
    await show_car_services(query, context, car_id, page, group_id)

async def close_group(query, context, data):
    parts = data.split('_')
    if len(parts) < 4:
        return
    car_id = int(parts[2])
    page = int(parts[3])
    context.user_data.pop(f"group_{car_id}", None)
    await show_car_services(query, context, car_id, page)

async def request_distance(query, context, data):
    parts = data.split('_')
    if len(parts) < 4:
        return
    service_id = int(parts[1])
    car_id = int(parts[2])
    page = int(parts[3])
    context.user_data['awaiting_distance'] = {
        "service_id": service_id,
        "car_id": car_id,
        "page": page,
    }
    await query.edit_message_text(
        "Введите километраж поездки (только цифры), например: 45",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_distance")]]
        )
    )

async def cancel_add_car(query, context):
    context.user_data.pop('awaiting_car_number', None)
    await query.edit_message_text("Ок, отменил ввод номера.")
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    has_active = False
    if db_user:
        has_active = DatabaseManager.get_active_shift(db_user['id']) is not None
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=create_main_reply_keyboard(has_active)
    )

async def cancel_distance(query, context):
    payload = context.user_data.pop('awaiting_distance', None)
    if not payload:
        await query.edit_message_text("Ок.")
        return
    car_id = payload["car_id"]
    page = payload["page"]
    group_id = context.user_data.get(f"group_{car_id}")
    await show_car_services(query, context, car_id, page, group_id)

async def edit_shift(query, context, data):
    parts = data.split('_')
    if len(parts) < 3:
        return
    shift_id = int(parts[2])
    context.user_data["return_shift_id"] = shift_id
    await show_shift_detail(query, context, shift_id)

async def edit_car(query, context, data):
    parts = data.split('_')
    if len(parts) < 4:
        return
    car_id = int(parts[2])
    shift_id = int(parts[3])
    context.user_data["return_shift_id"] = shift_id
    await show_car_services(query, context, car_id, 0)

async def delete_car(query, context, data):
    parts = data.split('_')
    if len(parts) < 4:
        return
    car_id = int(parts[2])
    shift_id = int(parts[3])
    DatabaseManager.delete_car(car_id)
    await show_shift_detail(query, context, shift_id)

async def back_to_shift(query, context):
    shift_id = context.user_data.get("return_shift_id")
    if not shift_id:
        await go_back(query, context)
        return
    await show_shift_detail(query, context, shift_id)

async def show_shift_detail(query, context, shift_id: int):
    shift = DatabaseManager.get_shift(shift_id)
    if not shift:
        await query.edit_message_text("❌ Смена не найдена")
        return
    cars = DatabaseManager.get_shift_cars(shift_id)
    total = DatabaseManager.get_shift_total(shift_id)
    start_time = parse_datetime(shift['start_time'])
    end_time = parse_datetime(shift['end_time']) if shift['end_time'] else None
    start_text = start_time.strftime('%H:%M %d.%m.%Y') if start_time else "неизвестно"
    end_text = end_time.strftime('%H:%M %d.%m.%Y') if end_time else "активна"
    status = "активна" if shift['status'] == "active" else "закрыта"

    message = (
        f"🗂️ СМЕНА #{shift_id}\n"
        f"Статус: {status}\n"
        f"Начата: {start_text}\n"
        f"Завершена: {end_text}\n"
        f"Машин: {len(cars)}\n"
        f"Сумма: {format_money(total)}\n\n"
    )
    if cars:
        message += "Машины:\n"
        for car in cars:
            message += f"• {car['car_number']} — {format_money(car['total_amount'])}\n"
    else:
        message += "Машин нет."

    keyboard = []
    for car in cars:
        keyboard.append([
            InlineKeyboardButton(f"✏️ {car['car_number']}", callback_data=f"edit_car_{car['id']}_{shift_id}"),
            InlineKeyboardButton(f"🗑️ {car['car_number']}", callback_data=f"delete_car_{car['id']}_{shift_id}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def save_car(query, context, data):
    """Сохранение машины"""
    parts = data.split('_')
    if len(parts) < 2:
        return
    
    car_id = int(parts[1])
    car = DatabaseManager.get_car(car_id)
    
    if not car:
        await query.edit_message_text("❌ Машина не найдена")
        return
    
    services = DatabaseManager.get_car_services(car_id)
    
    if not services:
        await query.edit_message_text(
            f"❌ Машина {car['car_number']} не сохранена.\n"
            f"Не выбрано ни одной услуги."
        )
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=create_main_reply_keyboard(True)
        )
        return
    
    await query.edit_message_text(
        f"✅ Машина {car['car_number']} сохранена!\n"
        f"Сумма: {format_money(car['total_amount'])}\n\n"
        f"Можете добавить следующую машину."
    )
    context.user_data.pop(f"edit_mode_{car_id}", None)
    context.user_data.pop(f"group_{car_id}", None)
    return_shift_id = context.user_data.get("return_shift_id")
    if return_shift_id:
        await show_shift_detail(query, context, return_shift_id)
    else:
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=create_main_reply_keyboard(True)
        )
        user = query.from_user
        db_user = DatabaseManager.get_user(user.id)
        if db_user and DatabaseManager.get_active_shift(db_user['id']):
            await send_goal_status_from_chat(context, query.message.chat_id, db_user['id'])

async def close_shift(query, context, data):
    """Закрытие смены"""
    parts = data.split('_')
    if len(parts) < 2:
        return

    shift_id = int(parts[1])
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)

    if not db_user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден")
        return

    shift = DatabaseManager.get_shift(shift_id)
    if not shift or shift['user_id'] != db_user['id']:
        await query.edit_message_text("❌ Смена не найдена")
        return

    if shift['status'] != 'active':
        await query.edit_message_text(
            "ℹ️ Эта смена уже закрыта."
        )
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=create_main_reply_keyboard(False)
        )
        return

    total = DatabaseManager.get_shift_total(shift_id)
    tax = round(total * 0.06)
    net = total - tax

    DatabaseManager.close_shift(shift_id)
    cars = DatabaseManager.get_shift_cars(shift_id)
    start_time = parse_datetime(shift['start_time'])
    end_time = datetime.now()
    duration_hours = 0
    if start_time:
        duration_hours = max((end_time - start_time).total_seconds() / 3600, 0)
    cars_per_hour = (len(cars) / duration_hours) if duration_hours > 0 else 0
    top_services = DatabaseManager.get_shift_service_stats(shift_id)
    top_text = ""
    if top_services:
        for item in top_services:
            top_text += f"• {item['service_name']} — {item['total_count']} шт.\n"
    else:
        top_text = "Нет данных"

    await query.edit_message_text(
        f"🔚 Смена закрыта!\n\n"
        f"💰 Итого: {format_money(total)}\n"
        f"🧾 Налог 6%: {format_money(tax)}\n"
        f"✅ К выплате: {format_money(net)}\n\n"
        f"📊 Отчёт смены:\n"
        f"Машин: {len(cars)}\n"
        f"Длительность: {duration_hours:.1f} ч.\n"
        f"Машин в час: {cars_per_hour:.2f}\n\n"
        f"Топ услуг:\n{top_text}"
    )
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=create_main_reply_keyboard(False)
    )

async def go_back(query, context):
    """Возврат в главное меню"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    has_active = False
    context.user_data.pop("return_shift_id", None)

    if db_user:
        has_active = DatabaseManager.get_active_shift(db_user['id']) is not None

    await query.edit_message_text("Ок, возвращаюсь в меню.")
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=create_main_reply_keyboard(has_active)
    )

async def change_goal(query, context):
    """Запрос цели дня"""
    context.user_data['awaiting_goal'] = True
    await query.edit_message_text(
        "Введите цель дня суммой, например: 5000"
    )

async def leaderboard(query, context):
    """Лидеры смены (активные смены)"""
    leaders = DatabaseManager.get_active_leaderboard()
    if not leaders:
        await query.edit_message_text(
            "🏆 ЛИДЕРЫ СМЕНЫ\n\n"
            "Пока нет активных смен."
        )
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=create_main_reply_keyboard(False)
        )
        return

    message = "🏆 ЛИДЕРЫ СМЕНЫ (активные)\n\n"
    for idx, leader in enumerate(leaders, start=1):
        message += (
            f"{idx}. {leader['name']} — {format_money(leader['total_amount'])} "
            f"(смен: {leader['shift_count']})\n"
        )

    await query.edit_message_text(message)
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=create_main_reply_keyboard(True)
    )

async def decade_callback(query, context):
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден")
        return
    message = build_decade_summary(db_user['id'])
    await query.edit_message_text(message)
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=create_main_reply_keyboard(True)
    )

async def stats_callback(query, context):
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден")
        return
    message = build_stats_summary(db_user['id'])
    await query.edit_message_text(message)
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=create_main_reply_keyboard(True)
    )

async def export_csv(query, context):
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден")
        return
    path = build_csv_report(db_user['id'])
    if not path:
        await query.edit_message_text("❌ Не получилось создать CSV отчёт.")
        return
    with open(path, "rb") as report_file:
        await query.message.reply_document(
            document=report_file,
            filename=os.path.basename(path),
            caption="📤 Ваш CSV отчёт"
        )
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=create_main_reply_keyboard(True)
    )

async def backup_db(query, context):
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден")
        return
    backup_path = create_db_backup()
    if not backup_path:
        await query.edit_message_text("❌ Не получилось сделать резервную копию.")
        return
    with open(backup_path, "rb") as backup_file:
        await query.message.reply_document(
            document=backup_file,
            filename=os.path.basename(backup_path),
            caption="🗄️ Резервная копия базы"
        )
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=create_main_reply_keyboard(True)
    )

async def reset_data(query, context):
    await query.edit_message_text(
        "⚠️ Сброс данных пока не включён.\n"
        "Если нужно — скажите, и я добавлю подтверждение и удаление данных."
    )
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=create_main_reply_keyboard(True)
    )

async def open_shift_message(update: Update, context: CallbackContext):
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден")
        return

    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    if active_shift:
        start_time = parse_datetime(active_shift['start_time'])
        time_text = start_time.strftime('%H:%M %d.%m') if start_time else "неизвестно"
        await update.message.reply_text(
            f"❌ У вас уже есть активная смена!\n"
            f"Начата: {time_text}",
            reply_markup=create_main_reply_keyboard(True)
        )
        return

    DatabaseManager.start_shift(db_user['id'])
    await update.message.reply_text(
        f"✅ Смена открыта!\n"
        f"Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
        f"Теперь можно добавлять машины.",
        reply_markup=create_main_reply_keyboard(True)
    )

async def add_car_message(update: Update, context: CallbackContext):
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден")
        return

    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    if not active_shift:
        await update.message.reply_text(
            "❌ Нет активной смены!\nСначала откройте смену.",
            reply_markup=create_main_reply_keyboard(False)
        )
        return

    context.user_data['awaiting_car_number'] = True
    await update.message.reply_text(
        "Введите номер машины:\n\n"
        "Примеры:\n"
        "• А123ВС777\n"
        "• Х340РУ797\n"
        "• В567ТХ799\n\n"
        "Можно вводить русскими или английскими буквами.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_car")]]
        )
    )

async def current_shift_message(update: Update, context: CallbackContext):
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден")
        return

    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    if not active_shift:
        await update.message.reply_text(
            "📭 Нет активной смены.\nОткройте смену для начала работы.",
            reply_markup=create_main_reply_keyboard(False)
        )
        return

    cars = DatabaseManager.get_shift_cars(active_shift['id'])
    total = DatabaseManager.get_shift_total(active_shift['id'])
    start_time = parse_datetime(active_shift['start_time'])
    start_text = start_time.strftime('%H:%M %d.%m.%Y') if start_time else "неизвестно"

    message = (
        f"📊 ТЕКУЩАЯ СМЕНА\n\n"
        f"Начата: {start_text}\n"
        f"Машин: {len(cars)}\n"
        f"Сумма: {format_money(total)}\n\n"
    )

    if cars:
        message += "Машины в смене:\n"
        for car in cars:
            message += f"• {car['car_number']} - {format_money(car['total_amount'])}\n"

    keyboard = [
        [InlineKeyboardButton("🚗 Добавить машину", callback_data="add_car")],
        [InlineKeyboardButton("🔚 Закрыть смену", callback_data=f"close_{active_shift['id']}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]

    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def history_message(update: Update, context: CallbackContext):
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден")
        return

    shifts = DatabaseManager.get_user_shifts(db_user['id'], limit=10)
    if not shifts:
        await update.message.reply_text(
            "📜 У вас ещё нет смен.\nОткройте первую смену!",
            reply_markup=create_main_reply_keyboard(False)
        )
        return

    message = "📜 ИСТОРИЯ СМЕН\n\n"
    for shift in shifts:
        start_time = parse_datetime(shift['start_time'])
        end_time = parse_datetime(shift['end_time']) if shift['end_time'] else None
        date_str = start_time.strftime("%d.%m") if start_time else "??.??"
        start_str = start_time.strftime("%H:%M") if start_time else "??:??"

        if end_time:
            end_str = end_time.strftime("%H:%M")
            time_str = f"{start_str}-{end_str}"
            status = "✅"
        else:
            time_str = f"{start_str}"
            status = "🟢"

        total = shift.get('total_amount', 0)
        message += f"{status} {date_str} {time_str} - {format_money(total)}\n"

    keyboard = build_history_keyboard(shifts)
    await update.message.reply_text(message, reply_markup=keyboard)

async def settings_message(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🎯 Цель дня", callback_data="change_goal")],
        [InlineKeyboardButton("🗑️ Сбросить данные", callback_data="reset_data")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    await update.message.reply_text(
        "⚙️ НАСТРОЙКИ\n\nВыберите параметр:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def leaderboard_message(update: Update, context: CallbackContext):
    leaders = DatabaseManager.get_active_leaderboard()
    if not leaders:
        await update.message.reply_text(
            "🏆 ЛИДЕРЫ СМЕНЫ\n\nПока нет активных смен.",
            reply_markup=create_main_reply_keyboard(False)
        )
        return

    message = "🏆 ЛИДЕРЫ СМЕНЫ (активные)\n\n"
    for idx, leader in enumerate(leaders, start=1):
        message += (
            f"{idx}. {leader['name']} — {format_money(leader['total_amount'])} "
            f"(смен: {leader['shift_count']})\n"
        )

    await update.message.reply_text(
        message,
        reply_markup=create_main_reply_keyboard(True)
    )

async def decade_message(update: Update, context: CallbackContext):
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден")
        return
    message = build_decade_summary(db_user['id'])
    await update.message.reply_text(
        message,
        reply_markup=create_main_reply_keyboard(True)
    )

async def stats_message(update: Update, context: CallbackContext):
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден")
        return
    message = build_stats_summary(db_user['id'])
    await update.message.reply_text(
        message,
        reply_markup=create_main_reply_keyboard(True)
    )

def render_car_services(context: CallbackContext, car_id: int, page: int = 0, group_id: Optional[int] = None):
    car = DatabaseManager.get_car(car_id)
    if not car:
        return None, None

    services = DatabaseManager.get_car_services(car_id)
    services_text = ""
    for service in services:
        services_text += f"• {service['service_name']} ({service['price']}₽) ×{service['quantity']}\n"

    if not services_text:
        services_text = "Нет выбранных услуг\n"

    edit_mode = get_edit_mode(context, car_id)
    mode_text = "✏️ Режим: удаление" if edit_mode else "➕ Режим: добавление"
    price_mode = get_price_mode(context)

    message = (
        f"🚗 Машина: {car['car_number']}\n"
        f"Итог: {format_money(car['total_amount'])}\n\n"
        f"{mode_text}\n\n"
        f"Услуги:\n{services_text}\n"
        f"Выберите ещё:"
    )

    keyboard = create_services_keyboard(car_id, page, edit_mode, price_mode, group_id)
    if context.user_data.get("return_shift_id"):
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton("⬅️ К смене", callback_data="back_shift")]
        )
    return message, keyboard

async def show_car_services(query, context: CallbackContext, car_id: int, page: int = 0, group_id: Optional[int] = None):
    """Показать услуги машины"""
    message, keyboard = render_car_services(context, car_id, page, group_id)
    if not message:
        await query.edit_message_text("❌ Машина не найдена")
        return
    await query.edit_message_text(message, reply_markup=keyboard)

# ========== ОБРАБОТЧИК ОШИБОК ==========

async def error_handler(update: Update, context: CallbackContext):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка.\n"
                "Попробуйте ещё раз или перезапустите бота командой /start"
            )
        except:
            pass

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    
    # Обработчик callback-кнопок
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота
    logger.info("🤖 Бот запускается...")
    print("=" * 60)
    print("🚀 БОТ ДЛЯ УЧЁТА УСЛУГ - УПРОЩЕННАЯ ВЕРСИЯ")
    print("✅ Просто работает")
    print("=" * 60)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
