BOT_TOKEN = "8353243831:AAG_F9d203LLJsRn2VCn2Iocw99jZc0JHTY"

# Разрешенные буквы для номеров (ТОЛЬКО РУССКИЕ!)
ALLOWED_LETTERS = "АВЕКМНОРСТУХ"

# Прайс-лист услуг (день/ночь)
SERVICES = {
    1: {"name": "✅ Проверка", "day_price": 100, "night_price": 150, "frequent": True},
    2: {"name": "⛽ Заправка", "day_price": 200, "night_price": 300, "frequent": True},
    3: {"name": "🌀 Подкачка", "day_price": 50, "night_price": 80, "frequent": True},
    4: {"name": "🔧 Прокрутка", "day_price": 150, "night_price": 200, "frequent": True},
    5: {"name": "🧽 Мойка", "day_price": 400, "night_price": 500, "frequent": True},
    6: {"name": "🔋 АКБ", "day_price": 250, "night_price": 350, "frequent": True},
    7: {"name": "🛢️ Замена масла", "day_price": 450, "night_price": 550, "frequent": False},
    8: {"name": "🔍 Диагностика", "day_price": 600, "night_price": 700, "frequent": False},
    9: {"name": "🛞 Шиномонтаж", "day_price": 800, "night_price": 900, "frequent": False},
    10: {"name": "🔨 Ремонт", "day_price": 1000, "night_price": 1200, "frequent": False},
    11: {"name": "❄️ Кондиционер", "day_price": 700, "night_price": 850, "frequent": False},
    12: {"name": "🌫️ Замена фильтра", "day_price": 300, "night_price": 400, "frequent": False},
}
