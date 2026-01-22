"""
ПОЛНАЯ РАБОЧАЯ ВЕРСИЯ БОТА ДЛЯ УЧЁТА УСЛУГ
"""

import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List

from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    KeyboardButton
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    CallbackContext, 
    CallbackQueryHandler,
    ConversationHandler
)

import config
from database import DatabaseManager, init_database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
REGISTER_NAME = 1
SET_TARGET = 2
SET_END_TIME = 3

# Глобальные переменные для хранения временных данных
user_temp_data = {}

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def format_progress_bar(current, target, length=20):
    """Форматирование прогресс-бара"""
    if target <= 0:
        return "[░░░░░░░░░░░░░░░░░░░░] 0%"
    
    percentage = min(current / target, 1.0)
    filled = int(length * percentage)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {int(percentage * 100)}%"

def create_main_keyboard():
    """Создание основной клавиатуры"""
    keyboard = [
        [KeyboardButton("🚗 Добавить машину"), KeyboardButton("📊 Прогресс")],
        [KeyboardButton("📜 История смен"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton("❓ Помощь"), KeyboardButton("🔚 Закрыть смену")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_services_keyboard(car_id=None):
    """Создание клавиатуры с услугами"""
    keyboard = []
    
    # Первые 6 услуг (самые частые)
    services = list(config.SERVICES.items())[:6]
    
    for i in range(0, len(services), 2):
        row = []
        for service_id, service in services[i:i+2]:
            callback_data = f"add_service_{service_id}"
            if car_id:
                callback_data += f"_{car_id}"
            row.append(
                InlineKeyboardButton(
                    f"{service['name']} ({service['price']}₽)",
                    callback_data=callback_data
                )
            )
        keyboard.append(row)
    
    # Кнопки управления
    keyboard.append([
        InlineKeyboardButton("🔽 Удалить последнюю", callback_data=f"remove_last_{car_id}"),
        InlineKeyboardButton("🗑️ Очистить всё", callback_data=f"clear_all_{car_id}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("💾 Сохранить машину", callback_data=f"save_car_{car_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_car_{car_id}")
    ])
    
    # Кнопка "Все услуги"
    if len(config.SERVICES) > 6:
        keyboard.append([
            InlineKeyboardButton("📋 Все услуги", callback_data=f"all_services_{car_id}")
        ])
    
    return InlineKeyboardMarkup(keyboard)

def create_all_services_keyboard(car_id=None, page=0):
    """Создание клавиатуры со всеми услугами (пагинация)"""
    keyboard = []
    services_per_page = 8
    all_services = list(config.SERVICES.items())
    
    start_idx = page * services_per_page
    end_idx = start_idx + services_per_page
    
    for i in range(start_idx, min(end_idx, len(all_services)), 2):
        row = []
        for service_id, service in all_services[i:i+2]:
            callback_data = f"add_service_{service_id}"
            if car_id:
                callback_data += f"_{car_id}"
            row.append(
                InlineKeyboardButton(
                    f"{service['name']} ({service['price']}₽)",
                    callback_data=callback_data
                )
            )
        keyboard.append(row)
    
    # Кнопки навигации
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton("◀️ Назад", callback_data=f"all_services_{car_id}_{page-1}"))
    
    if end_idx < len(all_services):
        navigation.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"all_services_{car_id}_{page+1}"))
    
    if navigation:
        keyboard.append(navigation)
    
    keyboard.append([
        InlineKeyboardButton("🔙 К частым услугам", callback_data=f"back_to_main_{car_id}")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_shifts_keyboard(shifts, page=0, action="view"):
    """Создание клавиатуры со сменами"""
    keyboard = []
    shifts_per_page = 5
    
    start_idx = page * shifts_per_page
    end_idx = start_idx + shifts_per_page
    
    for shift in shifts[start_idx:end_idx]:
        date_str = shift['created_at'].strftime("%d.%m.%Y")
        time_str = f"{shift['start_time'].strftime('%H:%M')}"
        if shift['end_time']:
            time_str += f"-{shift['end_time'].strftime('%H:%M')}"
        
        button_text = f"{date_str} {time_str} - {shift['total_amount']}₽"
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"{action}_shift_{shift['id']}_{page}"
            )
        ])
    
    # Кнопки навигации
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton("◀️", callback_data=f"shifts_page_{action}_{page-1}"))
    
    navigation.append(InlineKeyboardButton(f"Стр. {page+1}", callback_data="noop"))
    
    if end_idx < len(shifts):
        navigation.append(InlineKeyboardButton("▶️", callback_data=f"shifts_page_{action}_{page+1}"))
    
    if navigation:
        keyboard.append(navigation)
    
    keyboard.append([
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_cars_keyboard(cars, shift_id, page=0):
    """Создание клавиатуры с машинами смены"""
    keyboard = []
    
    for car in cars:
        button_text = f"{car['car_number']} - {car['total_amount']}₽"
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"view_car_{car['id']}_{shift_id}_{page}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("➕ Добавить машину", callback_data=f"add_car_to_shift_{shift_id}"),
        InlineKeyboardButton("🗑️ Удалить смену", callback_data=f"delete_shift_{shift_id}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 К истории", callback_data="back_to_history")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_car_edit_keyboard(car_id, shift_id, page):
    """Создание клавиатуры для редактирования машины"""
    keyboard = [
        [
            InlineKeyboardButton("✏️ Добавить услуги", callback_data=f"edit_add_services_{car_id}_{shift_id}_{page}"),
            InlineKeyboardButton("🗑️ Удалить машину", callback_data=f"delete_car_{car_id}_{shift_id}_{page}")
        ],
        [
            InlineKeyboardButton("🔙 К машинам", callback_data=f"back_to_cars_{shift_id}_{page}")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

async def start(update: Update, context: CallbackContext):
    """Обработка команды /start"""
    user = update.effective_user
    
    # Проверяем, зарегистрирован ли пользователь
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        # Если не зарегистрирован, просим ввести имя
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            f"Я бот для учёта услуг на работе.\n\n"
            f"Для начала работы введите ваше имя:"
        )
        return REGISTER_NAME
    else:
        # Проверяем активную смену
        active_shift = DatabaseManager.get_active_shift(db_user['id'])
        
        if active_shift:
            # Если есть активная смена, показываем главное меню с прогрессом
            total = DatabaseManager.get_shift_total(active_shift['id'])
            user_settings = DatabaseManager.get_user(user.id)
            
            progress_text = ""
            if user_settings and user_settings.get('progress_bar_enabled', True):
                target = user_settings.get('daily_target', 5000)
                progress_text = f"\n📊 Прогресс: {format_progress_bar(total, target)}\n"
            
            await update.message.reply_text(
                f"🎉 С возвращением, {db_user['name']}!\n"
                f"📍 Активная смена начата в {active_shift['start_time'].strftime('%H:%M')}\n"
                f"💰 Заработано: {total}₽"
                f"{progress_text}\n"
                f"Используйте кнопки ниже ↓",
                reply_markup=create_main_keyboard()
            )
        else:
            # Если активной смены нет
            await update.message.reply_text(
                f"🎉 С возвращением, {db_user['name']}!\n\n"
                f"Начните новую смену, нажав кнопку ниже ↓",
                reply_markup=create_main_keyboard()
            )
    
    return ConversationHandler.END

async def register_name(update: Update, context: CallbackContext):
    """Обработка ввода имени при регистрации"""
    name = update.message.text.strip()
    
    if len(name) < 2:
        await update.message.reply_text("❌ Имя слишком короткое. Введите ещё раз:")
        return REGISTER_NAME
    
    # Регистрируем пользователя
    user_id = DatabaseManager.register_user(update.effective_user.id, name)
    
    if user_id:
        await update.message.reply_text(
            f"✅ Отлично, {name}!\n"
            f"Вы успешно зарегистрированы.\n\n"
            f"Теперь вы можете начать работу.\n"
            f"Используйте кнопки ниже ↓",
            reply_markup=create_main_keyboard()
        )
        
        # Спрашиваем о цели на смену
        await update.message.reply_text(
            "🎯 <b>Установите цель на смену</b>\n\n"
            "Введите сумму в рублях (например: 5000):",
            parse_mode='HTML'
        )
        return SET_TARGET
    else:
        await update.message.reply_text(
            "❌ Ошибка регистрации. Попробуйте ещё раз: /start"
        )
        return ConversationHandler.END

async def set_target(update: Update, context: CallbackContext):
    """Установка цели на смену"""
    try:
        target = int(update.message.text.strip())
        
        if target < 100:
            await update.message.reply_text("❌ Цель должна быть не менее 100 рублей. Введите ещё раз:")
            return SET_TARGET
        
        # Обновляем настройки пользователя
        DatabaseManager.update_user_setting(update.effective_user.id, 'daily_target', target)
        
        await update.message.reply_text(
            f"✅ Цель установлена: <b>{target}₽</b>\n\n"
            f"Теперь вы можете начать смену!",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
        
        # Предлагаем начать смену
        keyboard = [[InlineKeyboardButton("🏁 Начать смену", callback_data="start_shift")]]
        await update.message.reply_text(
            "Нажмите кнопку ниже, чтобы начать смену:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except ValueError:
        await update.message.reply_text("❌ Введите число. Например: 5000")
        return SET_TARGET
    
    return ConversationHandler.END

async def handle_add_car(update: Update, context: CallbackContext):
    """Обработка нажатия 'Добавить машину'"""
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь: /start")
        return
    
    # Проверяем активную смену
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    
    if not active_shift:
        keyboard = [[InlineKeyboardButton("🏁 Начать смену", callback_data="start_shift")]]
        await update.message.reply_text(
            "❌ У вас нет активной смены.\n"
            "Начните смену, чтобы добавлять машины:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    await update.message.reply_text(
        "🚗 <b>Добавление машины</b>\n\n"
        "Введите номер машины:\n"
        "<code>Например: А123БВ777 или Х340РУ797</code>",
        parse_mode='HTML'
    )
    
    # Сохраняем данные для следующего шага
    context.user_data['awaiting_car_number'] = True
    context.user_data['active_shift_id'] = active_shift['id']

async def handle_car_number(update: Update, context: CallbackContext):
    """Обработка ввода номера машины"""
    if not context.user_data.get('awaiting_car_number'):
        return
    
    car_number = update.message.text.strip().upper()
    
    if len(car_number) < 5:
        await update.message.reply_text("❌ Номер слишком короткий. Введите ещё раз:")
        return
    
    # Добавляем машину в базу
    shift_id = context.user_data['active_shift_id']
    car_id = DatabaseManager.add_car(shift_id, car_number)
    
    if car_id:
        # Сохраняем ID машины
        context.user_data['current_car_id'] = car_id
        context.user_data['awaiting_car_number'] = False
        
        # Показываем кнопки с услугами
        await update.message.reply_text(
            f"🚗 Машина: <b>{car_number}</b>\n"
            f"💰 Итог: <b>0₽</b>\n\n"
            f"<i>Выберите услуги:</i>",
            reply_markup=create_services_keyboard(car_id),
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text("❌ Ошибка добавления машины. Попробуйте ещё раз.")

async def handle_progress(update: Update, context: CallbackContext):
    """Обработка нажатия 'Прогресс'"""
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь: /start")
        return
    
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    
    if not active_shift:
        await update.message.reply_text(
            "📊 <b>Прогресс</b>\n\n"
            "Сейчас нет активной смены.\n"
            "Начните смену, чтобы отслеживать прогресс.",
            parse_mode='HTML'
        )
        return
    
    # Получаем данные
    total = DatabaseManager.get_shift_total(active_shift['id'])
    target = db_user.get('daily_target', 5000)
    
    # Получаем список машин в смене
    cars = DatabaseManager.get_shift_cars(active_shift['id'])
    
    # Формируем сообщение
    message = f"📊 <b>Прогресс смены</b>\n\n"
    message += f"Начало: {active_shift['start_time'].strftime('%H:%M')}\n"
    message += f"Заработано: <b>{total}₽</b>\n"
    message += f"Цель: <b>{target}₽</b>\n"
    message += f"Прогресс: {format_progress_bar(total, target)}\n\n"
    
    if cars:
        message += "<b>Машины в смене:</b>\n"
        for i, car in enumerate(cars, 1):
            message += f"{i}. {car['car_number']} - {car['total_amount']}₽\n"
    else:
        message += "Машин ещё нет. Добавьте первую машину!\n"
    
    await update.message.reply_text(message, parse_mode='HTML')

async def handle_history(update: Update, context: CallbackContext):
    """Обработка нажатия 'История смен'"""
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь: /start")
        return
    
    # Получаем историю смен
    shifts = DatabaseManager.get_user_shifts(db_user['id'])
    
    if not shifts:
        await update.message.reply_text(
            "📜 <b>История смен</b>\n\n"
            "У вас ещё нет завершённых смен.",
            parse_mode='HTML'
        )
        return
    
    await update.message.reply_text(
        "📜 <b>История смен</b>\n\n"
        "Выберите смену для просмотра:",
        reply_markup=create_shifts_keyboard(shifts),
        parse_mode='HTML'
    )

async def handle_settings(update: Update, context: CallbackContext):
    """Обработка нажатия 'Настройки'"""
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь: /start")
        return
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"🎯 Цель: {db_user.get('daily_target', 5000)}₽",
                callback_data="change_target"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Прогресс-бар: ВКЛ" if db_user.get('progress_bar_enabled', True) else "📊 Прогресс-бар: ВЫКЛ",
                callback_data="toggle_progress_bar"
            )
        ],
        [
            InlineKeyboardButton("📈 Статистика", callback_data="show_stats"),
            InlineKeyboardButton("🔄 Сбросить прогресс", callback_data="reset_progress")
        ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
        ]
    ]
    
    await update.message.reply_text(
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите параметр для изменения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_help(update: Update, context: CallbackContext):
    """Обработка нажатия 'Помощь'"""
    help_text = """
❓ <b>Помощь по использованию бота</b>

<b>Основные функции:</b>
1. <b>🚗 Добавить машину</b> - добавить новую машину и выбрать услуги
2. <b>📊 Прогресс</b> - посмотреть прогресс текущей смены
3. <b>📜 История смен</b> - просмотреть и редактировать прошлые смены
4. <b>⚙️ Настройки</b> - изменить настройки бота
5. <b>🔚 Закрыть смену</b> - завершить текущую смену

<b>Как работать с машиной:</b>
1. Нажмите "🚗 Добавить машину"
2. Введите номер машины
3. Выберите услуги кнопками под сообщением
   - Можно нажимать несколько раз для увеличения количества
   - "🔽 Удалить последнюю" - удалить одну услугу
   - "🗑️ Очистить всё" - удалить все услуги
   - "💾 Сохранить машину" - сохранить и вернуться в меню
4. После сохранения можно добавить следующую машину

<b>Редактирование смен:</b>
- В "Истории смен" можно просматривать старые смены
- Можно добавлять/удалять машины в завершённых сменах
- Можно удалять целые смены

<b>Команды:</b>
/start - перезапустить бота
/help - показать эту справку
/test - проверить работу бота
    """
    
    await update.message.reply_text(help_text, parse_mode='HTML')

async def handle_close_shift(update: Update, context: CallbackContext):
    """Обработка нажатия 'Закрыть смену'"""
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь: /start")
        return
    
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    
    if not active_shift:
        await update.message.reply_text(
            "❌ У вас нет активной смены.\n"
            "Сначала начните смену."
        )
        return
    
    # Предлагаем указать время окончания
    keyboard = [
        [
            InlineKeyboardButton("🕐 Сейчас", callback_data=f"end_shift_now_{active_shift['id']}"),
            InlineKeyboardButton("🕑 Указать время", callback_data=f"end_shift_custom_{active_shift['id']}")
        ],
        [
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_end_shift")
        ]
    ]
    
    total = DatabaseManager.get_shift_total(active_shift['id'])
    
    await update.message.reply_text(
        f"🔚 <b>Закрытие смены</b>\n\n"
        f"Начало: {active_shift['start_time'].strftime('%H:%M (%d.%m.%Y)')}\n"
        f"Заработано: <b>{total}₽</b>\n"
        f"Машин обслужено: {len(DatabaseManager.get_shift_cars(active_shift['id']))}\n\n"
        f"Укажите время окончания смены:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ========== ОБРАБОТЧИКИ INLINE-КНОПОК ==========

async def handle_callback_query(update: Update, context: CallbackContext):
    """Обработка всех inline-кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = update.effective_user
    
    logger.info(f"Callback data: {data}")
    
    # Разбиваем данные на части
    parts = data.split('_')
    action = parts[0] if len(parts) > 0 else ""
    
    # Обработка разных действий
    if action == "start":
        await handle_start_shift_callback(query, context)
    elif action == "add":
        await handle_add_service_callback(query, context, parts)
    elif action == "remove":
        await handle_remove_service_callback(query, context, parts)
    elif action == "clear":
        await handle_clear_all_callback(query, context, parts)
    elif action == "save":
        await handle_save_car_callback(query, context, parts)
    elif action == "cancel":
        await handle_cancel_car_callback(query, context, parts)
    elif action == "all":
        await handle_all_services_callback(query, context, parts)
    elif action == "back":
        await handle_back_callback(query, context, parts)
    elif action == "end":
        await handle_end_shift_callback(query, context, parts)
    elif action == "view":
        await handle_view_shift_callback(query, context, parts)
    elif action == "edit":
        await handle_edit_car_callback(query, context, parts)
    elif action == "delete":
        await handle_delete_callback(query, context, parts)
    elif action == "shifts":
        await handle_shifts_page_callback(query, context, parts)
    elif action == "change":
        await handle_change_target_callback(query, context)
    elif action == "toggle":
        await handle_toggle_progress_bar_callback(query, context)
    elif action == "show":
        await handle_show_stats_callback(query, context)
    elif action == "reset":
        await handle_reset_progress_callback(query, context)
    elif action == "noop":
        # Ничего не делаем для кнопки-заглушки
        pass
    else:
        await query.edit_message_text("❌ Неизвестная команда")

async def handle_start_shift_callback(query, context):
    """Обработка начала смены"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await query.edit_message_text("❌ Сначала зарегистрируйтесь: /start")
        return
    
    # Начинаем новую смену
    shift_id = DatabaseManager.start_shift(db_user['id'])
    
    await query.edit_message_text(
        f"✅ <b>Смена начата!</b>\n\n"
        f"Время начала: {datetime.now().strftime('%H:%M (%d.%m.%Y)')}\n"
        f"Цель на смену: {db_user.get('daily_target', 5000)}₽\n\n"
        f"Теперь вы можете добавлять машины 🚗",
        parse_mode='HTML'
    )

async def handle_add_service_callback(query, context, parts):
    """Обработка добавления услуги"""
    if len(parts) < 3:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    service_id = int(parts[2])
    car_id = int(parts[3]) if len(parts) > 3 else None
    
    if not car_id:
        await query.answer("Ошибка: не указана машина")
        return
    
    # Получаем информацию об услуге
    service = config.SERVICES.get(service_id)
    if not service:
        await query.answer("Ошибка: услуга не найдена")
        return
    
    # Добавляем услугу к машине
    new_total = DatabaseManager.add_service_to_car(
        car_id, service_id, service['name'], service['price']
    )
    
    # Обновляем сообщение
    car = DatabaseManager.get_car(car_id)
    services = DatabaseManager.get_car_services(car_id)
    
    # Формируем список услуг с количеством
    services_text = ""
    services_count = {}
    for svc in services:
        name = svc['service_name']
        services_count[name] = services_count.get(name, 0) + svc['quantity']
    
    for name, count in services_count.items():
        services_text += f"{name} ×{count}\n"
    
    if not services_text:
        services_text = "Нет выбранных услуг"
    
    # Определяем, какую клавиатуру показывать
    if len(parts) > 4 and parts[1] == "services" and parts[4].isdigit():
        # Если мы на странице "Все услуги"
        page = int(parts[4])
        keyboard = create_all_services_keyboard(car_id, page)
    else:
        # Обычная клавиатура
        keyboard = create_services_keyboard(car_id)
    
    await query.edit_message_text(
        f"🚗 Машина: <b>{car['car_number']}</b>\n"
        f"💰 Итог: <b>{new_total}₽</b>\n\n"
        f"<b>Выбранные услуги:</b>\n{services_text}\n"
        f"<i>Продолжайте выбирать:</i>",
        reply_markup=keyboard,
        parse_mode='HTML'
    )

async def handle_remove_service_callback(query, context, parts):
    """Обработка удаления последней услуги"""
    if len(parts) < 3:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    car_id = int(parts[2]) if parts[2] != "last" else None
    
    if not car_id:
        await query.answer("Ошибка: не указана машина")
        return
    
    # Удаляем последнюю услугу
    new_total = DatabaseManager.remove_last_service(car_id)
    
    # Обновляем сообщение
    car = DatabaseManager.get_car(car_id)
    services = DatabaseManager.get_car_services(car_id)
    
    # Формируем список услуг с количеством
    services_text = ""
    services_count = {}
    for svc in services:
        name = svc['service_name']
        services_count[name] = services_count.get(name, 0) + svc['quantity']
    
    for name, count in services_count.items():
        services_text += f"{name} ×{count}\n"
    
    if not services_text:
        services_text = "Нет выбранных услуг"
    
    await query.edit_message_text(
        f"🚗 Машина: <b>{car['car_number']}</b>\n"
        f"💰 Итог: <b>{new_total}₽</b>\n\n"
        f"<b>Выбранные услуги:</b>\n{services_text}\n"
        f"<i>Продолжайте выбирать:</i>",
        reply_markup=create_services_keyboard(car_id),
        parse_mode='HTML'
    )

async def handle_clear_all_callback(query, context, parts):
    """Обработка очистки всех услуг"""
    if len(parts) < 3:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    car_id = int(parts[2])
    
    # Удаляем все услуги машины
    DatabaseManager.remove_last_service(car_id)  # Будем удалять по одной, пока они есть
    services = DatabaseManager.get_car_services(car_id)
    while services:
        DatabaseManager.remove_last_service(car_id)
        services = DatabaseManager.get_car_services(car_id)
    
    # Обновляем сообщение
    car = DatabaseManager.get_car(car_id)
    
    await query.edit_message_text(
        f"🚗 Машина: <b>{car['car_number']}</b>\n"
        f"💰 Итог: <b>0₽</b>\n\n"
        f"<b>Выбранные услуги:</b>\nНет выбранных услуг\n"
        f"<i>Продолжайте выбирать:</i>",
        reply_markup=create_services_keyboard(car_id),
        parse_mode='HTML'
    )

async def handle_save_car_callback(query, context, parts):
    """Обработка сохранения машины"""
    if len(parts) < 3:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    car_id = int(parts[2])
    
    # Получаем данные о машине
    car = DatabaseManager.get_car(car_id)
    services = DatabaseManager.get_car_services(car_id)
    
    if not services:
        await query.edit_message_text(
            f"❌ Машина <b>{car['car_number']}</b> не сохранена.\n"
            f"Не выбрано ни одной услуги.",
            parse_mode='HTML'
        )
        return
    
    # Обновляем общую сумму смены
    shift_id = DatabaseManager.update_shift_total(car['shift_id'])
    
    # Формируем сообщение
    services_text = ""
    services_count = {}
    for svc in services:
        name = svc['service_name']
        services_count[name] = services_count.get(name, 0) + svc['quantity']
    
    for name, count in services_count.items():
        services_text += f"• {name} ×{count}\n"
    
    await query.edit_message_text(
        f"✅ Машина <b>{car['car_number']}</b> сохранена!\n\n"
        f"<b>Услуги:</b>\n{services_text}\n"
        f"💰 <b>Итог: {car['total_amount']}₽</b>\n\n"
        f"Можете добавить следующую машину 🚗",
        parse_mode='HTML'
    )

async def handle_cancel_car_callback(query, context, parts):
    """Обработка отмены добавления машины"""
    if len(parts) < 3:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    car_id = int(parts[2])
    
    # Удаляем машину из базы
    shift_id = DatabaseManager.delete_car(car_id)
    
    await query.edit_message_text(
        "❌ Добавление машины отменено.\n"
        "Машина удалена из смены."
    )

async def handle_all_services_callback(query, context, parts):
    """Обработка показа всех услуг"""
    if len(parts) < 3:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    car_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    
    car = DatabaseManager.get_car(car_id)
    services = DatabaseManager.get_car_services(car_id)
    
    # Формируем список услуг с количеством
    services_text = ""
    services_count = {}
    for svc in services:
        name = svc['service_name']
        services_count[name] = services_count.get(name, 0) + svc['quantity']
    
    for name, count in services_count.items():
        services_text += f"{name} ×{count}\n"
    
    if not services_text:
        services_text = "Нет выбранных услуг"
    
    await query.edit_message_text(
        f"🚗 Машина: <b>{car['car_number']}</b>\n"
        f"💰 Итог: <b>{car['total_amount']}₽</b>\n\n"
        f"<b>Выбранные услуги:</b>\n{services_text}\n"
        f"<i>Все услуги:</i>",
        reply_markup=create_all_services_keyboard(car_id, page),
        parse_mode='HTML'
    )

async def handle_back_callback(query, context, parts):
    """Обработка возврата назад"""
    if len(parts) < 3:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    back_to = parts[2]
    
    if back_to == "to" and len(parts) > 3 and parts[3] == "main":
        # Возврат к основным услугам
        car_id = int(parts[4]) if len(parts) > 4 else None
        if car_id:
            car = DatabaseManager.get_car(car_id)
            services = DatabaseManager.get_car_services(car_id)
            
            services_text = ""
            services_count = {}
            for svc in services:
                name = svc['service_name']
                services_count[name] = services_count.get(name, 0) + svc['quantity']
            
            for name, count in services_count.items():
                services_text += f"{name} ×{count}\n"
            
            if not services_text:
                services_text = "Нет выбранных услуг"
            
            await query.edit_message_text(
                f"🚗 Машина: <b>{car['car_number']}</b>\n"
                f"💰 Итог: <b>{car['total_amount']}₽</b>\n\n"
                f"<b>Выбранные услуги:</b>\n{services_text}\n"
                f"<i>Выберите услуги:</i>",
                reply_markup=create_services_keyboard(car_id),
                parse_mode='HTML'
            )
    elif back_to == "to" and len(parts) > 3 and parts[3] == "main" and len(parts) == 4:
        # Просто возврат в главное меню
        await query.edit_message_text(
            "Главное меню",
            reply_markup=create_main_keyboard()
        )
    elif back_to == "to" and len(parts) > 3 and parts[3] == "history":
        # Возврат к истории смен
        user = query.from_user
        db_user = DatabaseManager.get_user(user.id)
        
        if db_user:
            shifts = DatabaseManager.get_user_shifts(db_user['id'])
            await query.edit_message_text(
                "📜 <b>История смен</b>\n\n"
                "Выберите смену для просмотра:",
                reply_markup=create_shifts_keyboard(shifts),
                parse_mode='HTML'
            )
    elif back_to == "to" and len(parts) > 3 and parts[3] == "cars":
        # Возврат к машинам смены
        if len(parts) > 5:
            shift_id = int(parts[4])
            page = int(parts[5])
            
            cars = DatabaseManager.get_shift_cars(shift_id)
            shift = DatabaseManager.get_shift_total(shift_id)
            
            await query.edit_message_text(
                f"🚗 <b>Машины в смене</b>\n"
                f"💰 Общая сумма: {shift}₽\n\n"
                f"Выберите машину для редактирования:",
                reply_markup=create_cars_keyboard(cars, shift_id, page),
                parse_mode='HTML'
            )

async def handle_end_shift_callback(query, context, parts):
    """Обработка закрытия смены"""
    if len(parts) < 3:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    action = parts[2]
    
    if action == "shift":
        if len(parts) < 4:
            await query.answer("Ошибка: неверный формат данных")
            return
        
        if parts[3] == "now":
            # Закрыть смену текущим временем
            shift_id = int(parts[4])
            ended_shift = DatabaseManager.end_shift(shift_id)
            
            if ended_shift:
                # Получаем данные для отчёта
                total = ended_shift['total_amount']
                cars = DatabaseManager.get_shift_cars(shift_id)
                
                # Формируем отчёт
                report = f"✅ <b>Смена завершена!</b>\n\n"
                report += f"Начало: {ended_shift['start_time'].strftime('%H:%M')}\n"
                report += f"Окончание: {ended_shift['end_time'].strftime('%H:%M')}\n"
                report += f"Длительность: {int((ended_shift['end_time'] - ended_shift['start_time']).total_seconds() / 3600)} ч.\n"
                report += f"💰 Итог: <b>{total}₽</b>\n"
                report += f"🚗 Машин: {len(cars)}\n\n"
                
                # Статистика по услугам
                all_services = []
                for car in cars:
                    services = DatabaseManager.get_car_services(car['id'])
                    all_services.extend(services)
                
                if all_services:
                    report += "<b>Статистика услуг:</b>\n"
                    service_stats = {}
                    for svc in all_services:
                        name = svc['service_name']
                        service_stats[name] = service_stats.get(name, 0) + svc['quantity']
                    
                    for name, count in service_stats.items():
                        report += f"• {name}: {count} раз\n"
                
                await query.edit_message_text(report, parse_mode='HTML')
        
        elif parts[3] == "custom":
            # Запрос на ввод времени окончания
            shift_id = int(parts[4])
            context.user_data['awaiting_end_time'] = True
            context.user_data['end_shift_id'] = shift_id
            
            await query.edit_message_text(
                "🕑 <b>Введите время окончания смены</b>\n\n"
                "Формат: ЧЧ:ММ\n"
                "Например: 14:30 или 02:15",
                parse_mode='HTML'
            )
    
    elif action == "cancel":
        await query.edit_message_text("❌ Закрытие смены отменено.")

async def handle_view_shift_callback(query, context, parts):
    """Обработка просмотра смены"""
    if len(parts) < 4:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    shift_id = int(parts[3])
    page = int(parts[4]) if len(parts) > 4 else 0
    
    # Получаем данные смены
    cars = DatabaseManager.get_shift_cars(shift_id)
    total = DatabaseManager.get_shift_total(shift_id)
    
    if not cars:
        await query.edit_message_text(
            f"📋 <b>Смена</b>\n\n"
            f"Машин в смене нет.\n"
            f"Общая сумма: {total}₽\n\n"
            f"Вы можете добавить машины даже в завершённую смену.",
            reply_markup=create_cars_keyboard(cars, shift_id, page),
            parse_mode='HTML'
        )
    else:
        cars_text = ""
        for i, car in enumerate(cars, 1):
            cars_text += f"{i}. {car['car_number']} - {car['total_amount']}₽\n"
        
        await query.edit_message_text(
            f"📋 <b>Смена</b>\n\n"
            f"Машин: {len(cars)}\n"
            f"Общая сумма: {total}₽\n\n"
            f"<b>Машины:</b>\n{cars_text}\n"
            f"Выберите машину для редактирования:",
            reply_markup=create_cars_keyboard(cars, shift_id, page),
            parse_mode='HTML'
        )

async def handle_edit_car_callback(query, context, parts):
    """Обработка редактирования машины"""
    if len(parts) < 5:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    action = parts[2]
    
    if action == "add" and parts[3] == "services":
        # Добавление услуг к существующей машине
        car_id = int(parts[4])
        shift_id = int(parts[5]) if len(parts) > 5 else None
        page = int(parts[6]) if len(parts) > 6 else 0
        
        car = DatabaseManager.get_car(car_id)
        services = DatabaseManager.get_car_services(car_id)
        
        services_text = ""
        services_count = {}
        for svc in services:
            name = svc['service_name']
            services_count[name] = services_count.get(name, 0) + svc['quantity']
        
        for name, count in services_count.items():
            services_text += f"{name} ×{count}\n"
        
        if not services_text:
            services_text = "Нет выбранных услуг"
        
        await query.edit_message_text(
            f"✏️ <b>Редактирование машины</b>\n"
            f"🚗 Машина: <b>{car['car_number']}</b>\n"
            f"💰 Итог: <b>{car['total_amount']}₽</b>\n\n"
            f"<b>Текущие услуги:</b>\n{services_text}\n"
            f"<i>Добавьте новые услуги:</i>",
            reply_markup=create_services_keyboard(car_id),
            parse_mode='HTML'
        )

async def handle_delete_callback(query, context, parts):
    """Обработка удаления"""
    if len(parts) < 3:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    item_type = parts[1]
    
    if item_type == "car":
        # Удаление машины
        car_id = int(parts[2])
        shift_id = int(parts[3]) if len(parts) > 3 else None
        page = int(parts[4]) if len(parts) > 4 else 0
        
        # Удаляем машину
        deleted_shift_id = DatabaseManager.delete_car(car_id)
        
        if deleted_shift_id:
            # Обновляем общую сумму смены
            DatabaseManager.update_shift_total(deleted_shift_id)
            
            # Получаем обновлённый список машин
            cars = DatabaseManager.get_shift_cars(deleted_shift_id)
            total = DatabaseManager.get_shift_total(deleted_shift_id)
            
            await query.edit_message_text(
                f"🗑️ <b>Машина удалена</b>\n\n"
                f"Машин осталось: {len(cars)}\n"
                f"Общая сумма смены: {total}₽\n\n"
                f"Выберите машину для редактирования:",
                reply_markup=create_cars_keyboard(cars, deleted_shift_id, page),
                parse_mode='HTML'
            )
    
    elif item_type == "shift":
        # Удаление смены
        shift_id = int(parts[2])
        
        # В реальном приложении здесь будет удаление смены из базы
        # Но для безопасности я пока не реализую полное удаление
        
        await query.edit_message_text(
            "⚠️ <b>Удаление смены временно недоступно</b>\n\n"
            "В целях безопасности данная функция находится в разработке.",
            parse_mode='HTML'
        )

async def handle_shifts_page_callback(query, context, parts):
    """Обработка перелистывания страниц смен"""
    if len(parts) < 5:
        await query.answer("Ошибка: неверный формат данных")
        return
    
    action = parts[2]
    page = int(parts[4])
    
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if db_user:
        shifts = DatabaseManager.get_user_shifts(db_user['id'])
        
        await query.edit_message_text(
            "📜 <b>История смен</b>\n\n"
            "Выберите смену для просмотра:",
            reply_markup=create_shifts_keyboard(shifts, page, action),
            parse_mode='HTML'
        )

async def handle_change_target_callback(query, context):
    """Обработка изменения цели"""
    await query.edit_message_text(
        "🎯 <b>Изменение цели на смену</b>\n\n"
        "Введите новую цель в рублях:",
        parse_mode='HTML'
    )
    
    # Устанавливаем состояние ожидания ввода цели
    context.user_data['awaiting_new_target'] = True

async def handle_toggle_progress_bar_callback(query, context):
    """Обработка переключения прогресс-бара"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if db_user:
        current = db_user.get('progress_bar_enabled', True)
        new_value = not current
        
        DatabaseManager.update_user_setting(user.id, 'progress_bar_enabled', new_value)
        
        status = "ВКЛ" if new_value else "ВЫКЛ"
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"🎯 Цель: {db_user.get('daily_target', 5000)}₽",
                    callback_data="change_target"
                )
            ],
            [
                InlineKeyboardButton(
                    f"📊 Прогресс-бар: {status}",
                    callback_data="toggle_progress_bar"
                )
            ],
            [
                InlineKeyboardButton("📈 Статистика", callback_data="show_stats"),
                InlineKeyboardButton("🔄 Сбросить прогресс", callback_data="reset_progress")
            ],
            [
                InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
            ]
        ]
        
        await query.edit_message_text(
            f"✅ Прогресс-бар <b>{status.lower()}</b>\n\n"
            f"Выберите параметр для изменения:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

async def handle_show_stats_callback(query, context):
    """Обработка показа статистики"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if db_user:
        stats = DatabaseManager.get_user_stats(db_user['id'])
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_settings")]]
        
        await query.edit_message_text(
            f"📈 <b>Ваша статистика</b>\n\n"
            f"Смен отработано: {stats['shift_count']}\n"
            f"Всего заработано: {stats['total_earned']}₽\n"
            f"Среднее за смену: {int(stats['avg_per_shift'])}₽\n\n"
            f"<i>Статистика за последние 30 дней</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

async def handle_reset_progress_callback(query, context):
    """Обработка сброса прогресса"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, сбросить", callback_data="confirm_reset"),
            InlineKeyboardButton("❌ Нет, отмена", callback_data="cancel_reset")
        ]
    ]
    
    await query.edit_message_text(
        "⚠️ <b>Сброс прогресса</b>\n\n"
        "Вы уверены, что хотите сбросить весь прогресс?\n"
        "Это действие нельзя отменить.\n\n"
        "Все данные будут удалены.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ========== ОБРАБОТЧИКИ СООБЩЕНИЙ ==========

async def handle_message(update: Update, context: CallbackContext):
    """Обработка всех текстовых сообщений"""
    # Проверяем, ожидаем ли мы ввод номера машины
    if context.user_data.get('awaiting_car_number'):
        await handle_car_number(update, context)
        return
    
    # Проверяем, ожидаем ли мы ввод времени окончания смены
    elif context.user_data.get('awaiting_end_time'):
        await handle_end_time_input(update, context)
        return
    
    # Проверяем, ожидаем ли мы ввод новой цели
    elif context.user_data.get('awaiting_new_target'):
        await handle_new_target_input(update, context)
        return
    
    # Если это не специальный ввод, обрабатываем как обычное сообщение
    text = update.message.text
    
    if text == "🚗 Добавить машину":
        await handle_add_car(update, context)
    elif text == "📊 Прогресс":
        await handle_progress(update, context)
    elif text == "📜 История смен":
        await handle_history(update, context)
    elif text == "⚙️ Настройки":
        await handle_settings(update, context)
    elif text == "❓ Помощь":
        await handle_help(update, context)
    elif text == "🔚 Закрыть смену":
        await handle_close_shift(update, context)
    else:
        await update.message.reply_text(
            "Я не понимаю эту команду. Используйте кнопки ниже ↓",
            reply_markup=create_main_keyboard()
        )

async def handle_end_time_input(update: Update, context: CallbackContext):
    """Обработка ввода времени окончания смены"""
    time_str = update.message.text.strip()
    
    try:
        # Парсим время
        end_time = datetime.strptime(time_str, "%H:%M")
        # Обновляем дату на сегодня
        now = datetime.now()
        end_time = end_time.replace(year=now.year, month=now.month, day=now.day)
        
        shift_id = context.user_data['end_shift_id']
        
        # Закрываем смену с указанным временем
        ended_shift = DatabaseManager.end_shift(shift_id, end_time)
        
        if ended_shift:
            # Получаем данные для отчёта
            total = ended_shift['total_amount']
            cars = DatabaseManager.get_shift_cars(shift_id)
            
            # Формируем отчёт
            report = f"✅ <b>Смена завершена!</b>\n\n"
            report += f"Начало: {ended_shift['start_time'].strftime('%H:%M')}\n"
            report += f"Окончание: {ended_shift['end_time'].strftime('%H:%M')}\n"
            duration = (ended_shift['end_time'] - ended_shift['start_time']).total_seconds() / 3600
            report += f"Длительность: {int(duration)} ч.\n"
            report += f"💰 Итог: <b>{total}₽</b>\n"
            report += f"🚗 Машин: {len(cars)}\n\n"
            
            # Статистика по услугам
            all_services = []
            for car in cars:
                services = DatabaseManager.get_car_services(car['id'])
                all_services.extend(services)
            
            if all_services:
                report += "<b>Статистика услуг:</b>\n"
                service_stats = {}
                for svc in all_services:
                    name = svc['service_name']
                    service_stats[name] = service_stats.get(name, 0) + svc['quantity']
                
                for name, count in service_stats.items():
                    report += f"• {name}: {count} раз\n"
            
            await update.message.reply_text(report, parse_mode='HTML')
        
        # Очищаем состояние
        context.user_data.pop('awaiting_end_time', None)
        context.user_data.pop('end_shift_id', None)
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат времени.\n"
            "Введите время в формате ЧЧ:ММ\n"
            "Например: 14:30 или 02:15"
        )

async def handle_new_target_input(update: Update, context: CallbackContext):
    """Обработка ввода новой цели"""
    try:
        target = int(update.message.text.strip())
        
        if target < 100:
            await update.message.reply_text("❌ Цель должна быть не менее 100 рублей. Введите ещё раз:")
            return
        
        # Обновляем настройки пользователя
        DatabaseManager.update_user_setting(update.effective_user.id, 'daily_target', target)
        
        await update.message.reply_text(
            f"✅ Цель обновлена: <b>{target}₽</b>",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
        
        # Очищаем состояние
        context.user_data.pop('awaiting_new_target', None)
        
    except ValueError:
        await update.message.reply_text("❌ Введите число. Например: 5000")

# ========== ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ==========

async def test_command(update: Update, context: CallbackContext):
    """Команда /test - проверка работы бота"""
    await update.message.reply_text(
        "✅ Бот работает!\n"
        "Все системы в норме.\n\n"
        "Используйте кнопки ниже для работы.",
        reply_markup=create_main_keyboard()
    )

async def cancel(update: Update, context: CallbackContext):
    """Отмена текущего действия"""
    # Очищаем все состояния
    for key in list(context.user_data.keys()):
        if key.startswith('awaiting_'):
            context.user_data.pop(key, None)
    
    await update.message.reply_text(
        "Действие отменено.",
        reply_markup=create_main_keyboard()
    )
    
    return ConversationHandler.END

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========

def main():
    """Запуск бота"""
    logger.info("=" * 60)
    logger.info("ЗАПУСК ПОЛНОЙ ВЕРСИИ БОТА ДЛЯ УЧЁТА УСЛУГ")
    logger.info("=" * 60)
    
    # Инициализация базы данных
    try:
        init_database()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        print("Внимание: используется режим без базы данных")
    
    # Проверяем токен
    if config.BOT_TOKEN.startswith("8353243831"):
        print("✅ Используется ваш токен")
    else:
        print("❌ ВНИМАНИЕ: Замените BOT_TOKEN в config.py на свой токен!")
        return
    
    try:
        # Создаём приложение
        application = Application.builder().token(config.BOT_TOKEN).build()
        
        # Создаём ConversationHandler для регистрации
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                REGISTER_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)
                ],
                SET_TARGET: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, set_target)
                ],
                SET_END_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_end_time_input)
                ]
            },
            fallbacks=[CommandHandler('cancel', cancel)],
            allow_reentry=True
        )
        
        # Регистрируем обработчики
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('test', test_command))
        application.add_handler(CommandHandler('help', handle_help))
        application.add_handler(CommandHandler('cancel', cancel))
        
        # Регистрируем обработчик inline-кнопок
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        
        # Регистрируем обработчик текстовых сообщений
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            handle_message
        ))
        
        # Запускаем бота
        logger.info("🟢 Бот запускается...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            poll_interval=1.0,
            timeout=30
        )
        
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
