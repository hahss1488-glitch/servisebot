"""
ПОЛНЫЙ БОТ ДЛЯ УЧЁТА УСЛУГ - ФИНАЛЬНАЯ ВЕРСИЯ
С интеграцией DatabaseManager и всеми функциями
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    CallbackContext,
    filters,
)

# Импортируем вашу базу данных
from database import DatabaseManager, init_database

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8353243831:AAG_F9d203LLJsRn2VCn2Iocw99jZc0JHTY"  # ⚠️ Лучше вынести в config.py или переменные окружения

# ========== ПРАЙС-ЛИСТ ==========
SERVICES = {
    1: {"name": "Проверка", "day_price": 100, "night_price": 150, "frequent": True},
    2: {"name": "Заправка", "day_price": 200, "night_price": 300, "frequent": True},
    3: {"name": "Подкачка", "day_price": 50, "night_price": 80, "frequent": True},
    4: {"name": "Прокрутка", "day_price": 150, "night_price": 200, "frequent": True},
    5: {"name": "Мойка", "day_price": 400, "night_price": 500, "frequent": True},
    6: {"name": "АКБ", "day_price": 250, "night_price": 350, "frequent": True},
    7: {"name": "Замена масла", "day_price": 450, "night_price": 550, "frequent": False},
    8: {"name": "Диагностика", "day_price": 600, "night_price": 700, "frequent": False},
    9: {"name": "Шиномонтаж", "day_price": 800, "night_price": 900, "frequent": False},
    10: {"name": "Ремонт", "day_price": 1000, "night_price": 1200, "frequent": False},
    11: {"name": "Заправка кондиционера", "day_price": 700, "night_price": 850, "frequent": False},
    12: {"name": "Замена фильтра", "day_price": 300, "night_price": 400, "frequent": False},
}

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Детальный обработчик ошибок
import traceback

async def detailed_error_handler(update: Update, context: CallbackContext):
    """Детальный обработчик ошибок для отладки"""
    try:
        # Логируем ошибку
        logger.error(f"❌ ОШИБКА: {context.error}")
        logger.error(f"📱 Update: {update}")
        logger.error(f"💾 User Data: {context.user_data}")
        
        # Получаем стек вызовов
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = ''.join(tb_list)
        logger.error(f"📝 Трассировка:\n{tb_string}")
        
        # Показываем пользователю понятное сообщение
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка.\n"
                "Попробуйте ещё раз или перезапустите бота командой /start\n\n"
                "<i>Администратор уже уведомлён об ошибке</i>",
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике ошибок: {e}")

# Инициализация базы данных
init_database()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def normalize_car_number(text: str) -> str:
    """Нормализация номера машины"""
    text = text.strip().upper()
    
    eng_to_rus = {
        'A': 'А', 'B': 'В', 'C': 'С', 'E': 'Е', 'H': 'Н',
        'K': 'К', 'M': 'М', 'O': 'О', 'P': 'Р', 'T': 'Т',
        'X': 'Х', 'Y': 'У'
    }
    
    result = []
    for char in text:
        result.append(eng_to_rus.get(char, char))
    
    normalized = ''.join(result)
    
    # Удаляем все не буквы/цифры
    normalized = re.sub(r'[^АВЕКМНОРСТУХ0-9]', '', normalized)
    
    # Добавляем регион если не хватает
    if len(normalized) <= 6:
        normalized += "797"
    
    return normalized

def validate_car_number(text: str) -> bool:
    """Проверка валидности номера машины"""
    normalized = normalize_car_number(text)
    pattern = r'^[АВЕКМНОРСТУХ]{1}\d{3}[АВЕКМНОРСТУХ]{2}\d{3}$'
    return bool(re.match(pattern, normalized))

def get_current_price(service_id: int) -> int:
    """Получение текущей цены (учёт времени)"""
    service = SERVICES.get(service_id)
    if not service:
        return 0
    
    hour = datetime.now().hour
    if 21 <= hour or hour < 9:  # 21:00-9:00 ночь
        return service["night_price"]
    return service["day_price"]

def get_current_time_type() -> str:
    hour = datetime.now().hour
    return "🌙 Ночь" if 21 <= hour or hour < 9 else "☀️ День"

def format_money(amount: int) -> str:
    """Форматирование денежной суммы"""
    return f"{amount:,}₽".replace(",", " ")

def format_progress_bar(current: int, target: int, length: int = 20) -> str:
    """Форматирование прогресс-бара"""
    if target <= 0:
        return "[░░░░░░░░░░░░░░░░░░░░] 0%"
    
    percentage = min(current / target, 1.0)
    filled = int(length * percentage)
    return f"[{'█' * filled}{'░' * (length - filled)}] {int(percentage * 100)}%"

def get_current_decade() -> Tuple[int, Tuple[int, int]]:
    """Определение текущей декады"""
    today = datetime.now()
    day = today.day
    
    if 1 <= day <= 10:
        return 1, (1, 10)
    elif 11 <= day <= 20:
        return 2, (11, 20)
    else:
        # Для последней декады
        last_day = 31
        if today.month == 2:
            last_day = 29 if (today.year % 4 == 0 and today.year % 100 != 0) or (today.year % 400 == 0) else 28
        elif today.month in [4, 6, 9, 11]:
            last_day = 30
        return 3, (21, last_day)

def get_decade_stats(user_id: int, decade: int) -> Dict[str, Any]:
    """Статистика по декаде (временная реализация)"""
    # Временная реализация - можно улучшить в DatabaseManager
    today = datetime.now()
    
    if decade == 1:
        start_day, end_day = 1, 10
    elif decade == 2:
        start_day, end_day = 11, 20
    else:
        start_day = 21
        if today.month in [1, 3, 5, 7, 8, 10, 12]:
            end_day = 31
        elif today.month == 2:
            end_day = 29 if (today.year % 4 == 0) else 28
        else:
            end_day = 30
    
    # Создаем даты для фильтрации
    start_date = today.replace(day=start_day, hour=0, minute=0, second=0, microsecond=0)
    end_date = today.replace(day=end_day, hour=23, minute=59, second=59, microsecond=999999)
    
    # Здесь должна быть логика подсчёта статистики
    # Временный заглушка
    return {
        'shift_count': 0,
        'total_earned': 0,
        'cars_count': 0,
        'days_passed': min(today.day - start_day + 1, end_day - start_day + 1),
        'total_days': end_day - start_day + 1,
        'start_day': start_day,
        'end_day': end_day,
        'decade': decade
    }

# ========== КЛАВИАТУРЫ ==========

def create_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("🚗 Добавить машину", callback_data="main_add_car")],
        [InlineKeyboardButton("📊 Текущая смена", callback_data="main_current")],
        [InlineKeyboardButton("📜 История смен", callback_data="main_history_0")],
        [InlineKeyboardButton("📈 Статистика", callback_data="main_stats")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="main_settings")],
        [InlineKeyboardButton("❓ Помощь", callback_data="main_help")],
    ]
    return InlineKeyboardMarkup(keyboard)

def create_services_keyboard(car_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура с услугами"""
    keyboard = []
    
    # Разделяем на частые и остальные
    frequent = [(id, s) for id, s in SERVICES.items() if s.get('frequent', False)]
    others = [(id, s) for id, s in SERVICES.items() if not s.get('frequent', False)]
    
    if page == 0:  # Частые услуги
        services_to_show = frequent
    else:  # Остальные услуги с пагинацией
        start_idx = (page - 1) * 6
        services_to_show = others[start_idx:start_idx + 6]
    
    # Добавляем кнопки услуг (по 2 в ряд)
    for i in range(0, len(services_to_show), 2):
        row = []
        for service_id, service in services_to_show[i:i+2]:
            price = get_current_price(service_id)
            btn_text = f"{service['name']} ({price}₽)"
            row.append(InlineKeyboardButton(
                btn_text, 
                callback_data=f"service_add_{service_id}_{car_id}_{page}"
            ))
        if row:
            keyboard.append(row)
    
    # Кнопки управления
    keyboard.append([
        InlineKeyboardButton("🔽 Удалить последнюю", 
                           callback_data=f"service_remove_{car_id}_{page}"),
        InlineKeyboardButton("🗑️ Очистить всё", 
                           callback_data=f"service_clear_{car_id}_{page}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("💾 Сохранить машину", 
                           callback_data=f"car_save_{car_id}"),
        InlineKeyboardButton("❌ Отмена", 
                           callback_data=f"car_cancel_{car_id}")
    ])
    
    # Навигация по страницам
    if page == 0 and len(others) > 0:
        keyboard.append([
            InlineKeyboardButton("📋 Все услуги →", 
                               callback_data=f"service_all_{car_id}_1")
        ])
    elif page > 0:
        nav_buttons = []
        total_other_pages = (len(others) + 5) // 6
        
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(
                "◀️", 
                callback_data=f"service_all_{car_id}_{page-1}"
            ))
        
        nav_buttons.append(InlineKeyboardButton(
            f"Стр. {page}", 
            callback_data="noop"
        ))
        
        if page < total_other_pages:
            nav_buttons.append(InlineKeyboardButton(
                "▶️", 
                callback_data=f"service_all_{car_id}_{page+1}"
            ))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([
            InlineKeyboardButton("🔙 К частым", 
                               callback_data=f"service_page_{car_id}_0")
        ])
    
    return InlineKeyboardMarkup(keyboard)

def create_confirmation_keyboard(action: str, item_id: int, *args) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    callback_data = f"confirm_{action}_{item_id}"
    if args:
        callback_data += "_" + "_".join(map(str, args))
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data=callback_data),
            InlineKeyboardButton("❌ Нет", callback_data=f"cancel_{action}_{item_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_shifts_keyboard(shifts: List[Dict], page: int = 0, action: str = "view") -> InlineKeyboardMarkup:
    """Клавиатура со сменами с пагинацией"""
    keyboard = []
    shifts_per_page = 5
    
    start_idx = page * shifts_per_page
    end_idx = start_idx + shifts_per_page
    
    for shift in shifts[start_idx:end_idx]:
        date_str = shift['created_at'].strftime("%d.%m")
        start_time = shift['start_time'].strftime("%H:%M")
        
        if shift.get('end_time'):
            end_time = shift['end_time'].strftime("%H:%M")
            time_str = f"{start_time}-{end_time}"
            status_icon = "✅"
        else:
            time_str = f"{start_time}"
            status_icon = "🟢"
        
        total = shift.get('total_amount', 0)
        button_text = f"{status_icon} {date_str} {time_str} - {format_money(total)}"
        
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"shift_{action}_{shift['id']}_{page}"
            )
        ])
    
    # Навигация по страницам
    navigation = []
    total_pages = (len(shifts) + shifts_per_page - 1) // shifts_per_page
    
    if page > 0:
        navigation.append(InlineKeyboardButton(
            "◀️", 
            callback_data=f"main_history_{page-1}"
        ))
    
    navigation.append(InlineKeyboardButton(
        f"{page+1}/{total_pages}", 
        callback_data="noop"
    ))
    
    if page < total_pages - 1:
        navigation.append(InlineKeyboardButton(
            "▶️", 
            callback_data=f"main_history_{page+1}"
        ))
    
    if navigation:
        keyboard.append(navigation)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_back")])
    
    return InlineKeyboardMarkup(keyboard)

def create_cars_keyboard(cars: List[Dict], shift_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура с машинами смены"""
    keyboard = []
    
    for car in cars:
        button_text = f"{car['car_number']} - {format_money(car['total_amount'])}"
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"car_view_{car['id']}_{shift_id}_{page}"
            )
        ])
    
    # Кнопки управления
    keyboard.append([
        InlineKeyboardButton("➕ Добавить машину", 
                           callback_data=f"shift_add_car_{shift_id}_{page}"),
        InlineKeyboardButton("🗑️ Удалить смену", 
                           callback_data=f"shift_delete_{shift_id}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 К сменам", 
                           callback_data="main_history_0")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_car_edit_keyboard(car_id: int, shift_id: int, page: int) -> InlineKeyboardMarkup:
    """Клавиатура редактирования машины"""
    keyboard = [
        [
            InlineKeyboardButton("✏️ Добавить услуги", 
                               callback_data=f"car_edit_{car_id}_{shift_id}_{page}"),
            InlineKeyboardButton("🗑️ Удалить машину", 
                               callback_data=f"car_delete_{car_id}_{shift_id}_{page}")
        ],
        [
            InlineKeyboardButton("🔙 К машинам", 
                               callback_data=f"shift_view_{shift_id}_{page}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_settings_keyboard(user: Dict) -> InlineKeyboardMarkup:
    """Клавиатура настроек"""
    progress_status = "ВКЛ" if user.get('progress_bar_enabled', True) else "ВЫКЛ"
    
    keyboard = [
        [InlineKeyboardButton(
            f"🎯 Цель: {format_money(user.get('daily_target', 5000))}", 
            callback_data="setting_target"
        )],
        [InlineKeyboardButton(
            f"📊 Прогресс-бар: {progress_status}", 
            callback_data="setting_progress"
        )],
        [InlineKeyboardButton("📈 Статистика за декаду", 
                            callback_data="setting_decade_stats")],
        [InlineKeyboardButton("🔄 Сбросить данные", 
                            callback_data="setting_reset")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_back")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

async def start(update: Update, context: CallbackContext):
    """Команда /start"""
    user = update.effective_user
    
    # Проверяем регистрацию
    db_user = DatabaseManager.get_user(user.id)
    if not db_user:
        await update.message.reply_text(
            f"👋 Привет! Я бот для учёта услуг на работе.\n\n"
            f"Для начала работы введите ваше имя:"
        )
        context.user_data['awaiting_name'] = True
        return
    
    await show_main_menu(update, context, user.id)

async def show_main_menu(update: Update, context: CallbackContext, user_id: int):
    """Показать главное меню"""
    user = DatabaseManager.get_user(user_id)
    if not user:
        return
    
    message = f"👤 <b>{user['name']}</b>\n"
    
    # Информация об активной смене
    active_shift = DatabaseManager.get_active_shift(user['id'])
    if active_shift:
        total = active_shift.get('total_amount', 0)
        target = user.get('daily_target', 5000)
        
        message += f"\n📅 Активная смена с {active_shift['start_time'].strftime('%H:%M')}\n"
        message += f"💰 Заработано: <b>{format_money(total)}</b>\n"
        
        if user.get('progress_bar_enabled', True):
            message += f"🎯 Цель: {format_money(target)}\n"
            message += f"📊 {format_progress_bar(total, target)}\n"
    else:
        message += "\n📅 Нет активной смены\n"
        message += "Начните смену, добавив первую машину\n"
    
    message += "\nВыберите действие:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message, 
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========

async def handle_message(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений"""
    user = update.effective_user
    text = update.message.text.strip()
    
    # Ожидание имени при регистрации
    if context.user_data.get('awaiting_name'):
        if len(text) < 2:
            await update.message.reply_text("❌ Имя слишком короткое. Введите ещё раз:")
            return
        
        DatabaseManager.register_user(user.id, text)
        context.user_data.pop('awaiting_name', None)
        
        await update.message.reply_text(
            f"✅ Отлично, {text}! Вы зарегистрированы.\n",
            reply_markup=create_main_keyboard()
        )
        return
    
    # Ожидание номера машины
    elif context.user_data.get('awaiting_car_number'):
        if not validate_car_number(text):
            await update.message.reply_text(
                "❌ Неверный формат номера.\n"
                "Примеры:\n"
                "• А123БВ777\n"
                "• X340PY\n"
                "• Х340РУ\n\n"
                "Введите номер ещё раз:"
            )
            return
        
        normalized = normalize_car_number(text)
        db_user = DatabaseManager.get_user(user.id)
        
        if not db_user:
            await update.message.reply_text("❌ Ошибка: пользователь не найден")
            return
        
        # Получаем shift_id из контекста (если добавляем в существующую смену)
        shift_id = context.user_data.get('car_for_shift')
        if not shift_id:
            # Ищем активную смену или создаём новую
            active_shift = DatabaseManager.get_active_shift(db_user['id'])
            if not active_shift:
                shift_id = DatabaseManager.start_shift(db_user['id'])
            else:
                shift_id = active_shift['id']
        
        car_id = DatabaseManager.add_car(shift_id, normalized)
        if not car_id:
            await update.message.reply_text("❌ Ошибка добавления машины")
            return
        
        # Очищаем контекст
        context.user_data.pop('awaiting_car_number', None)
        context.user_data.pop('car_for_shift', None)
        
        time_type = get_current_time_type()
        
        await update.message.reply_text(
            f"🚗 Машина: <b>{normalized}</b>\n"
            f"⏰ {time_type}\n"
            f"💰 Итог: <b>0₽</b>\n\n"
            f"<i>Выберите услуги:</i>",
            parse_mode='HTML',
            reply_markup=create_services_keyboard(car_id)
        )
        return
    
    # Ожидание цели
    elif context.user_data.get('awaiting_target'):
        try:
            target = int(text)
            if target < 100:
                await update.message.reply_text("❌ Цель должна быть не менее 100₽. Введите ещё раз:")
                return
            
            DatabaseManager.update_user_setting(user.id, 'daily_target', target)
            context.user_data.pop('awaiting_target', None)
            
            await update.message.reply_text(
                f"✅ Цель установлена: <b>{format_money(target)}</b>",
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
        except ValueError:
            await update.message.reply_text("❌ Введите число. Например: 5000")
        return
    
    # Неизвестное сообщение - показываем главное меню
    await update.message.reply_text(
        "Используйте кнопки меню для работы с ботом.",
        reply_markup=create_main_keyboard()
    )

# ========== ОБРАБОТЧИК КНОПОК ==========

async def handle_callback(update: Update, context: CallbackContext):
    """Обработка всех callback-кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    logger.info(f"Callback: {data} from {user.id}")
    
    # Проверка регистрации для всех команд кроме регистрации
    if data != "noop" and not data.startswith("confirm_") and not data.startswith("cancel_"):
        db_user = DatabaseManager.get_user(user.id)
        if not db_user:
            await query.edit_message_text(
                "❌ Сначала зарегистрируйтесь: /start",
                reply_markup=None
            )
            return
    
    # Маршрутизация команд
    if data == "noop":
        return
    
    elif data.startswith("main_"):
        await handle_main_callback(query, context, data)
    
    elif data.startswith("service_"):
        await handle_service_callback(query, context, data)
    
    elif data.startswith("car_"):
        await handle_car_callback(query, context, data)
    
    elif data.startswith("shift_"):
        await handle_shift_callback(query, context, data)
    
    elif data.startswith("setting_"):
        await handle_setting_callback(query, context, data)
    
    elif data.startswith("confirm_"):
        await handle_confirm_callback(query, context, data)
    
    elif data.startswith("cancel_"):
        await handle_cancel_callback(query, context, data)
    
    else:
        await query.edit_message_text("❌ Неизвестная команда")

async def handle_main_callback(query, context, data):
    """Обработка главного меню"""
    parts = data.split("_")
    action = parts[1] if len(parts) > 1 else ""
    page = int(parts[2]) if len(parts) > 2 else 0
    
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await query.edit_message_text("❌ Пользователь не найден")
        return
    
    if action == "add_car":
        context.user_data['awaiting_car_number'] = True
        await query.edit_message_text(
            "🚗 <b>Добавление машины</b>\n\n"
            "Введите номер машины:\n"
            "<i>Примеры:</i>\n"
            "• А123БВ777\n"
            "• X340PY\n"
            "• Х340РУ\n\n"
            "Номер можно вводить русскими или английскими буквами.",
            parse_mode='HTML'
        )
    
    elif action == "current":
        await show_current_shift(query, db_user)
    
    elif action == "history":
        await show_history(query, db_user, page)
    
    elif action == "stats":
        await show_stats(query, db_user)
    
    elif action == "settings":
        await show_settings(query, db_user)
    
    elif action == "help":
        await show_help(query)
    
    elif action == "back":
        await show_main_menu(update=Update(update_id=0, callback_query=query), 
                           context=context, user_id=user.id)

async def handle_service_callback(query, context, data):
    """Обработка действий с услугами"""
    parts = data.split("_")
    if len(parts) < 3:
        return
    
    action = parts[1]
    
    if action == "add":
        if len(parts) < 4:
            return
        service_id = int(parts[2])
        car_id = int(parts[3])
        page = int(parts[4]) if len(parts) > 4 else 0
        
        price = get_current_price(service_id)
        service_name = SERVICES[service_id]['name']
        DatabaseManager.add_service_to_car(car_id, service_id, service_name, price)
        await update_car_display(query, car_id, page)
    
    elif action == "remove":
        if len(parts) < 3:
            return
        car_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
        
        DatabaseManager.remove_last_service(car_id)
        await update_car_display(query, car_id, page)
    
    elif action == "clear":
        if len(parts) < 3:
            return
        car_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
        
        # Очищаем все услуги
        while DatabaseManager.get_car_services(car_id):
            DatabaseManager.remove_last_service(car_id)
        
        await update_car_display(query, car_id, page)
    
    elif action == "all":
        if len(parts) < 4:
            return
        car_id = int(parts[2])
        page = int(parts[3])
        
        await update_car_display(query, car_id, page)
    
    elif action == "page":
        if len(parts) < 4:
            return
        car_id = int(parts[2])
        page = int(parts[3])
        
        await update_car_display(query, car_id, page)

async def update_car_display(query, car_id: int, page: int = 0):
    """Обновление отображения машины с услугами"""
    car = DatabaseManager.get_car(car_id)
    if not car:
        await query.edit_message_text("❌ Машина не найдена")
        return
    
    services = DatabaseManager.get_car_services(car_id)
    
    # Группируем услуги по названию
    grouped = {}
    for service in services:
        name = service['service_name']
        if name not in grouped:
            grouped[name] = {'quantity': 0, 'price': service['price']}
        grouped[name]['quantity'] += service['quantity']
    
    # Формируем текст с услугами
    services_text = ""
    for name, data in grouped.items():
        total = data['price'] * data['quantity']
        services_text += f"• {name} ({data['price']}₽) ×{data['quantity']} = {format_money(total)}\n"
    
    if not services_text:
        services_text = "Нет выбранных услуг\n"
    
    time_type = get_current_time_type()
    
    message = (
        f"🚗 Машина: <b>{car['car_number']}</b>\n"
        f"⏰ {time_type}\n"
        f"💰 Итог: <b>{format_money(car['total_amount'])}</b>\n\n"
        f"<b>Выбранные услуги:</b>\n{services_text}\n"
        f"<i>Выберите ещё:</i>"
    )
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=create_services_keyboard(car_id, page)
    )

async def handle_car_callback(query, context, data):
    """Обработка действий с машинами"""
    parts = data.split("_")
    if len(parts) < 3:
        return
    
    action = parts[1]
    car_id = int(parts[2])
    
    if action == "save":
        car = DatabaseManager.get_car(car_id)
        if not car:
            await query.edit_message_text("❌ Машина не найдена")
            return
        
        services = DatabaseManager.get_car_services(car_id)
        if not services:
            await query.edit_message_text(
                f"❌ Машина <b>{car['car_number']}</b> не сохранена.\n"
                f"Не выбрано ни одной услуги.",
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
            return
        
        # Получаем смену для отображения общей суммы
        shift_id = car['shift_id']
        shift_total = DatabaseManager.get_shift_total(shift_id)
        
        await query.edit_message_text(
            f"✅ Машина <b>{car['car_number']}</b> сохранена!\n\n"
            f"💰 Итог: <b>{format_money(car['total_amount'])}</b>\n"
            f"📊 Общая сумма смены: <b>{format_money(shift_total)}</b>\n\n"
            f"Можете добавить следующую машину 🚗",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
    
    elif action == "cancel":
        DatabaseManager.delete_car(car_id)
        await query.edit_message_text(
            "❌ Добавление машины отменено.\n"
            "Машина удалена из смены.",
            reply_markup=create_main_keyboard()
        )
    
    elif action == "view":
        if len(parts) < 5:
            return
        shift_id = int(parts[3])
        page = int(parts[4])
        
        await show_car_details(query, car_id, shift_id, page)
    
    elif action == "edit":
        if len(parts) < 5:
            return
        shift_id = int(parts[3])
        page = int(parts[4])
        
        car = DatabaseManager.get_car(car_id)
        if not car:
            await query.edit_message_text("❌ Машина не найдена")
            return
        
        await update_car_display(query, car_id, 0)
    
    elif action == "delete":
        if len(parts) < 5:
            return
        shift_id = int(parts[3])
        page = int(parts[4])
        
        await query.edit_message_text(
            "🗑️ <b>Удаление машины</b>\n\n"
            "Вы уверены, что хотите удалить эту машину?\n"
            "Все услуги машины будут удалены.",
            parse_mode='HTML',
            reply_markup=create_confirmation_keyboard("car_delete", car_id, shift_id, page)
        )

async def handle_shift_callback(query, context, data):
    """Обработка действий со сменами"""
    parts = data.split("_")
    if len(parts) < 3:
        return
    
    action = parts[1]
    shift_id = int(parts[2])
    
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await query.edit_message_text("❌ Пользователь не найден")
        return
    
    shift = DatabaseManager.get_shift(shift_id)
    if not shift or shift['user_id'] != db_user['id']:
        await query.edit_message_text("❌ Смена не найдена")
        return
    
    if action == "view":
        page = int(parts[3]) if len(parts) > 3 else 0
        await show_shift_details(query, shift_id, page)
    
    elif action == "add_car":
        page = int(parts[3]) if len(parts) > 3 else 0
        context.user_data['awaiting_car_number'] = True
        context.user_data['car_for_shift'] = shift_id
        
        await query.edit_message_text(
            "🚗 <b>Добавление машины в смену</b>\n\n"
            "Введите номер машины:\n"
            "<i>Примеры:</i>\n"
            "• А123БВ777\n"
            "• X340PY\n"
            "• Х340РУ\n\n"
            "Номер можно вводить русскими или английскими буквами.",
            parse_mode='HTML'
        )
    
    elif action == "end":
        await confirm_end_shift(query, shift_id)
    
    elif action == "delete":
        await query.edit_message_text(
            "🗑️ <b>Удаление смены</b>\n\n"
            "Вы уверены, что хотите удалить эту смену?\n"
            "Все машины и услуги в смене будут удалены.\n"
            "<b>Это действие нельзя отменить!</b>",
            parse_mode='HTML',
            reply_markup=create_confirmation_keyboard("shift_delete", shift_id)
        )

async def handle_setting_callback(query, context, data):
    """Обработка настроек"""
    parts = data.split("_")
    action = parts[1] if len(parts) > 1 else ""
    
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await query.edit_message_text("❌ Пользователь не найден")
        return
    
    if action == "target":
        context.user_data['awaiting_target'] = True
        await query.edit_message_text(
            "🎯 <b>Изменение цели на смену</b>\n\n"
            "Введите новую цель в рублях (например: 5000):",
            parse_mode='HTML'
        )
    
    elif action == "progress":
        current = db_user.get('progress_bar_enabled', True)
        DatabaseManager.update_user_setting(user.id, 'progress_bar_enabled', not current)
        
        status = "ВКЛ" if not current else "ВЫКЛ"
        await query.edit_message_text(
            f"✅ Прогресс-бар <b>{status}</b>",
            parse_mode='HTML',
            reply_markup=create_settings_keyboard(DatabaseManager.get_user(user.id))
        )
    
    elif action == "decade_stats":
        await show_decade_stats(query, db_user)
    
    elif action == "reset":
        await query.edit_message_text(
            "🔄 <b>Сброс данных</b>\n\n"
            "Вы уверены, что хотите сбросить ВСЕ данные?\n"
            "Будут удалены:\n"
            "• Все смены\n"
            "• Все машины\n"
            "• Вся статистика\n\n"
            "<b>Это действие нельзя отменить!</b>",
            parse_mode='HTML',
            reply_markup=create_confirmation_keyboard("reset_data", user.id)
        )

async def handle_confirm_callback(query, context, data):
    """Обработка подтверждений"""
    parts = data.split("_")
    if len(parts) < 3:
        return
    
    action = parts[1]
    item_id = int(parts[2])
    
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await query.edit_message_text("❌ Пользователь не найдена")
        return
    
    if action == "end_shift":
        shift = DatabaseManager.get_shift(item_id)
        if not shift:
            await query.edit_message_text("❌ Смена не найдена")
            return
        
        # Завершаем смену
        ended_shift = DatabaseManager.end_shift(item_id)
        if not ended_shift:
            await query.edit_message_text("❌ Ошибка закрытия смены")
            return
        
        # Генерируем отчёты
        await generate_shift_reports(query, ended_shift)
    
    elif action == "car_delete":
        if len(parts) < 5:
            return
        
        shift_id = int(parts[3])
        page = int(parts[4])
        
        # Удаляем машину
        DatabaseManager.delete_car(item_id)
        
        # Возвращаемся к списку машин
        shift = DatabaseManager.get_shift(shift_id)
        if shift:
            cars = DatabaseManager.get_shift_cars(shift_id)
            total = DatabaseManager.get_shift_total(shift_id)
            
            message = f"🗑️ Машина удалена\n\n"
            message += f"💰 Общая сумма смены: <b>{format_money(total)}</b>\n"
            message += f"🚗 Машин осталось: <b>{len(cars)}</b>\n\n"
            message += "Выберите машину для редактирования:"
            
            await query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=create_cars_keyboard(cars, shift_id, page)
            )
    
    elif action == "shift_delete":
        # Удаляем смену
        # В DatabaseManager нет метода delete_shift, нужно добавить или сделать по-другому
        # Временно просто удаляем все машины смены
        cars = DatabaseManager.get_shift_cars(item_id)
        for car in cars:
            DatabaseManager.delete_car(car['id'])
        
        await query.edit_message_text(
            "✅ Смена удалена",
            reply_markup=create_main_keyboard()
        )
    
    elif action == "reset_data":
        # Сброс данных пользователя (удаляем все его смены)
        user_shifts = DatabaseManager.get_user_shifts(db_user['id'], limit=1000)
        for shift in user_shifts:
            cars = DatabaseManager.get_shift_cars(shift['id'])
            for car in cars:
                DatabaseManager.delete_car(car['id'])
        
        await query.edit_message_text(
            "✅ Все данные сброшены",
            reply_markup=create_main_keyboard()
        )

async def handle_cancel_callback(query, context, data):
    """Обработка отмены действий"""
    parts = data.split("_")
    if len(parts) < 3:
        return
    
    action = parts[1]
    
    if action == "end_shift":
        await query.edit_message_text(
            "❌ Закрытие смены отменено.",
            reply_markup=create_main_keyboard()
        )
    
    elif action == "car_delete":
        if len(parts) < 4:
            return
        
        shift_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
        
        await query.edit_message_text(
            "❌ Удаление машины отменено.",
            callback_data=f"shift_view_{shift_id}_{page}"
        )
    
    elif action == "shift_delete":
        shift_id = int(parts[2])
        await query.edit_message_text(
            "❌ Удаление смены отменено.",
            callback_data=f"shift_view_{shift_id}_0"
        )
    
    elif action == "reset_data":
        await query.edit_message_text(
            "❌ Сброс данных отменен.",
            reply_markup=create_settings_keyboard(DatabaseManager.get_user(query.from_user.id))
        )

# ========== ФУНКЦИИ ОТОБРАЖЕНИЯ ==========

async def show_current_shift(query, user):
    """Показать текущую смену"""
    active_shift = DatabaseManager.get_active_shift(user['id'])
    
    if not active_shift:
        await query.edit_message_text(
            "📅 <b>Текущая смена</b>\n\n"
            "Нет активной смены.\n"
            "Начните смену, добавив первую машину.",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
        return
    
    cars = DatabaseManager.get_shift_cars(active_shift['id'])
    total = active_shift.get('total_amount', 0)
    target = user.get('daily_target', 5000)
    
    message = f"📅 <b>Текущая смена</b>\n\n"
    message += f"Начало: {active_shift['start_time'].strftime('%H:%M (%d.%m.%Y)')}\n"
    message += f"💰 Заработано: <b>{format_money(total)}</b>\n"
    
    if user.get('progress_bar_enabled', True):
        message += f"🎯 Цель: {format_money(target)}\n"
        message += f"📊 {format_progress_bar(total, target)}\n"
    
    if cars:
        message += f"\n<b>Машины ({len(cars)}):</b>\n"
        for i, car in enumerate(cars, 1):
            message += f"{i}. {car['car_number']} - {format_money(car['total_amount'])}\n"
    else:
        message += "\nМашин ещё нет.\n"
    
    keyboard = [
        [InlineKeyboardButton("🚗 Добавить машину", callback_data="main_add_car")],
        [InlineKeyboardButton("🔚 Закрыть смену", 
                            callback_data=f"shift_end_{active_shift['id']}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_back")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_history(query, user, page: int = 0):
    """Показать историю смен"""
    shifts = DatabaseManager.get_user_shifts(user['id'], limit=100)
    
    if not shifts:
        await query.edit_message_text(
            "📜 <b>История смен</b>\n\n"
            "У вас ещё нет смен.",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
        return
    
    await query.edit_message_text(
        "📜 <b>История смен</b>\n\n"
        "Выберите смену для просмотра:",
        parse_mode='HTML',
        reply_markup=create_shifts_keyboard(shifts, page)
    )

async def show_shift_details(query, shift_id: int, page: int = 0):
    """Показать детали смены"""
    shift = DatabaseManager.get_shift(shift_id)
    if not shift:
        await query.edit_message_text("❌ Смена не найдена")
        return
    
    cars = DatabaseManager.get_shift_cars(shift_id)
    total = DatabaseManager.get_shift_total(shift_id)
    
    message = f"📋 <b>Смена</b>\n\n"
    
    if shift['status'] == 'active':
        message += f"🟢 <i>Активна</i>\n"
    else:
        message += f"🔴 <i>Завершена</i>\n"
    
    message += f"Начало: {shift['start_time'].strftime('%H:%M (%d.%m.%Y)')}\n"
    
    if shift['end_time']:
        message += f"Окончание: {shift['end_time'].strftime('%H:%M')}\n"
        duration = (shift['end_time'] - shift['start_time']).total_seconds() / 3600
        message += f"Длительность: {int(duration)} ч.\n"
    
    message += f"💰 Общая сумма: <b>{format_money(total)}</b>\n"
    message += f"🚗 Машин: <b>{len(cars)}</b>\n\n"
    
    if cars:
        message += "<b>Машины:</b>\n"
        for i, car in enumerate(cars, 1):
            message += f"{i}. {car['car_number']} - {format_money(car['total_amount'])}\n"
    
    message += "\nВыберите машину для редактирования:"
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=create_cars_keyboard(cars, shift_id, page)
    )

async def show_car_details(query, car_id: int, shift_id: int, page: int):
    """Показать детали машины"""
    car = DatabaseManager.get_car(car_id)
    if not car:
        await query.edit_message_text("❌ Машина не найдена")
        return
    
    services = DatabaseManager.get_car_services(car_id)
    
    # Группируем услуги
    grouped = {}
    for service in services:
        name = service['service_name']
        if name not in grouped:
            grouped[name] = {'quantity': 0, 'price': service['price']}
        grouped[name]['quantity'] += service['quantity']
    
    # Формируем текст
    services_text = ""
    for name, data in grouped.items():
        total = data['price'] * data['quantity']
        services_text += f"• {name} ({data['price']}₽) ×{data['quantity']} = {format_money(total)}\n"
    
    if not services_text:
        services_text = "Нет услуг\n"
    
    message = (
        f"🚗 Машина: <b>{car['car_number']}</b>\n"
        f"💰 Итог: <b>{format_money(car['total_amount'])}</b>\n\n"
        f"<b>Услуги:</b>\n{services_text}\n"
        f"<i>Выберите действие:</i>"
    )
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=create_car_edit_keyboard(car_id, shift_id, page)
    )

async def confirm_end_shift(query, shift_id: int):
    """Подтверждение закрытия смены"""
    shift = DatabaseManager.get_shift(shift_id)
    if not shift:
        await query.edit_message_text("❌ Смена не найдена")
        return
    
    cars = DatabaseManager.get_shift_cars(shift_id)
    total = DatabaseManager.get_shift_total(shift_id)
    
    message = f"🔚 <b>Закрытие смены</b>\n\n"
    message += f"Начало: {shift['start_time'].strftime('%H:%M (%d.%m.%Y)')}\n"
    message += f"Длительность: {int((datetime.now() - shift['start_time']).total_seconds() / 3600)} ч.\n"
    message += f"💰 Итог: <b>{format_money(total)}</b>\n"
    message += f"🚗 Машин: <b>{len(cars)}</b>\n\n"
    message += "<i>Вы уверены, что хотите закрыть смену?</i>"
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=create_confirmation_keyboard("end_shift", shift_id)
    )

async def generate_shift_reports(query, shift):
    """Генерация отчётов по смене"""
    shift_id = shift['id']
    cars = DatabaseManager.get_shift_cars(shift_id)
    total = DatabaseManager.get_shift_total(shift_id)
    
    # Собираем все услуги за смену
    all_services = []
    for car in cars:
        car_services = DatabaseManager.get_car_services(car['id'])
        all_services.extend(car_services)
    
    # Анализируем услуги
    service_stats = {}
    repeated_services = []
    
    for service in all_services:
        name = service['service_name']
        if name not in service_stats:
            service_stats[name] = {'count': 0, 'total': 0}
        
        service_stats[name]['count'] += service['quantity']
        service_stats[name]['total'] += service['price'] * service['quantity']
        
        # Находим повторяющиеся услуги (количество > 1)
        if service['quantity'] > 1:
            # Находим номер машины
            car = DatabaseManager.get_car(service['car_id'])
            if car:
                repeated_services.append({
                    'car_number': car['car_number'],
                    'service_name': name,
                    'quantity': service['quantity']
                })
    
    # Отчёт 1: Денежный
    report1 = f"📊 <b>ОТЧЁТ ЗА СМЕНУ</b>\n\n"
    report1 += f"• Начало: {shift['start_time'].strftime('%H:%M')}\n"
    report1 += f"• Окончание: {shift['end_time'].strftime('%H:%M')}\n"
    report1 += f"• Длительность: {int((shift['end_time'] - shift['start_time']).total_seconds() / 3600)} ч.\n"
    report1 += f"• Машин обслужено: {len(cars)}\n"
    report1 += f"• Заработано: <b>{format_money(total)}</b>\n"
    
    avg_per_car = int(total / len(cars)) if cars else 0
    report1 += f"• Средний чек: <b>{format_money(avg_per_car)}</b>\n\n"
    
    # Топ-3 услуги по выручке
    if service_stats:
        top_services = sorted(service_stats.items(), 
                            key=lambda x: x[1]['total'], 
                            reverse=True)[:3]
        
        report1 += "<b>ТОП-3 услуги по выручке:</b>\n"
        for i, (name, stats) in enumerate(top_services, 1):
            report1 += f"{i}. {name} — {format_money(stats['total'])} ({stats['count']} раз)\n"
    
    # Отчёт 2: Повторы
    report2 = "\n🔄 <b>ОТЧЁТ ПОВТОРОВ</b>\n"
    if repeated_services:
        report2 += "Машины с повторяющимися услугами:\n"
        for item in repeated_services:
            report2 += f"• {item['car_number']} — {item['service_name']} ×{item['quantity']}\n"
    else:
        report2 += "Повторяющихся услуг нет\n"
    
    full_report = report1 + report2 + "\n✅ Смена успешно закрыта!"
    
    await query.edit_message_text(
        full_report,
        parse_mode='HTML',
        reply_markup=create_main_keyboard()
    )

async def show_stats(query, user):
    """Показать статистику"""
    stats = DatabaseManager.get_user_stats(user['id'], days=30)
    
    message = f"📈 <b>Ваша статистика</b>\n\n"
    message += f"<b>За последние 30 дней:</b>\n"
    message += f"• Смен: {stats['shift_count']}\n"
    message += f"• Машин: {stats.get('cars_count', 0)}\n"
    message += f"• Заработано: <b>{format_money(stats['total_earned'])}</b>\n"
    
    if stats['shift_count'] > 0:
        message += f"• Среднее за смену: <b>{format_money(int(stats['avg_per_shift']))}</b>\n"
    
    # Активная смена
    active_shift = DatabaseManager.get_active_shift(user['id'])
    if active_shift:
        message += f"\n<b>Активная смена:</b>\n"
        message += f"• Начата: {active_shift['start_time'].strftime('%H:%M')}\n"
        message += f"• Заработано: {format_money(active_shift.get('total_amount', 0))}\n"
        message += f"• Машин: {len(DatabaseManager.get_shift_cars(active_shift['id']))}\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика по декаде", callback_data="setting_decade_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_back")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_decade_stats(query, user):
    """Показать статистику по декаде"""
    decade, (start_day, end_day) = get_current_decade()
    stats = get_decade_stats(user['id'], decade)
    
    message = f"📈 <b>Декада {decade} ({start_day}-{end_day})</b>\n\n"
    
    message += f"📅 Дней прошло: {stats['days_passed']}/{stats['total_days']}\n"
    message += f"📊 Смен отработано: <b>{stats['shift_count']}</b>\n"
    message += f"💰 Заработано: <b>{format_money(stats['total_earned'])}</b>\n"
    message += f"🚗 Машин обслужено: <b>{stats['cars_count']}</b>\n"
    
    if stats['shift_count'] > 0:
        avg_per_shift = stats['total_earned'] / stats['shift_count']
        avg_per_car = stats['total_earned'] / stats['cars_count'] if stats['cars_count'] > 0 else 0
        
        message += f"📈 Среднее за смену: <b>{format_money(int(avg_per_shift))}</b>\n"
        message += f"📊 Средний чек: <b>{format_money(int(avg_per_car))}</b>\n"
        
        # Прогноз на декаду
        if stats['days_passed'] > 0:
            daily_avg = stats['total_earned'] / stats['days_passed']
            forecast = int(daily_avg * stats['total_days'])
            days_left = stats['total_days'] - stats['days_passed']
            
            message += f"🎯 Прогноз на декаду: <b>{format_money(forecast)}</b>\n"
            message += f"⏱️ Осталось дней: <b>{days_left}</b>\n"
    
    message += "\nВыберите действие:"
    
    keyboard = [
        [InlineKeyboardButton("📊 Общая статистика", callback_data="main_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_back")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_settings(query, user):
    """Показать настройки"""
    await query.edit_message_text(
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите параметр для изменения:",
        parse_mode='HTML',
        reply_markup=create_settings_keyboard(user)
    )

async def show_help(query):
    """Показать помощь"""
    help_text = """
❓ <b>Помощь по использованию бота</b>

<b>Основные функции:</b>
1. <b>🚗 Добавить машину</b> - начать смену и добавить машину
2. <b>📊 Текущая смена</b> - посмотреть прогресс активной смены
3. <b>📜 История смен</b> - просмотреть и редактировать прошлые смены
4. <b>📈 Статистика</b> - посмотреть статистику работы
5. <b>⚙️ Настройки</b> - изменить настройки бота

<b>Как работать:</b>
1. Нажмите "🚗 Добавить машину"
2. Введите номер машины
3. Выберите услуги (можно несколько раз для увеличения количества)
4. Нажмите "💾 Сохранить машину"

<b>Особенности:</b>
• Номера автоматически приводятся к русской раскладке
• Регион 797 добавляется автоматически если не указан
• Цены зависят от времени (день/ночь)
• При закрытии смены генерируются два отчёта

<b>Редактирование:</b>
• В "Истории смен" можно просматривать прошлые смены
• В смене можно добавлять/удалять машины
• В машине можно редактировать услуги

<b>Декады:</b>
• Статистика автоматически группируется по декадам:
  - 1-я: 1-10 число
  - 2-я: 11-20 число
  - 3-я: 21-конец месяца

<b>Команды:</b>
/start - перезапустить бота
/help - показать эту справку
    """
    
    await query.edit_message_text(
        help_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="main_back")]
        ])
    )

async def help_command(update: Update, context: CallbackContext):
    """Обработчик команды /help"""
    await show_help(update.callback_query if update.callback_query else None)

async def error_handler(update: Update, context: CallbackContext):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Попробуйте ещё раз или перезапустите бота /start"
        )

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Обработчик callback-кнопок
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("🤖 Бот запущен...")
    print("=" * 60)
    print("🚀 Бот успешно запущен!")
    print(f"✅ Режим базы данных: {'PostgreSQL' if hasattr(DatabaseManager, '__module__') and DatabaseManager.__module__ == '__main__' else 'Память'}")
    print("=" * 60)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
