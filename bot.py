"""
🤖 БОТ ДЛЯ УЧЁТА УСЛУГ - УПРОЩЕННАЯ ВЕРСИЯ
Просто работает
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    CallbackContext,
    filters,
)

from config import BOT_TOKEN, SERVICES, validate_car_number, get_correct_examples, get_allowed_letters_explained
from database import DatabaseManager, init_database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
init_database()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def get_current_price(service_id: int) -> int:
    """Получение текущей цены (день/ночь)"""
    service = SERVICES.get(service_id)
    if not service:
        return 0
    
    hour = datetime.now().hour
    if 21 <= hour or hour < 9:
        return service["night_price"]
    return service["day_price"]

def format_money(amount: int) -> str:
    """Форматирование денежной суммы"""
    return f"{amount:,}₽".replace(",", " ")

# ========== КЛАВИАТУРЫ ==========

def create_main_keyboard(has_active_shift: bool = False) -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = []
    
    if has_active_shift:
        keyboard.append([InlineKeyboardButton("🚗 Добавить машину", callback_data="add_car")])
        keyboard.append([InlineKeyboardButton("📊 Текущая смена", callback_data="current_shift")])
    else:
        keyboard.append([InlineKeyboardButton("📅 Открыть смену", callback_data="open_shift")])
    
    keyboard.append([InlineKeyboardButton("📜 История смен", callback_data="history_0")])
    keyboard.append([InlineKeyboardButton("⚙️ Настройки", callback_data="settings")])
    
    return InlineKeyboardMarkup(keyboard)

def create_services_keyboard(car_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора услуг"""
    keyboard = []
    
    # Все услуги
    for service_id, service in SERVICES.items():
        price = get_current_price(service_id)
        text = f"{service['name']} ({price}₽)"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"service_{service_id}_{car_id}")])
    
    keyboard.append([
        InlineKeyboardButton("🗑️ Очистить всё", callback_data=f"clear_{car_id}"),
        InlineKeyboardButton("💾 Сохранить", callback_data=f"save_{car_id}")
    ])
    
    return InlineKeyboardMarkup(keyboard)

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

async def start_command(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    user = update.effective_user
    
    if update.message:
        # Автоматическая регистрация
        db_user = DatabaseManager.get_user(user.id)
        
        if not db_user:
            name = user.first_name or user.username or "Пользователь"
            DatabaseManager.register_user(user.id, name)
        
        # Простое приветствие
        await update.message.reply_text(
            f"👋 Привет!\n"
            f"Я бот для учёта услуг на СТО.\n\n"
            f"Выберите действие:",
            reply_markup=create_main_keyboard()
        )

async def handle_message(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений"""
    user = update.effective_user
    text = update.message.text.strip()
    
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
        active_shift = DatabaseManager.get_active_shift(db_user['id'])
        
        if not active_shift:
            await update.message.reply_text(
                "❌ Нет активной смены! Сначала откройте смену."
            )
            context.user_data.pop('awaiting_car_number', None)
            return
        
        # Добавляем машину
        car_id = DatabaseManager.add_car(active_shift['id'], normalized_number)
        
        context.user_data.pop('awaiting_car_number', None)
        context.user_data['current_car'] = car_id
        
        await update.message.reply_text(
            f"🚗 Машина: {normalized_number}\n"
            f"Выберите услуги:",
            reply_markup=create_services_keyboard(car_id)
        )
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
    elif data.startswith("clear_"):
        await clear_services(query, context, data)
    elif data.startswith("save_"):
        await save_car(query, context, data)
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
        await query.edit_message_text(
            f"❌ У вас уже есть активная смена!\n"
            f"Начата: {active_shift['start_time'].strftime('%H:%M %d.%m')}",
            reply_markup=create_main_keyboard(True)
        )
        return
    
    # Создаём новую смену
    shift_id = DatabaseManager.start_shift(db_user['id'])
    
    await query.edit_message_text(
        f"✅ Смена открыта!\n"
        f"Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
        f"Теперь можно добавлять машины.",
        reply_markup=create_main_keyboard(True)
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
            "Сначала откройте смену.",
            reply_markup=create_main_keyboard(False)
        )
        return
    
    context.user_data['awaiting_car_number'] = True
    
    await query.edit_message_text(
        f"Введите номер машины:\n\n"
        f"Примеры правильных номеров:\n"
        f"• А123ВС777\n"
        f"• Х340РУ797\n"
        f"• В567ТХ799\n\n"
        f"Можно вводить русскими или английскими буквами."
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
            "Откройте смену для начала работы.",
            reply_markup=create_main_keyboard(False)
        )
        return
    
    cars = DatabaseManager.get_shift_cars(active_shift['id'])
    total = DatabaseManager.get_shift_total(active_shift['id'])
    
    message = (
        f"📊 ТЕКУЩАЯ СМЕНА\n\n"
        f"Начата: {active_shift['start_time'].strftime('%H:%M %d.%m.%Y')}\n"
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
            "Откройте первую смену!",
            reply_markup=create_main_keyboard(False)
        )
        return
    
    message = "📜 ИСТОРИЯ СМЕН\n\n"
    
    for shift in shifts:
        date_str = shift['created_at'].strftime("%d.%m")
        start_time = shift['start_time'].strftime("%H:%M")
        
        if shift['end_time']:
            end_time = shift['end_time'].strftime("%H:%M")
            time_str = f"{start_time}-{end_time}"
            status = "✅"
        else:
            time_str = f"{start_time}"
            status = "🟢"
        
        total = shift.get('total_amount', 0)
        message += f"{status} {date_str} {time_str} - {format_money(total)}\n"
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]])
    )

async def settings(query, context):
    """Настройки"""
    keyboard = [
        [InlineKeyboardButton("🎯 Изменить цель", callback_data="change_target")],
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
    if len(parts) < 3:
        return
    
    service_id = int(parts[1])
    car_id = int(parts[2])
    
    service = SERVICES.get(service_id)
    if not service:
        return
    
    price = get_current_price(service_id)
    
    # Добавляем услугу
    DatabaseManager.add_service_to_car(car_id, service_id, service['name'], price)
    
    # Обновляем отображение
    await show_car_services(query, car_id)

async def clear_services(query, context, data):
    """Очистка услуг"""
    parts = data.split('_')
    if len(parts) < 2:
        return
    
    car_id = int(parts[1])
    
    # Очищаем услуги
    DatabaseManager.clear_car_services(car_id)
    
    await show_car_services(query, car_id)

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
            f"Не выбрано ни одной услуги.",
            reply_markup=create_main_keyboard(True)
        )
        return
    
    await query.edit_message_text(
        f"✅ Машина {car['car_number']} сохранена!\n"
        f"Сумма: {format_money(car['total_amount'])}\n\n"
        f"Можете добавить следующую машину.",
        reply_markup=create_main_keyboard(True)
    )

async def show_car_services(query, car_id: int):
    """Показать услуги машины"""
    car = DatabaseManager.get_car(car_id)
    if not car:
        await query.edit_message_text("❌ Машина не найдена")
        return
    
    services = DatabaseManager.get_car_services(car_id)
    
    services_text = ""
    for service in services:
        services_text += f"• {service['service_name']} ({service['price']}₽) ×{service['quantity']}\n"
    
    if not services_text:
        services_text = "Нет выбранных услуг\n"
    
    message = (
        f"🚗 Машина: {car['car_number']}\n"
        f"Итог: {format_money(car['total_amount'])}\n\n"
        f"Услуги:\n{services_text}\n"
        f"Выберите ещё:"
    )
    
    await query.edit_message_text(
        message,
        reply_markup=create_services_keyboard(car_id)
    )

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
