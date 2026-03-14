import os
from pathlib import Path
BOT_TOKEN = os.getenv("SERVICEBOT_TOKEN", "")

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_TEMPLATE_PATH = BASE_DIR / "ui" / "assets" / "dashboard" / "dashboard_template_v2.png"

# Дефолтный регион для автодополнения номеров
DEFAULT_REGION = "797"

# Соответствие английских букв русским
ENG_TO_RUS = {
    "A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н",
    "K": "К", "M": "М", "O": "О", "P": "Р", "T": "Т",
    "X": "Х", "Y": "У",
}

RUS_LETTERS = "АВЕКМНОРСТУХ"

# Обратное соответствие (русские → английские, для отладки)
RUS_TO_ENG = {rus: eng for eng, rus in ENG_TO_RUS.items()}


# Разрешенные буквы для использования в номерах
ALLOWED_LETTERS = RUS_LETTERS  # Просто ссылаемся на RUS_LETTERS

# ========== ПРАЙС-ЛИСТ ==========

SERVICES = {
    1: {"name": "✅ Проверка", "day_price": 115, "night_price": 92, "priority": 1, "order": 1},
    2: {"name": "⛽ Заправка ТС", "day_price": 198, "night_price": 158, "priority": 1, "order": 2},
    3: {"name": "🧴 Заливка омывайки", "day_price": 66, "night_price": 55, "priority": 1, "order": 3},
    4: {"name": "🚗 Перегон ТС на ТО", "day_price": 254, "night_price": 203, "priority": 1, "order": 4},
    5: {"name": "📡 Нет спутника", "day_price": 398, "night_price": 315, "priority": 1, "order": 5},
    6: {"name": "⚡ Срочный выезд", "day_price": 220, "night_price": 174, "priority": 1, "order": 6},
    7: {"name": "🔋 Зарядка АКБ", "day_price": 125, "night_price": 98, "priority": 2, "order": 1},
    8: {"name": "🏁 Завершение длит. аренд", "day_price": 93, "night_price": 74, "priority": 2, "order": 2},
    9: {"name": "🧪 Долив тех. жидкостей", "day_price": 77, "night_price": 66, "priority": 2, "order": 3},
   10: {"name": "🛣️ Дальняк", "day_price": 0, "night_price": 0, "priority": 2, "order": 4, "kind": "distance", "rate_per_km": 7},
    11: {"name": "🚙 Длительные поездки (список)", "priority": 2, "order": 5, "kind": "group", "children": [30, 31, 32, 33]},
    12: {"name": "🧾 Диагностика Чек", "day_price": 50, "night_price": 39, "priority": 3, "order": 1},
    13: {"name": "🛞 Подкачка колеса", "day_price": 75, "night_price": 59, "priority": 3, "order": 2},
    14: {"name": "🅿️ Перепарковка ТС", "day_price": 150, "night_price": 118, "priority": 3, "order": 3},
    15: {"name": "🧰 Проверка ходовой", "day_price": 115, "night_price": 92, "priority": 3, "order": 4},
    16: {"name": "🚫 Холостой выезд", "day_price": 64, "night_price": 55, "priority": 3, "order": 5},
    17: {"name": "🔩 Протяжка колесных болтов", "day_price": 92, "night_price": 74, "priority": 3, "order": 6},
    18: {"name": "🧱 Сугроб простой", "day_price": 160, "night_price": 126, "priority": 4, "order": 1},
    19: {"name": "🧊 Сугроб сложный", "day_price": 902, "night_price": 686, "priority": 4, "order": 2},
    20: {"name": "📄 Вложение документов", "day_price": 31, "night_price": 25, "priority": 4, "order": 3},
    21: {"name": "⚙️ Нестандартная операция", "day_price": 83, "night_price": 64, "priority": 4, "order": 4},
    22: {"name": "💡 Замена лампочки", "day_price": 31, "night_price": 25, "priority": 4, "order": 5},
    23: {"name": "🪪 Закрепление ГРЗ", "day_price": 31, "night_price": 25, "priority": 4, "order": 6},
    24: {"name": "🔌 Перезагрузка оборудования", "day_price": 101, "night_price": 79, "priority": 4, "order": 7},
    25: {"name": "🧹 Установка дворника", "day_price": 31, "night_price": 25, "priority": 4, "order": 8},
    26: {"name": "🪞 Установка зеркала", "day_price": 74, "night_price": 59, "priority": 4, "order": 9},
    27: {"name": "💧 Установка форсунки омывателя", "day_price": 74, "night_price": 59, "priority": 4, "order": 10},
    28: {"name": "🧢 Установка колпака (1 шт)", "day_price": 27, "night_price": 22, "priority": 4, "order": 11},
    29: {"name": "🛠️ Замена предохранителей", "day_price": 75, "night_price": 59, "priority": 4, "order": 12},
    30: {"name": "⏱️ Длительные поездки до 1 часа", "day_price": 149, "night_price": 118, "hidden": True},
    31: {"name": "⏱️ Длительные поездки до 3 часов", "day_price": 648, "night_price": 511, "hidden": True},
    32: {"name": "⏱️ Длительные поездки до 5 часов", "day_price": 1146, "night_price": 905, "hidden": True},
    33: {"name": "⏱️ Длительные поездки до 10 часов", "day_price": 2243, "night_price": 1770, "hidden": True},
    34: {"name": "👨‍🔧 Развоз механиков (список)", "priority": 4, "order": 13, "kind": "group", "children": [35, 36, 37, 38]},
    35: {"name": "🚐 Развоз до 3 часов", "day_price": 373, "night_price": 295, "hidden": True},
    36: {"name": "🚐 Развоз до 5 часов", "day_price": 747, "night_price": 590, "hidden": True},
    37: {"name": "🚐 Развоз до 7 часов", "day_price": 1495, "night_price": 1180, "hidden": True},
    38: {"name": "🚐 Развоз от 7 часов", "day_price": 2243, "night_price": 1770, "hidden": True},
    39: {"name": "🚚 Перемещение ТС (список)", "priority": 4, "order": 14, "kind": "group", "children": [40, 41, 42, 43, 44]},
    40: {"name": "🚚 С территории СТО", "day_price": 31, "night_price": 25, "hidden": True},
    41: {"name": "🚚 Перемещение ТС до 20 км", "day_price": 320, "night_price": 252, "hidden": True},
    42: {"name": "🚚 Перемещение ТС от 20 до 26 км", "day_price": 543, "night_price": 429, "hidden": True},
    43: {"name": "🚚 Перемещение ТС от 26 до 32 км", "day_price": 725, "night_price": 572, "hidden": True},
    44: {"name": "🚚 Перемещение ТС от 32 км", "day_price": 911, "night_price": 720, "hidden": True},
    45: {"name": "🧾 Заправка из канистры", "day_price": 278, "night_price": 278, "priority": 4, "order": 15},
    46: {"name": "🧾 Заправка из канистры (срочно)", "day_price": 333, "night_price": 332, "priority": 4, "order": 16},
    47: {"name": "🔧 Удалённая заправка", "day_price": 545, "night_price": 433, "priority": 4, "order": 17},
}

# ========== ФУНКЦИИ НОРМАЛИЗАЦИИ ==========

def normalize_car_number(text: str) -> str:
    """
    Нормализация номера машины по стандарту РФ

    Примеры преобразования:
    - 'x340py' → 'Х340РУ'
    - 'х340ру' → 'Х340РУ'
    - 'H340PY797' → 'Н340РУ797'
    - 'а123вс' → 'А123ВС'
    - 'b567tx' → 'В567ТХ'
    """
    if not text:
        return ""

    text = text.strip().upper()
    text = text.replace(' ', '').replace('-', '').replace('_', '')

    result = []
    for char in text:
        if char in ENG_TO_RUS:
            result.append(ENG_TO_RUS[char])
        else:
            result.append(char)

    normalized = ''.join(result)
    allowed_chars = RUS_LETTERS + '0123456789'
    normalized = ''.join([c for c in normalized if c in allowed_chars])
    return normalized


def validate_car_number(text: str) -> tuple[bool, str, str]:
    """Проверка и нормализация номера машины."""
    if not text:
        return False, "", "Введите номер машины"

    import re

    normalized = normalize_car_number(text)
    if len(normalized) < 6:
        return False, normalized, f"Номер слишком короткий: {normalized}"

    pattern_full = f'^[{RUS_LETTERS}]\d{{3}}[{RUS_LETTERS}]{{2}}\d{{3}}$'
    pattern_short = f'^[{RUS_LETTERS}]\d{{3}}[{RUS_LETTERS}]{{2}}$'

    if re.match(pattern_short, normalized):
        return True, normalized + DEFAULT_REGION, ""
    if re.match(pattern_full, normalized):
        return True, normalized, ""

    # Свободный формат (например, ХРУ340 или 340ХРУ)
    compact_letters = ''.join(ch for ch in normalized if ch in RUS_LETTERS)
    compact_digits = ''.join(ch for ch in normalized if ch.isdigit())
    if len(compact_letters) >= 3 and len(compact_digits) >= 3:
        rebuilt = compact_letters[0] + compact_digits[:3] + compact_letters[1:3]
        rebuilt += compact_digits[3:6] if len(compact_digits) >= 6 else DEFAULT_REGION
        if re.match(pattern_full, rebuilt):
            return True, rebuilt, ""

    return False, normalized, "Неверный формат. Пример: А123ВС777"


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
    
    text = "✅ **ПРИМЕРЫ ПРАВИЛЬНЫХ НОМЕРОВ:**\n\n"
    
    text += "📱 **Что можно вводить (бот преобразует):**\n"
    for input_ex, output in input_examples:
        text += f"• `{input_ex}` {output}\n"
    
    text += "\n🎯 **Финальный формат в базе:**\n"
    for i, example in enumerate(examples[:5]):
        text += f"• {example}\n"
    
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

# ========== ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ==========

if __name__ == "__main__":
    # Тестирование функции нормализации
    test_cases = [
        "x340py",
        "х340ру",
        "H340PY797",
        "а123вс",
        "b567tx",
        "e234km",
        "X340PY",
        "h340py",
        "y123ab",
        "А123ВС777",
        "Х340РУ",
        "В567 ТХ-799",  # С пробелом и дефисом
        "о234 ср 797",  # С пробелами
    ]
    
    print("🧪 Тестирование нормализации номеров:")
    print("=" * 50)
    
    for test in test_cases:
        normalized = normalize_car_number(test)
        is_valid, final_number, error = validate_car_number(test)
        
        print(f"Ввод: '{test}'")
        print(f"  Нормализовано: {normalized}")
        print(f"  Валидность: {'✅' if is_valid else '❌'}")
        print(f"  Финальный номер: {final_number}")
        if error:
            print(f"  Ошибка: {error}")
        print()
