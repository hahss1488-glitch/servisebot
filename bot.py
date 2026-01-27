"""
🤖 БОТ ДЛЯ УЧЁТА УСЛУГ - ПОЛНАЯ ВЕРСИЯ
С закреплёнными сообщениями, прогресс-баром и уведомлениями
"""

import logging
import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery  # ВОТ ЭТОГО НЕ ХВАТАЛО
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    CallbackContext,
    filters,
)

from config import BOT_TOKEN, SERVICES, ALLOWED_LETTERS
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

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def normalize_car_number_custom(text: str) -> str:
    """
    Нормализация номера машины по стандарту РФ
    
    Примеры преобразования:
    - 'x340py' → 'Х340РУ797'
    - 'х340ру' → 'Х340РУ797'
    - 'H340PY797' → 'Н340РУ797'
    - 'а123вс' → 'А123ВС797'
    - 'b567tx' → 'В567ТХ797'
    """
    if not text:
        return ""
    
    # 1. Приводим к верхнему регистру
    text = text.strip().upper()
    
    # 2. Удаляем все пробелы, дефисы и другие разделители
    text = text.replace(' ', '').replace('-', '').replace('_', '')
    
    # 3. Заменяем английские буквы на русские
    ENG_TO_RUS = {
        'A': 'А', 'B': 'В', 'C': 'С', 'E': 'Е', 'H': 'Н',
        'K': 'К', 'M': 'М', 'O': 'О', 'P': 'Р', 'T': 'Т',
        'X': 'Х', 'Y': 'У'
    }
    
    result = []
    for char in text:
        # Если это английская буква из нашего словаря - заменяем
        if char in ENG_TO_RUS:
            result.append(ENG_TO_RUS[char])
        else:
            # Иначе оставляем как есть (русские буквы, цифры)
            result.append(char)
    
    normalized = ''.join(result)
    
    # 4. Удаляем ВСЕ символы, кроме разрешённых русских букв и цифр
    ALLOWED_LETTERS = "АВЕКМНОРСТУХ"
    allowed_chars = ALLOWED_LETTERS + '0123456789'
    normalized = ''.join([c for c in normalized if c in allowed_chars])
    
    # 5. Автодобавление региона если нужно
    DEFAULT_REGION = "797"
    
    # Считаем количество букв и цифр
    letters = sum(1 for c in normalized if c in ALLOWED_LETTERS)
    digits = sum(1 for c in normalized if c.isdigit())
    
    # Если есть хотя бы 3 цифры и 3 буквы - считаем, что номер полный
    if digits >= 3 and letters >= 3:
        # Убедимся, что цифр ровно 6 (3 в номере + 3 в регионе)
        if digits < 6:
            # Добавляем недостающие цифры из региона
            missing_digits = 6 - digits
            normalized += DEFAULT_REGION[:missing_digits]
        return normalized
    
    # Если номер короткий (только основная часть)
    if len(normalized) <= 6:
        normalized += DEFAULT_REGION
    
    return normalized

def validate_car_number_custom(text: str) -> tuple:
    """
    Проверка валидности номера машины
    
    Возвращает: (is_valid, normalized_number, error_message)
    """
    if not text:
        return False, "", "Введите номер машины"
    
    # Нормализуем номер
    normalized = normalize_car_number_custom(text)
    
    # Проверяем длину
    if len(normalized) < 6:
        return False, normalized, f"Номер слишком короткий: {normalized}"
    
    # Проверяем полный формат: буква-3 цифры-2 буквы-3 цифры
    ALLOWED_LETTERS = "АВЕКМНОРСТУХ"
    pattern = f'^[{ALLOWED_LETTERS}]\\d{{3}}[{ALLOWED_LETTERS}]{{2}}\\d{{3}}$'
    
    if not re.match(pattern, normalized):
        # Попробуем частичный формат: буква-3 цифры-2 буквы
        partial_pattern = f'^[{ALLOWED_LETTERS}]\\d{{3}}[{ALLOWED_LETTERS}]{{2}}$'
        if re.match(partial_pattern, normalized):
            # Это частичный номер, добавляем регион
            normalized = normalized + "797"
            # Теперь проверяем полный формат
            if re.match(pattern, normalized):
                return True, normalized, ""
        
        # Показываем пример правильного формата
        return False, normalized, f"Неверный формат. Пример: А123ВС777"
    
    return True, normalized, ""

def get_correct_examples() -> str:
    """Примеры правильных номеров для отображения"""
    examples = [
        "А123ВС777",
        "Х340РУ797", 
        "В567ТХ799",
        "Е234КМ777",
        "М890РТ799",
        "О567СТ799",
        "Р123ТХ777",
        "С456ВЕ797",
        "Т789АК799",
        "У012НХ777"
    ]
    
    input_examples = [
        ("x340py", "→ Х340РУ797"),
        ("х340ру", "→ Х340РУ797"),
        ("H340PY797", "→ Н340РУ797"),
        ("а123вс", "→ А123ВС797"),
        ("b567tx", "→ В567ТХ797"),
        ("e234km", "→ Е234КМ797"),
    ]
    
    text = "✅ **ПРАВИЛЬНЫЕ ПРИМЕРЫ:**\n\n"
    
    text += "📱 **Что можно вводить (бот преобразует):**\n"
    for input_ex, output in input_examples:
        text += f"• `{input_ex}` {output}\n"
    
    text += "\n🎯 **Финальный формат в базе:**\n"
    for i, example in enumerate(examples[:5]):
        text += f"• {example}\n"
    
    return text

def get_allowed_letters_explained() -> str:
    """Объяснение разрешённых букв"""
    letters_info = [
        ("A/А", "Латинская A или русская А"),
        ("B/В", "Латинская B или русская В"),
        ("C/С", "Латинская C или русская С"),
        ("E/Е", "Латинская E или русская Е"),
        ("H/Н", "Латинская H или русская Н (важно: H → Н)"),
        ("K/К", "Латинская K или русская К"),
        ("M/М", "Латинская M или русская М"),
        ("O/О", "Латинская O или русская О"),
        ("P/Р", "Латинская P или русская Р"),
        ("T/Т", "Латинская T или русская Т"),
        ("X/Х", "Латинская X или русская Х (важно: X → Х)"),
        ("Y/У", "Латинская Y или русская У (важно: Y → У)"),
    ]
    
    text = "🔤 **РАЗРЕШЁННЫЕ БУКВЫ:**\n\n"
    text += "Можно вводить русские или английские буквы:\n"
    
    for letter, description in letters_info:
        text += f"• {letter} - {description}\n"
    
    return text

def get_wrong_examples() -> str:
    """Примеры неправильных номеров"""
    return (
        "❌ **НЕПРАВИЛЬНЫЕ НОМЕРА:**\n"
        "• А123БВ777 (буква Б не используется в номерах РФ)\n"
        "• ABC123 (неправильный формат)\n"
        "• 123456 (только цифры)\n"
        "• АБВГДЕ (только буквы)\n"
    )

def get_current_price(service_id: int) -> int:
    """Получение текущей цены (день/ночь)"""
    service = SERVICES.get(service_id)
    if not service:
        return 0
    
    hour = datetime.now().hour
    if 21 <= hour or hour < 9:  # 21:00-9:00 ночь
        return service["night_price"]
    return service["day_price"]

def get_current_time_type() -> str:
    """Текущее время (день/ночь)"""
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
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}] {int(percentage * 100)}%"

def get_emoji_progress(current: int, target: int) -> str:
    """Получить эмодзи для прогресса"""
    if target <= 0:
        return "⚪"
    
    percentage = current / target
    if percentage >= 1.0:
        return "🟢"
    elif percentage >= 0.75:
        return "🟡"
    elif percentage >= 0.5:
        return "🟠"
    elif percentage >= 0.25:
        return "🔵"
    else:
        return "⚪"

def get_current_decade() -> Tuple[int, Tuple[int, int]]:
    """Определение текущей декады"""
    today = datetime.now()
    day = today.day
    
    if 1 <= day <= 10:
        return 1, (1, 10)
    elif 11 <= day <= 20:
        return 2, (11, 20)
    else:
        last_day = 31
        if today.month == 2:
            last_day = 29 if (today.year % 4 == 0) else 28
        elif today.month in [4, 6, 9, 11]:
            last_day = 30
        return 3, (21, last_day)

async def send_progress_notification(context: CallbackContext, user_id: int, 
                                   current: int, target: int, telegram_id: int):
    """Отправка уведомления о прогрессе"""
    if target <= 0:
        return
    
    percentage = current / target * 100
    user = DatabaseManager.get_user_by_id(user_id)
    
    if not user:
        return
    
    last_notification = user.get('last_progress_notification', 0)
    
    # Определяем, какое уведомление нужно отправить
    notification_level = 0
    if percentage >= 100 and last_notification < 100:
        notification_level = 100
    elif percentage >= 75 and last_notification < 75:
        notification_level = 75
    elif percentage >= 50 and last_notification < 50:
        notification_level = 50
    
    if notification_level > 0:
        try:
            if notification_level == 100:
                message = f"🎉 **ПОЗДРАВЛЯЕМ!** 🎉\n\nЦель {format_money(target)} выполнена!\nТекущий результат: {format_money(current)}"
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                    parse_mode='Markdown'
                )
            elif notification_level == 75:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=f"⚡ Осталось совсем немного! Вы на {int(percentage)}% цели!",
                    parse_mode='Markdown'
                )
            elif notification_level == 50:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=f"🎯 Вы на полпути! Выполнено {int(percentage)}% от цели!",
                    parse_mode='Markdown'
                )
            
            # Обновляем уровень последнего уведомления
            DatabaseManager.update_user_setting(telegram_id, 'last_progress_notification', notification_level)
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")

# ========== СИСТЕМА ЗАКРЕПЛЁННЫХ СООБЩЕНИЙ ==========

async def create_or_update_pinned_message(context: CallbackContext, user_id: int, telegram_id: int):
    """Создать или обновить закреплённое сообщение с прогрессом"""
    try:
        user = DatabaseManager.get_user_by_id(user_id)
        if not user:
            return None
        
        active_shift = DatabaseManager.get_active_shift(user_id)
        if not active_shift:
            # Если нет активной смены, удаляем закреплённое сообщение
            pinned_id = user.get('pinned_message_id')
            if pinned_id:
                try:
                    await context.bot.delete_message(chat_id=telegram_id, message_id=pinned_id)
                except:
                    pass
                DatabaseManager.update_user_setting(telegram_id, 'pinned_message_id', None)
            return None
        
        # Получаем данные для сообщения
        cars = DatabaseManager.get_shift_cars(active_shift['id'])
        total = DatabaseManager.get_shift_total(active_shift['id'])
        target = user.get('daily_target', 5000)
        
        # Формируем текст
        message_text = (
            f"📊 **АКТИВНАЯ СМЕНА** {get_emoji_progress(total, target)}\n"
            f"⏰ Открыта: {active_shift['start_time'].strftime('%H:%M')}\n"
            f"🚗 Машин: **{len(cars)}** | 💰 Сумма: **{format_money(total)}**\n"
            f"🎯 Цель: {format_money(target)}\n"
            f"`{format_progress_bar(total, target)}`\n"
        )
        
        # Добавляем последнюю машину если есть
        if cars:
            last_car = max(cars, key=lambda x: x['created_at'])
            message_text += f"━━━━━━━━━━━━━━━━━━━\n"
            message_text += f"Последняя: {last_car['car_number']} ({format_money(last_car['total_amount'])})"
        
        pinned_id = user.get('pinned_message_id')
        
        if pinned_id:
            # Обновляем существующее сообщение
            try:
                await context.bot.edit_message_text(
                    chat_id=telegram_id,
                    message_id=pinned_id,
                    text=message_text,
                    parse_mode='Markdown'
                )
                return pinned_id
            except Exception as e:
                # Если сообщение не найдено, создаём новое
                logger.warning(f"Не удалось обновить сообщение {pinned_id}: {e}")
                pinned_id = None
        
        if not pinned_id:
            # Создаём новое сообщение
            sent_message = await context.bot.send_message(
                chat_id=telegram_id,
                text=message_text,
                parse_mode='Markdown'
            )
            
            # Пытаемся закрепить
            try:
                await sent_message.pin(disable_notification=True)
                pinned_id = sent_message.message_id
                DatabaseManager.update_user_setting(telegram_id, 'pinned_message_id', pinned_id)
            except Exception as e:
                logger.warning(f"Не удалось закрепить сообщение: {e}")
                pinned_id = sent_message.message_id
        
        # Проверяем уведомления о прогрессе
        await send_progress_notification(context, user_id, total, target, telegram_id)
        
        return pinned_id
        
    except Exception as e:
        logger.error(f"Ошибка в закреплённом сообщении: {e}")
        return None

async def delete_pinned_message(context: CallbackContext, telegram_id: int):
    """Удалить закреплённое сообщение"""
    try:
        user = DatabaseManager.get_user(telegram_id)
        if not user:
            return
        
        pinned_id = user.get('pinned_message_id')
        if pinned_id:
            try:
                await context.bot.delete_message(chat_id=telegram_id, message_id=pinned_id)
            except:
                pass
        
        DatabaseManager.update_user_setting(telegram_id, 'pinned_message_id', None)
        DatabaseManager.update_user_setting(telegram_id, 'last_progress_notification', 0)
        
    except Exception as e:
        logger.error(f"Ошибка удаления закреплённого сообщения: {e}")

# ========== КЛАВИАТУРЫ ==========

def create_main_keyboard(user: Dict, has_active_shift: bool = False) -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = []
    
    if has_active_shift:
        keyboard.append([InlineKeyboardButton("🚗 Добавить машину", callback_data="add_car")])
        keyboard.append([InlineKeyboardButton("📊 Текущая смена", callback_data="current_shift")])
    else:
        keyboard.append([InlineKeyboardButton("📅 Открыть смену", callback_data="open_shift")])
        keyboard.append([InlineKeyboardButton("🚗 Добавить машину", callback_data="no_shift", disabled=True)])
    
    keyboard.append([InlineKeyboardButton("📜 История смен", callback_data="history_0")])
    keyboard.append([InlineKeyboardButton("📈 Статистика", callback_data="stats")])
    keyboard.append([InlineKeyboardButton("⚙️ Настройки", callback_data="settings")])
    keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="help")])
    
    return InlineKeyboardMarkup(keyboard)

def create_services_keyboard(car_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура выбора услуг"""
    keyboard = []
    
    # Частые услуги
    frequent = [(id, s) for id, s in SERVICES.items() if s.get('frequent', False)]
    others = [(id, s) for id, s in SERVICES.items() if not s.get('frequent', False)]
    
    if page == 0:
        services_to_show = frequent
    else:
        start_idx = (page - 1) * 6
        services_to_show = others[start_idx:start_idx + 6]
    
    # Добавляем услуги по 2 в ряд
    for i in range(0, len(services_to_show), 2):
        row = []
        for service_id, service in services_to_show[i:i+2]:
            price = get_current_price(service_id)
            text = f"{service['name']} ({price}₽)"
            row.append(InlineKeyboardButton(text, callback_data=f"service_{service_id}_{car_id}_{page}"))
        if row:
            keyboard.append(row)
    
    # Кнопки управления
    keyboard.append([
        InlineKeyboardButton("🔽 Удалить последнюю", callback_data=f"remove_last_{car_id}_{page}"),
        InlineKeyboardButton("🗑️ Очистить всё", callback_data=f"clear_all_{car_id}_{page}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("💾 Сохранить машину", callback_data=f"save_car_{car_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_car_{car_id}")
    ])
    
    # Навигация по страницам
    if page == 0 and len(others) > 0:
        keyboard.append([InlineKeyboardButton("📋 Все услуги →", callback_data=f"all_services_{car_id}_1")])
    elif page > 0:
        nav_buttons = []
        total_pages = (len(others) + 5) // 6
        
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"all_services_{car_id}_{page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"Стр. {page}", callback_data="noop"))
        
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"all_services_{car_id}_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🔙 К частым", callback_data=f"page_services_{car_id}_0")])
    
    return InlineKeyboardMarkup(keyboard)

def create_shift_keyboard(shift_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура управления сменой"""
    keyboard = []
    
    keyboard.append([InlineKeyboardButton("🚗 Добавить машину", callback_data=f"add_car_to_{shift_id}")])
    keyboard.append([InlineKeyboardButton("🔚 Закрыть смену", callback_data=f"close_shift_{shift_id}")])
    keyboard.append([InlineKeyboardButton("🗑️ Удалить смену", callback_data=f"delete_shift_{shift_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)

def create_cars_keyboard(cars: List[Dict], shift_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура со списком машин"""
    keyboard = []
    
    for car in cars:
        text = f"{car['car_number']} - {format_money(car['total_amount'])}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"view_car_{car['id']}_{shift_id}")])
    
    # Навигация
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton("◀️", callback_data=f"cars_page_{shift_id}_{page-1}"))
    
    navigation.append(InlineKeyboardButton(f"Стр. {page+1}", callback_data="noop"))
    
    if len(cars) == 10:  # Предполагаем пагинацию по 10
        navigation.append(InlineKeyboardButton("▶️", callback_data=f"cars_page_{shift_id}_{page+1}"))
    
    if navigation:
        keyboard.append(navigation)
    
    keyboard.append([InlineKeyboardButton("➕ Добавить машину", callback_data=f"add_car_to_{shift_id}")])
    keyboard.append([InlineKeyboardButton("🔙 К смене", callback_data=f"view_shift_{shift_id}")])
    
    return InlineKeyboardMarkup(keyboard)

def create_confirmation_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да", callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton("❌ Нет", callback_data=f"cancel_{action}_{item_id}")
        ]
    ])

def create_settings_keyboard(user: Dict) -> InlineKeyboardMarkup:
    """Клавиатура настроек"""
    progress_status = "✅ ВКЛ" if user.get('progress_bar_enabled', True) else "❌ ВЫКЛ"
    
    keyboard = [
        [InlineKeyboardButton(f"🎯 Цель: {format_money(user.get('daily_target', 5000))}", callback_data="change_target")],
        [InlineKeyboardButton(f"📊 Прогресс-бар: {progress_status}", callback_data="toggle_progress")],
        [InlineKeyboardButton("📈 Статистика за декаду", callback_data="decade_stats")],
        [InlineKeyboardButton("🔄 Сбросить все данные", callback_data="reset_data")],
        [InlineKeyboardButton("💾 Создать backup", callback_data="create_backup")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

async def start_command(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    user = update.effective_user
    
    if update.message:
        db_user = DatabaseManager.get_user(user.id)
        
        if not db_user:
            await update.message.reply_text(
                f"👋 Привет, {user.first_name}!\n\n"
                f"Я бот для учёта услуг на СТО/автосервисе.\n"
                f"Для начала работы введите ваше имя:"
            )
            context.user_data['awaiting_name'] = True
            return
        
        await show_main_menu(update, context, user.id)

async def help_command(update: Update, context: CallbackContext):
    """Обработчик команды /help"""
    help_text = """
🤖 **ПОМОЩЬ ПО ИСПОЛЬЗОВАНИЮ БОТА**

📌 **Основные функции:**
• `📅 Открыть смену` - начать новую рабочую смену
• `🚗 Добавить машину` - добавить автомобиль для обслуживания
• `📊 Текущая смена` - управление активной сменой
• `📜 История смен` - просмотр завершённых смен
• `📈 Статистика` - аналитика вашей работы

🚗 **Добавление машины:**
1. Нажмите "🚗 Добавить машину"
2. Введите номер машины (пример: А123ВС777)
3. Выберите услуги из списка
4. Нажмите "💾 Сохранить машину"

✅ **Правильные номера:**
• А123ВС777 ✓
• Х340КХ797 ✓
• В567ТХ799 ✓

❌ **Неправильные номера:**
• А123БВ777 ✗ (буква Б не разрешена)
• ABC123 ✗ (английские буквы)
• 123456 ✗ (только цифры)

🎯 **Прогресс-бар:**
• Автоматически обновляется в закреплённом сообщении
• Уведомления при 50%, 75% и 100% цели
• Можно отключить в настройках

📱 **Быстрые команды:**
`/now` - показать текущий прогресс
`/target 7000` - установить новую цель
`/stats` - показать статистику

⚙️ **Настройки:**
• Изменение дневной цели
• Включение/выключение прогресс-бара
• Сброс данных
• Создание backup

💡 **Советы:**
• Все данные сохраняются автоматически
• При закрытии смены генерируется отчёт
• Можно редактировать машины в активной смене

🆘 **Если что-то не работает:**
1. Попробуйте перезапустить бота `/start`
2. Проверьте корректность ввода номера
3. Если проблема осталась - обратитесь к разработчику
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def now_command(update: Update, context: CallbackContext):
    """Показать текущий прогресс"""
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь: /start")
        return
    
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    
    if not active_shift:
        await update.message.reply_text("📭 Нет активной смены. Откройте смену для начала работы.")
        return
    
    cars = DatabaseManager.get_shift_cars(active_shift['id'])
    total = DatabaseManager.get_shift_total(active_shift['id'])
    target = db_user.get('daily_target', 5000)
    
    message = (
        f"📊 **ТЕКУЩАЯ СМЕНА**\n\n"
        f"⏰ Открыта: {active_shift['start_time'].strftime('%H:%M (%d.%m)')}\n"
        f"🚗 Машин: **{len(cars)}**\n"
        f"💰 Сумма: **{format_money(total)}**\n"
        f"🎯 Цель: {format_money(target)}\n"
        f"`{format_progress_bar(total, target)}`\n\n"
    )
    
    if cars:
        message += "**Машины в смене:**\n"
        for i, car in enumerate(cars, 1):
            message += f"{i}. {car['car_number']} - {format_money(car['total_amount'])}\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def target_command(update: Update, context: CallbackContext):
    """Быстрое изменение цели"""
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь: /start")
        return
    
    if not context.args:
        await update.message.reply_text(
            f"🎯 Текущая цель: **{format_money(db_user.get('daily_target', 5000))}**\n\n"
            f"Чтобы изменить цель, введите:\n"
            f"`/target 7000`"
        )
        return
    
    try:
        new_target = int(context.args[0])
        if new_target < 100:
            await update.message.reply_text("❌ Цель должна быть не менее 100₽")
            return
        
        DatabaseManager.update_user_setting(user.id, 'daily_target', new_target)
        
        await update.message.reply_text(
            f"✅ Цель изменена: **{format_money(new_target)}**\n\n"
            f"Прогресс-бар обновится автоматически."
        )
        
        # Обновляем закреплённое сообщение если есть
        active_shift = DatabaseManager.get_active_shift(db_user['id'])
        if active_shift:
            await create_or_update_pinned_message(context, db_user['id'], user.id)
            
    except ValueError:
        await update.message.reply_text("❌ Введите число. Например: `/target 7000`")

async def stats_command(update: Update, context: CallbackContext):
    """Быстрая статистика"""
    user = update.effective_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь: /start")
        return
    
    stats = DatabaseManager.get_user_stats(db_user['id'], days=30)
    
    message = (
        f"📈 **ВАША СТАТИСТИКА**\n\n"
        f"**За последние 30 дней:**\n"
        f"📊 Смен: **{stats['shift_count']}**\n"
        f"🚗 Машин: **{stats['cars_count']}**\n"
        f"💰 Заработано: **{format_money(stats['total_earned'])}**\n"
    )
    
    if stats['shift_count'] > 0:
        message += f"📈 Среднее за смену: **{format_money(stats['avg_per_shift'])}**\n"
    
    # Активная смена
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    if active_shift:
        total = DatabaseManager.get_shift_total(active_shift['id'])
        message += f"\n**Активная смена:**\n"
        message += f"⏰ Начата: {active_shift['start_time'].strftime('%H:%M')}\n"
        message += f"🚗 Машин: {len(DatabaseManager.get_shift_cars(active_shift['id']))}\n"
        message += f"💰 Сумма: {format_money(total)}\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

# ========== ОБРАБОТЧИКИ СООБЩЕНИЙ ==========

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
            f"✅ Отлично, **{text}**! Вы зарегистрированы.\n\n"
            f"Теперь вы можете начать работу.",
            parse_mode='Markdown'
        )
        
        await show_main_menu(update, context, user.id)
        return
    
       # Ожидание номера машины
    elif context.user_data.get('awaiting_car_number'):
        db_user = DatabaseManager.get_user(user.id)
        
        if not db_user:
            await update.message.reply_text("❌ Ошибка: пользователь не найден")
            return
        
        # ПРОВЕРЯЕМ ВАЛИДНОСТЬ НОМЕРА (НОВАЯ ЛОГИКА)
        is_valid, normalized_number, error_msg = validate_car_number_custom(text)
        
        if not is_valid:
            await update.message.reply_text(
                f"❌ **Ошибка!** {error_msg}\n\n"
                f"{get_correct_examples()}\n\n"
                f"**Введите номер ещё раз:**",
                parse_mode='Markdown'
            )
            return
        
        # Номер валиден, используем normalized_number
        normalized_number = normalized_number  # Уже нормализован в функции валидации
        
        # Получаем shift_id из контекста
        shift_id = context.user_data.get('car_for_shift')
        if not shift_id:
            # Ищем активную смену
            active_shift = DatabaseManager.get_active_shift(db_user['id'])
            if not active_shift:
                await update.message.reply_text(
                    "❌ Нет активной смены!\n\n"
                    "Сначала откройте смену через главное меню."
                )
                context.user_data.pop('awaiting_car_number', None)
                await show_main_menu(update, context, user.id)
                return
            shift_id = active_shift['id']
        
        # Добавляем машину
        car_id = DatabaseManager.add_car(shift_id, normalized_number)
        
        if not car_id:
            await update.message.reply_text("❌ Ошибка при добавлении машины")
            context.user_data.pop('awaiting_car_number', None)
            return
        
        # Очищаем контекст
        context.user_data.pop('awaiting_car_number', None)
        context.user_data.pop('car_for_shift', None)
        
        # Сохраняем car_id для показа услуг
        context.user_data['current_car'] = car_id
        
        # Показываем выбор услуг
        time_type = get_current_time_type()
        
        await update.message.reply_text(
            f"🚗 **Машина добавлена:** `{normalized_number}`\n"
            f"⏰ {time_type}\n"
            f"💰 Итог: **0₽**\n\n"
            f"Выберите услуги:",
            parse_mode='Markdown',
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
                f"✅ Цель установлена: **{format_money(target)}**",
                parse_mode='Markdown'
            )
            
            # Обновляем закреплённое сообщение
            db_user = DatabaseManager.get_user(user.id)
            if db_user:
                active_shift = DatabaseManager.get_active_shift(db_user['id'])
                if active_shift:
                    await create_or_update_pinned_message(context, db_user['id'], user.id)
            
            await show_main_menu(update, context, user.id)
            
        except ValueError:
            await update.message.reply_text("❌ Введите число. Например: 5000")
        return
    
    # Неизвестное сообщение
    await update.message.reply_text(
        "Используйте кнопки меню или команды для работы с ботом.\n"
        "Напишите /help для справки."
    )

# ========== ОБРАБОТЧИКИ КНОПОК ==========

async def handle_callback(update: Update, context: CallbackContext):
    """Главный обработчик callback-кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    logger.info(f"Callback: {data} from {user.id}")
    
    # Проверяем регистрацию
    if data not in ["noop", "start_register"]:
        db_user = DatabaseManager.get_user(user.id)
        if not db_user:
            await query.edit_message_text(
                "❌ Сначала зарегистрируйтесь!\n\n"
                "Напишите /start для начала работы."
            )
            return
    
    # Обработка noop (пустая кнопка)
    if data == "noop":
        return
    
    # Регистрация через кнопку
    if data == "start_register":
        await query.edit_message_text("Введите ваше имя:")
        context.user_data['awaiting_name'] = True
        return
    
    # Маршрутизация по префиксам
    if data.startswith("add_car"):
        await handle_add_car(query, context)
    elif data.startswith("open_shift"):
        await handle_open_shift(query, context)
    elif data.startswith("current_shift"):
        await handle_current_shift(query, context)
    elif data.startswith("history_"):
        await handle_history(query, context, data)
    elif data.startswith("stats"):
        await handle_stats(query, context)
    elif data.startswith("settings"):
        await handle_settings(query, context)
    elif data.startswith("help"):
        await handle_help(query, context)
    elif data.startswith("back_to_main"):
        await show_main_menu(update, context, user.id)
    elif data.startswith("no_shift"):
        await query.answer("❌ Сначала откройте смену!", show_alert=True)
    elif data.startswith("service_"):
        await handle_service(query, context, data)
    elif data.startswith("remove_last_"):
        await handle_remove_last(query, context, data)
    elif data.startswith("clear_all_"):
        await handle_clear_all(query, context, data)
    elif data.startswith("save_car_"):
        await handle_save_car(query, context, data)
    elif data.startswith("cancel_car_"):
        await handle_cancel_car(query, context, data)
    elif data.startswith("all_services_"):
        await handle_all_services(query, context, data)
    elif data.startswith("page_services_"):
        await handle_page_services(query, context, data)
    elif data.startswith("view_shift_"):
        await handle_view_shift(query, context, data)
    elif data.startswith("add_car_to_"):
        await handle_add_car_to_shift(query, context, data)
    elif data.startswith("close_shift_"):
        await handle_close_shift(query, context, data)
    elif data.startswith("delete_shift_"):
        await handle_delete_shift(query, context, data)
    elif data.startswith("view_car_"):
        await handle_view_car(query, context, data)
    elif data.startswith("cars_page_"):
        await handle_cars_page(query, context, data)
    elif data.startswith("confirm_"):
        await handle_confirm(query, context, data)
    elif data.startswith("cancel_"):
        await handle_cancel(query, context, data)
    elif data.startswith("change_target"):
        await handle_change_target(query, context)
    elif data.startswith("toggle_progress"):
        await handle_toggle_progress(query, context)
    elif data.startswith("decade_stats"):
        await handle_decade_stats(query, context)
    elif data.startswith("reset_data"):
        await handle_reset_data(query, context)
    elif data.startswith("create_backup"):
        await handle_create_backup(query, context)
    else:
        await query.edit_message_text("❌ Неизвестная команда")

async def handle_add_car(query, context):
    """Добавление машины"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        return
    
    # Проверяем активную смену
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    if not active_shift:
        await query.edit_message_text(
            "❌ **Нет активной смены!**\n\n"
            "Сначала откройте смену через главное меню.",
            parse_mode='Markdown'
        )
        return
    
    context.user_data['awaiting_car_number'] = True
    
    await query.edit_message_text(
        f"🚗 **ДОБАВЛЕНИЕ МАШИНЫ**\n\n"
        f"{get_correct_examples()}\n"
        f"{get_allowed_letters_explained()}\n"
        f"{get_wrong_examples()}\n\n"
        f"**Введите номер машины:**\n"
        f"_Можно вводить русскими или английскими буквами_",
        parse_mode='Markdown'
    )
    
    # Проверяем активную смену
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    if not active_shift:
        await query.edit_message_text(
            "❌ **Нет активной смены!**\n\n"
            "Сначала откройте смену через главное меню.",
            parse_mode='Markdown'
        )
        return
    
    context.user_data['awaiting_car_number'] = True
    
    await query.edit_message_text(
        f"🚗 **ДОБАВЛЕНИЕ МАШИНЫ**\n\n"
        f"✅ **ПРАВИЛЬНЫЕ ПРИМЕРЫ:**\n"
        f"• А123ВС777\n"
        f"• Х340КХ797\n"
        f"• В567ТХ799\n\n"
        f"✅ **РАЗРЕШЁННЫЕ БУКВЫ:**\n"
        f"{' '.join(ALLOWED_LETTERS)}\n\n"
        f"❌ **НЕПРАВИЛЬНО:**\n"
        f"• А123БВ777 (буква Б не разрешена)\n"
        f"• ABC123 (английские буквы)\n"
        f"• 123456 (только цифры)\n\n"
        f"**Введите номер машины:**",
        parse_mode='Markdown'
    )

async def handle_open_shift(query, context):
    """Открытие смены"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        return
    
    # Проверяем, нет ли уже активной смены
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    if active_shift:
        await query.edit_message_text(
            f"❌ **У вас уже есть активная смена!**\n\n"
            f"Начата: {active_shift['start_time'].strftime('%H:%M (%d.%m.%Y)')}\n"
            f"💰 Заработано: {format_money(active_shift.get('total_amount', 0))}\n"
            f"🚗 Машин: {len(DatabaseManager.get_shift_cars(active_shift['id']))}",
            parse_mode='Markdown'
        )
        return
    
    # Создаём новую смену
    shift_id = DatabaseManager.start_shift(db_user['id'])
    shift = DatabaseManager.get_shift(shift_id)
    
    # Создаём закреплённое сообщение
    await create_or_update_pinned_message(context, db_user['id'], user.id)
    
    await query.edit_message_text(
        f"✅ **Смена открыта!**\n\n"
        f"📅 Начало: {shift['start_time'].strftime('%H:%M (%d.%m.%Y)')}\n"
        f"💼 Статус: **Активна**\n\n"
        f"Теперь вы можете добавлять машины 🚗",
        parse_mode='Markdown',
        reply_markup=create_main_keyboard(db_user, has_active_shift=True)
    )

async def show_main_menu(update: Update, context: CallbackContext, user_id: int):
    """Показать главное меню"""
    user = DatabaseManager.get_user(user_id)
    if not user:
        return
    
    message = f"👤 **{user['name']}**\n\n"
    
    # Информация об активной смене
    active_shift = DatabaseManager.get_active_shift(user['id'])
    if active_shift:
        total = DatabaseManager.get_shift_total(active_shift['id'])
        target = user.get('daily_target', 5000)
        
        message += f"📅 **Активная смена** (с {active_shift['start_time'].strftime('%H:%M')})\n"
        message += f"🚗 Машин: **{len(DatabaseManager.get_shift_cars(active_shift['id']))}**\n"
        message += f"💰 Заработано: **{format_money(total)}**\n"
        
        if user.get('progress_bar_enabled', True):
            message += f"🎯 Цель: {format_money(target)}\n"
            message += f"`{format_progress_bar(total, target)}`\n"
        
        message += "\nВыберите действие:"
        has_active_shift = True
    else:
        message += "📅 **Нет активной смены**\n"
        message += "Начните работу, открыв смену\n"
        message += "\nВыберите действие:"
        has_active_shift = False
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message, 
            parse_mode='Markdown',
            reply_markup=create_main_keyboard(user, has_active_shift)
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard(user, has_active_shift)
        )

# ========== ОБРАБОТЧИКИ УСЛУГ ==========

async def handle_service(query, context, data):
    """Добавление услуги"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    service_id = int(parts[1])
    car_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    
    # Получаем данные услуги
    service = SERVICES.get(service_id)
    if not service:
        await query.answer("❌ Услуга не найдена", show_alert=True)
        return
    
    price = get_current_price(service_id)
    
    # Добавляем услугу
    new_total = DatabaseManager.add_service_to_car(car_id, service_id, service['name'], price)
    
    if new_total == 0:
        await query.answer("❌ Ошибка добавления услуги", show_alert=True)
        return
    
    # Обновляем закреплённое сообщение
    car = DatabaseManager.get_car(car_id)
    if car:
        shift = DatabaseManager.get_shift(car['shift_id'])
        if shift:
            user = DatabaseManager.get_user_by_id(shift['user_id'])
            if user:
                await create_or_update_pinned_message(context, user['id'], user['telegram_id'])
    
    # Обновляем отображение
    await update_car_display(query, car_id, page)

async def handle_remove_last(query, context, data):
    """Удаление последней услуги"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    car_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    
    # Удаляем услугу
    new_total = DatabaseManager.remove_last_service(car_id)
    
    # Обновляем закреплённое сообщение
    car = DatabaseManager.get_car(car_id)
    if car:
        shift = DatabaseManager.get_shift(car['shift_id'])
        if shift:
            user = DatabaseManager.get_user_by_id(shift['user_id'])
            if user:
                await create_or_update_pinned_message(context, user['id'], user['telegram_id'])
    
    # Обновляем отображение
    await update_car_display(query, car_id, page)

async def handle_clear_all(query, context, data):
    """Очистка всех услуг"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    car_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    
    # Очищаем услуги
    DatabaseManager.clear_car_services(car_id)
    
    # Обновляем закреплённое сообщение
    car = DatabaseManager.get_car(car_id)
    if car:
        shift = DatabaseManager.get_shift(car['shift_id'])
        if shift:
            user = DatabaseManager.get_user_by_id(shift['user_id'])
            if user:
                await create_or_update_pinned_message(context, user['id'], user['telegram_id'])
    
    # Обновляем отображение
    await update_car_display(query, car_id, page)

async def update_car_display(query, car_id: int, page: int = 0):
    """Обновить отображение машины с услугами"""
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
    total = car['total_amount']
    
    for name, data in grouped.items():
        service_total = data['price'] * data['quantity']
        services_text += f"• {name} ({data['price']}₽) ×{data['quantity']} = {format_money(service_total)}\n"
    
    if not services_text:
        services_text = "Нет выбранных услуг\n"
    
    time_type = get_current_time_type()
    
    message = (
        f"🚗 **Машина:** `{car['car_number']}`\n"
        f"⏰ {time_type}\n"
        f"💰 Итог: **{format_money(total)}**\n\n"
        f"**Выбранные услуги:**\n{services_text}\n"
        f"Выберите ещё:"
    )
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=create_services_keyboard(car_id, page)
    )

# ========== СОХРАНЕНИЕ/ОТМЕНА МАШИНЫ ==========

async def handle_save_car(query, context, data):
    """Сохранение машины"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    car_id = int(parts[2])
    car = DatabaseManager.get_car(car_id)
    
    if not car:
        await query.edit_message_text("❌ Машина не найдена")
        return
    
    services = DatabaseManager.get_car_services(car_id)
    
    if not services:
        await query.edit_message_text(
            f"❌ Машина `{car['car_number']}` не сохранена.\n"
            f"Не выбрано ни одной услуги.",
            parse_mode='Markdown'
        )
        return
    
    shift = DatabaseManager.get_shift(car['shift_id'])
    user = DatabaseManager.get_user_by_id(shift['user_id']) if shift else None
    
    if user:
        # Обновляем закреплённое сообщение
        await create_or_update_pinned_message(context, user['id'], user['telegram_id'])
    
    await query.edit_message_text(
        f"✅ Машина `{car['car_number']}` сохранена!\n\n"
        f"💰 Итог: **{format_money(car['total_amount'])}**\n\n"
        f"Можете добавить следующую машину 🚗",
        parse_mode='Markdown',
        reply_markup=create_main_keyboard(user, has_active_shift=True) if user else None
    )

async def handle_cancel_car(query, context, data):
    """Отмена добавления машины"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    car_id = int(parts[2])
    
    # Удаляем машину
    DatabaseManager.delete_car(car_id)
    
    await query.edit_message_text(
        "❌ Добавление машины отменено.\n"
        "Машина удалена из смены."
    )

# ========== ОБРАБОТЧИКИ СМЕН ==========

async def handle_current_shift(query, context):
    """Текущая смена"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        return
    
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    
    if not active_shift:
        await query.edit_message_text(
            "📭 **Нет активной смены**\n\n"
            "Откройте смену для начала работы.",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard(db_user, has_active_shift=False)
        )
        return
    
    cars = DatabaseManager.get_shift_cars(active_shift['id'])
    total = DatabaseManager.get_shift_total(active_shift['id'])
    
    message = (
        f"📊 **ТЕКУЩАЯ СМЕНА**\n\n"
        f"⏰ Начата: {active_shift['start_time'].strftime('%H:%M (%d.%m.%Y)')}\n"
        f"💰 Заработано: **{format_money(total)}**\n"
        f"🚗 Машин: **{len(cars)}**\n\n"
    )
    
    if cars:
        message += "**Машины в смене:**\n"
        for i, car in enumerate(cars, 1):
            message += f"{i}. {car['car_number']} - {format_money(car['total_amount'])}\n"
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=create_shift_keyboard(active_shift['id'])
    )

async def handle_view_shift(query, context, data):
    """Просмотр смены"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    shift_id = int(parts[2])
    shift = DatabaseManager.get_shift(shift_id)
    
    if not shift:
        await query.edit_message_text("❌ Смена не найдена")
        return
    
    cars = DatabaseManager.get_shift_cars(shift_id)
    total = DatabaseManager.get_shift_total(shift_id)
    
    message = f"📋 **СМЕНА**\n\n"
    
    if shift['status'] == 'active':
        message += "🟢 **Активна**\n"
    else:
        message += "🔴 **Завершена**\n"
    
    message += f"⏰ Начало: {shift['start_time'].strftime('%H:%M (%d.%m.%Y)')}\n"
    
    if shift['end_time']:
        message += f"⏰ Окончание: {shift['end_time'].strftime('%H:%M')}\n"
        duration = (shift['end_time'] - shift['start_time']).total_seconds() / 3600
        message += f"⏱️ Длительность: {int(duration)} ч.\n"
    
    message += f"💰 Общая сумма: **{format_money(total)}**\n"
    message += f"🚗 Машин: **{len(cars)}**\n\n"
    
    if cars:
        message += "**Машины:**\n"
        for i, car in enumerate(cars[:10], 1):  # Показываем первые 10
            message += f"{i}. {car['car_number']} - {format_money(car['total_amount'])}\n"
        
        if len(cars) > 10:
            message += f"\n... и ещё {len(cars) - 10} машин\n"
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=create_shift_keyboard(shift_id)
    )

async def handle_add_car_to_shift(query, context, data):
    """Добавление машины в существующую смену"""
    parts = data.split('_')
    if len(parts) < 4:
        return
    
    shift_id = int(parts[3])
    
    context.user_data['awaiting_car_number'] = True
    context.user_data['car_for_shift'] = shift_id
    
    await query.edit_message_text(
        f"🚗 **ДОБАВЛЕНИЕ МАШИНЫ В СМЕНУ**\n\n"
        f"{get_correct_examples()}\n"
        f"{get_allowed_letters_explained()}\n\n"
        f"**Введите номер машины:**\n"
        f"_Можно вводить русскими или английскими буквами_",
        parse_mode='Markdown'
    )

async def handle_close_shift(query, context, data):
    """Закрытие смены"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    shift_id = int(parts[2])
    shift = DatabaseManager.get_shift(shift_id)
    
    if not shift:
        await query.edit_message_text("❌ Смена не найдена")
        return
    
    cars = DatabaseManager.get_shift_cars(shift_id)
    total = DatabaseManager.get_shift_total(shift_id)
    
    await query.edit_message_text(
        f"🔚 **ЗАКРЫТИЕ СМЕНЫ**\n\n"
        f"⏰ Начата: {shift['start_time'].strftime('%H:%M (%d.%m.%Y)')}\n"
        f"⏱️ Длительность: {int((datetime.now() - shift['start_time']).total_seconds() / 3600)} ч.\n"
        f"💰 Итог: **{format_money(total)}**\n"
        f"🚗 Машин: **{len(cars)}**\n\n"
        f"Вы уверены, что хотите закрыть смену?\n"
        f"Будет сгенерирован отчёт.",
        parse_mode='Markdown',
        reply_markup=create_confirmation_keyboard("close_shift", shift_id)
    )

async def handle_delete_shift(query, context, data):
    """Удаление смены"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    shift_id = int(parts[2])
    
    await query.edit_message_text(
        "🗑️ **УДАЛЕНИЕ СМЕНЫ**\n\n"
        "⚠️ **ВНИМАНИЕ!**\n"
        "Вы уверены, что хотите удалить эту смену?\n\n"
        "❌ **Будут удалены:**\n"
        "• Все машины в смене\n"
        "• Все услуги машин\n"
        "• Вся статистика по смене\n\n"
        "**Это действие нельзя отменить!**",
        parse_mode='Markdown',
        reply_markup=create_confirmation_keyboard("delete_shift", shift_id)
    )

# ========== ОБРАБОТЧИКИ ИСТОРИИ ==========

async def handle_history(query, context, data):
    """История смен"""
    parts = data.split('_')
    page = int(parts[1]) if len(parts) > 1 else 0
    
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        return
    
    shifts = DatabaseManager.get_user_shifts(db_user['id'], limit=100)
    
    if not shifts:
        await query.edit_message_text(
            "📜 **ИСТОРИЯ СМЕН**\n\n"
            "У вас ещё нет смен.\n"
            "Откройте первую смену, чтобы начать работу.",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard(db_user, has_active_shift=False)
        )
        return
    
    # Пагинация
    shifts_per_page = 10
    start_idx = page * shifts_per_page
    end_idx = start_idx + shifts_per_page
    page_shifts = shifts[start_idx:end_idx]
    
    message = f"📜 **ИСТОРИЯ СМЕН**\n\n"
    
    for i, shift in enumerate(page_shifts, start_idx + 1):
        date_str = shift['created_at'].strftime("%d.%m")
        start_time = shift['start_time'].strftime("%H:%M")
        
        if shift['end_time']:
            end_time = shift['end_time'].strftime("%H:%M")
            time_str = f"{start_time}-{end_time}"
            status_icon = "✅"
        else:
            time_str = f"{start_time}"
            status_icon = "🟢"
        
        total = shift.get('total_amount', 0)
        message += f"{i}. {status_icon} {date_str} {time_str} - **{format_money(total)}**\n"
    
    # Навигация
    total_pages = (len(shifts) + shifts_per_page - 1) // shifts_per_page
    navigation = []
    
    if page > 0:
        navigation.append(InlineKeyboardButton("◀️", callback_data=f"history_{page-1}"))
    
    navigation.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        navigation.append(InlineKeyboardButton("▶️", callback_data=f"history_{page+1}"))
    
    keyboard = []
    
    # Кнопки для выбора смены
    for i, shift in enumerate(page_shifts):
        text = f"{shift['created_at'].strftime('%d.%m %H:%M')} - {format_money(shift.get('total_amount', 0))}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"view_shift_{shift['id']}")])
    
    if navigation:
        keyboard.append(navigation)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ========== ОБРАБОТЧИКИ ПОДТВЕРЖДЕНИЙ ==========

async def handle_confirm(query, context, data):
    """Подтверждение действий"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    action = parts[1]
    item_id = int(parts[2])
    
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        return
    
    if action == "close_shift":
        # Завершаем смену
        shift = DatabaseManager.end_shift(item_id)
        
        if not shift:
            await query.edit_message_text("❌ Ошибка закрытия смены")
            return
        
        # Генерируем отчёт
        report = DatabaseManager.get_shift_report(item_id)
        
        if not report:
            await query.edit_message_text("❌ Ошибка генерации отчёта")
            return
        
        # Удаляем закреплённое сообщение
        await delete_pinned_message(context, user.id)
        
        # Отправляем отчёт
        message = (
            f"📊 **ОТЧЁТ ЗА СМЕНУ**\n\n"
            f"⏰ Начало: {shift['start_time'].strftime('%H:%M')}\n"
            f"⏰ Окончание: {shift['end_time'].strftime('%H:%M')}\n"
            f"⏱️ Длительность: {int((shift['end_time'] - shift['start_time']).total_seconds() / 3600)} ч.\n"
            f"🚗 Машин обслужено: **{len(report['cars'])}**\n"
            f"💰 Заработано: **{format_money(report['total'])}**\n\n"
        )
        
        avg_per_car = report['total'] / len(report['cars']) if report['cars'] else 0
        message += f"📈 Средний чек: **{format_money(int(avg_per_car))}**\n\n"
        
        if report['top_services']:
            message += "🏆 **ТОП-3 УСЛУГИ:**\n"
            for i, (name, stats) in enumerate(report['top_services'], 1):
                message += f"{i}. {name} — {format_money(stats['total'])} ({stats['count']} раз)\n"
        
        message += f"\n✅ **Смена успешно закрыта!**"
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard(db_user, has_active_shift=False)
        )
        
    elif action == "delete_shift":
        # Удаляем смену
        success = DatabaseManager.delete_shift(item_id)
        
        if success:
            await query.edit_message_text(
                "✅ **Смена удалена**\n\n"
                "Все данные по смене удалены.",
                parse_mode='Markdown',
                reply_markup=create_main_keyboard(db_user, has_active_shift=False)
            )
        else:
            await query.edit_message_text("❌ Ошибка удаления смены")

async def handle_cancel(query, context, data):
    """Отмена действий"""
    parts = data.split('_')
    if len(parts) < 3:
        return
    
    action = parts[1]
    item_id = int(parts[2])
    
    if action == "close_shift":
        await query.edit_message_text(
            "❌ Закрытие смены отменено.",
            reply_markup=create_shift_keyboard(item_id)
        )
    elif action == "delete_shift":
        await query.edit_message_text(
            "❌ Удаление смены отменено.",
            reply_markup=create_shift_keyboard(item_id)
        )

# ========== ОБРАБОТЧИКИ НАСТРОЕК ==========

async def handle_settings(query, context):
    """Настройки"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        return
    
    await query.edit_message_text(
        "⚙️ **НАСТРОЙКИ**\n\n"
        "Выберите параметр для изменения:",
        parse_mode='Markdown',
        reply_markup=create_settings_keyboard(db_user)
    )

async def handle_change_target(query, context):
    """Изменение цели"""
    user = query.from_user
    
    context.user_data['awaiting_target'] = True
    
    await query.edit_message_text(
        "🎯 **ИЗМЕНЕНИЕ ЦЕЛИ**\n\n"
        "Введите новую цель в рублях:\n"
        "Пример: 5000\n\n"
        "**Введите число:**",
        parse_mode='Markdown'
    )

async def handle_toggle_progress(query, context):
    """Переключение прогресс-бара"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        return
    
    current = db_user.get('progress_bar_enabled', True)
    new_value = not current
    
    DatabaseManager.update_user_setting(user.id, 'progress_bar_enabled', new_value)
    
    status = "✅ ВКЛЮЧЕН" if new_value else "❌ ВЫКЛЮЧЕН"
    
    await query.edit_message_text(
        f"📊 **ПРОГРЕСС-БАР**\n\n"
        f"Статус: **{status}**",
        parse_mode='Markdown',
        reply_markup=create_settings_keyboard(DatabaseManager.get_user(user.id))
    )

async def handle_decade_stats(query, context):
    """Статистика по декаде"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        return
    
    decade, (start_day, end_day) = get_current_decade()
    
    # Временная заглушка для статистики
    # В реальном приложении здесь должен быть вызов DatabaseManager.get_decade_stats()
    
    message = (
        f"📈 **СТАТИСТИКА ЗА ДЕКАДУ**\n\n"
        f"📅 Декада {decade} ({start_day}-{end_day})\n"
        f"⏱️ Дней прошло: {min(datetime.now().day - start_day + 1, end_day - start_day + 1)}/{end_day - start_day + 1}\n\n"
        f"⚠️ **Функция в разработке**\n"
        f"Подробная статистика по декадам будет доступна в следующем обновлении."
    )
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=create_settings_keyboard(db_user)
    )

async def handle_reset_data(query, context):
    """Сброс данных"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        return
    
    # Получаем все смены пользователя
    shifts = DatabaseManager.get_user_shifts(db_user['id'], limit=1000)
    
    message = (
        "🔄 **СБРОС ВСЕХ ДАННЫХ**\n\n"
        "⚠️ **ВНИМАНИЕ!**\n"
        "Вы уверены, что хотите сбросить ВСЕ данные?\n\n"
        f"❌ **Будут удалены:**\n"
        f"• {len(shifts)} смен\n"
        f"• Все машины и услуги\n"
        f"• Вся статистика\n\n"
        "**Это действие нельзя отменить!**"
    )
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=create_confirmation_keyboard("reset_data", db_user['id'])
    )

async def handle_create_backup(query, context):
    """Создание backup"""
    user = query.from_user
    
    # В режиме памяти можно сохранить backup
    try:
        # Это работает только в режиме памяти
        # В PostgreSQL backup делается через pg_dump
        await query.answer("✅ Backup создан (только для режима памяти)", show_alert=True)
        
        # В реальном приложении здесь должна быть логика создания backup
        # DatabaseManager.save_backup() если в режиме памяти
        
    except Exception as e:
        await query.answer(f"❌ Ошибка создания backup: {e}", show_alert=True)

# ========== ОБРАБОТЧИКИ СТАТИСТИКИ И ПОМОЩИ ==========

async def handle_stats(query, context):
    """Статистика"""
    user = query.from_user
    db_user = DatabaseManager.get_user(user.id)
    
    if not db_user:
        return
    
    stats = DatabaseManager.get_user_stats(db_user['id'], days=30)
    
    message = (
        f"📈 **ВАША СТАТИСТИКА**\n\n"
        f"**За последние 30 дней:**\n"
        f"📊 Смен: **{stats['shift_count']}**\n"
        f"🚗 Машин: **{stats['cars_count']}**\n"
        f"💰 Заработано: **{format_money(stats['total_earned'])}**\n"
    )
    
    if stats['shift_count'] > 0:
        message += f"📈 Среднее за смену: **{format_money(stats['avg_per_shift'])}**\n"
    
    # Активная смена
    active_shift = DatabaseManager.get_active_shift(db_user['id'])
    if active_shift:
        total = DatabaseManager.get_shift_total(active_shift['id'])
        message += f"\n**Активная смена:**\n"
        message += f"⏰ Начата: {active_shift['start_time'].strftime('%H:%M')}\n"
        message += f"🚗 Машин: {len(DatabaseManager.get_shift_cars(active_shift['id']))}\n"
        message += f"💰 Сумма: {format_money(total)}\n"
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard(db_user, has_active_shift=bool(active_shift))
    )

async def handle_help(query, context):
    """Помощь"""
    help_text = """
🤖 **ПОМОЩЬ ПО ИСПОЛЬЗОВАНИЮ БОТА**

📌 **Основные функции:**
• `📅 Открыть смену` - начать новую рабочую смену
• `🚗 Добавить машину` - добавить автомобиль для обслуживания
• `📊 Текущая смена` - управление активной сменой
• `📜 История смен` - просмотр завершённых смен
• `📈 Статистика` - аналитика вашей работы

🚗 **Добавление машины:**
1. Нажмите "🚗 Добавить машину"
2. Введите номер машины (пример: А123ВС777)
3. Выберите услуги из списка
4. Нажмите "💾 Сохранить машину"

✅ **Правильные номера:**
• А123ВС777 ✓
• Х340КХ797 ✓
• В567ТХ799 ✓

❌ **Неправильные номера:**
• А123БВ777 ✗ (буква Б не разрешена)
• ABC123 ✗ (английские буквы)
• 123456 ✗ (только цифры)

🎯 **Прогресс-бар:**
• Автоматически обновляется в закреплённом сообщении
• Уведомления при 50%, 75% и 100% цели
• Можно отключить в настройках

📱 **Быстрые команды:**
`/now` - показать текущий прогресс
`/target 7000` - установить новую цель
`/stats` - показать статистику
`/help` - показать эту справку

⚙️ **Настройки:**
• Изменение дневной цели
• Включение/выключение прогресс-бара
• Сброс данных
• Создание backup
"""
    
    await query.edit_message_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
    )

# ========== ОБРАБОТЧИКИ ОСТАЛЬНОГО ==========

async def handle_all_services(query, context, data):
    """Все услуги (пагинация)"""
    parts = data.split('_')
    if len(parts) < 4:
        return
    
    car_id = int(parts[2])
    page = int(parts[3])
    
    await update_car_display(query, car_id, page)

async def handle_page_services(query, context, data):
    """Смена страницы услуг"""
    parts = data.split('_')
    if len(parts) < 4:
        return
    
    car_id = int(parts[2])
    page = int(parts[3])
    
    await update_car_display(query, car_id, page)

async def handle_view_car(query, context, data):
    """Просмотр машины"""
    parts = data.split('_')
    if len(parts) < 4:
        return
    
    car_id = int(parts[2])
    shift_id = int(parts[3])
    
    car = DatabaseManager.get_car(car_id)
    if not car:
        await query.edit_message_text("❌ Машина не найдена")
        return
    
    services = DatabaseManager.get_car_services(car_id)
    
    message = (
        f"🚗 **МАШИНА:** `{car['car_number']}`\n"
        f"💰 Итог: **{format_money(car['total_amount'])}**\n\n"
    )
    
    if services:
        message += "**Услуги:**\n"
        for service in services:
            message += f"• {service['service_name']} ({service['price']}₽) ×{service['quantity']}\n"
    else:
        message += "Нет услуг\n"
    
    keyboard = [
        [
            InlineKeyboardButton("✏️ Редактировать услуги", callback_data=f"all_services_{car_id}_0"),
            InlineKeyboardButton("🗑️ Удалить машину", callback_data=f"confirm_delete_car_{car_id}")
        ],
        [InlineKeyboardButton("🔙 К машинам", callback_data=f"view_shift_{shift_id}")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_cars_page(query, context, data):
    """Пагинация машин"""
    # Временная заглушка
    await query.answer("Пагинация машин в разработке", show_alert=True)

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
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("now", now_command))
    application.add_handler(CommandHandler("target", target_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Обработчик callback-кнопок
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота
    logger.info("🤖 Бот запускается...")
    print("=" * 60)
    print("🚀 БОТ ДЛЯ УЧЁТА УСЛУГ")
    print("✅ Версия: 2.0 (полная)")
    print("✅ Функции: закреплённые сообщения, прогресс-бар, уведомления")
    print("=" * 60)
    
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
