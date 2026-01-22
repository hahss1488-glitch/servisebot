"""
ПРОСТОЙ РАБОЧИЙ БОТ ДЛЯ УЧЁТА УСЛУГ
"""

import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# ========== НАСТРОЙКИ ==========
# ЗАМЕНИТЕ ЭТОТ ТОКЕН НА СВОЙ!
BOT_TOKEN = "ВАШ_НОВЫЙ_ТОКЕН_ЗДЕСЬ"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== КОМАНДЫ БОТА ==========

async def start(update: Update, context: CallbackContext):
    """Команда /start - приветствие"""
    user = update.effective_user
    
    # Создаём клавиатуру с кнопками
    keyboard = [
        ["🚗 Добавить машину"],
        ["📊 Мой прогресс"],
        ["⚙️ Настройки", "❓ Помощь"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"🎉 <b>Добро пожаловать, {user.first_name}!</b>\n\n"
        f"Я помогу вам вести учёт услуг на работе.\n\n"
        f"<b>Что я умею:</b>\n"
        f"• Записывать выполненные услуги\n"
        f"• Считать заработок за смену\n"
        f"• Показывать прогресс\n"
        f"• Формировать отчёты\n\n"
        f"<i>Используйте кнопки ниже ↓</i>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    logger.info(f"Пользователь {user.id} запустил бота")

async def handle_add_car(update: Update, context: CallbackContext):
    """Обработка кнопки 'Добавить машину'"""
    await update.message.reply_text(
        "🚗 <b>Добавление машины</b>\n\n"
        "Отправьте номер машины:\n"
        "<code>Например: А123БВ777 или Х340РУ797</code>\n\n"
        "После этого вы сможете выбрать услуги.",
        parse_mode='HTML'
    )

async def handle_car_number(update: Update, context: CallbackContext):
    """Обработка номера машины"""
    car_number = update.message.text.upper().strip()
    
    if len(car_number) < 5:
        await update.message.reply_text("❌ Номер слишком короткий!")
        return
    
    # Сохраняем номер
    context.user_data['current_car'] = car_number
    
    await update.message.reply_text(
        f"✅ <b>Машина {car_number} добавлена!</b>\n\n"
        f"Скоро здесь появятся кнопки для выбора услуг:\n"
        f"• Проверка\n"
        f"• Заправка\n"
        f"• Подкачка колёс\n"
        f"• И другие услуги\n\n"
        f"<i>Эта функция в разработке...</i>",
        parse_mode='HTML'
    )

async def handle_progress(update: Update, context: CallbackContext):
    """Обработка кнопки 'Мой прогресс'"""
    await update.message.reply_text(
        "📊 <b>Ваш прогресс</b>\n\n"
        "Сегодня: <b>0₽</b> (смена не начата)\n"
        "Цель: <b>5 000₽</b>\n"
        "Прогресс: [░░░░░░░░░░] 0%\n\n"
        "<i>Начните смену в настройках</i>",
        parse_mode='HTML'
    )

async def handle_settings(update: Update, context: CallbackContext):
    """Обработка кнопки 'Настройки'"""
    await update.message.reply_text(
        "⚙️ <b>Настройки</b>\n\n"
        "1. Установить цель на смену\n"
        "2. Начать смену\n"
        "3. Изменить имя\n\n"
        "<i>Скоро будут доступны</i>",
        parse_mode='HTML'
    )

async def handle_help(update: Update, context: CallbackContext):
    """Обработка кнопки 'Помощь'"""
    await update.message.reply_text(
        "❓ <b>Помощь</b>\n\n"
        "<b>Как пользоваться:</b>\n"
        "1. Нажмите '🚗 Добавить машину'\n"
        "2. Введите номер машины\n"
        "3. Выберите услуги (скоро)\n"
        "4. Смотрите прогресс\n\n"
        "<b>Команды:</b>\n"
        "/start - перезапустить бота\n"
        "/test - проверить работу\n\n"
        "<i>Бот в активной разработке</i>",
        parse_mode='HTML'
    )

async def test_command(update: Update, context: CallbackContext):
    """Команда /test"""
    await update.message.reply_text("✅ Бот работает! Все системы в норме.")

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========

def main():
    """Запуск бота"""
    logger.info("=" * 50)
    logger.info("ЗАПУСК БОТА ДЛЯ УЧЁТА УСЛУГ")
    logger.info("=" * 50)
    
    # Проверяем токен
    if BOT_TOKEN.startswith("ВАШ_НОВЫЙ_ТОКЕН"):
        print("❌ ОШИБКА: Замените BOT_TOKEN в коде на свой токен!")
        print("1. Получите токен у @BotFather")
        print("2. Вставьте его в файл bot.py")
        return
    
    try:
        # Создаём приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Регистрируем команды
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("test", test_command))
        
        # Регистрируем обработчики кнопок
        application.add_handler(MessageHandler(filters.Regex(r'^🚗 Добавить машину$'), handle_add_car))
        application.add_handler(MessageHandler(filters.Regex(r'^📊 Мой прогресс$'), handle_progress))
        application.add_handler(MessageHandler(filters.Regex(r'^⚙️ Настройки$'), handle_settings))
        application.add_handler(MessageHandler(filters.Regex(r'^❓ Помощь$'), handle_help))
        
        # Обработчик номеров машин (любой текст после нажатия "Добавить машину")
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^🚗|📊|⚙️|❓'),
            handle_car_number
        ))
        
        # Запускаем бота
        logger.info("Бот запускается...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        print("❌ Бот не запустился. Проверьте:")
        print("1. Правильный ли токен?")
        print("2. Есть ли интернет соединение?")
        print("3. Не запущен ли другой бот с таким же токеном?")

if __name__ == '__main__':
    main()
