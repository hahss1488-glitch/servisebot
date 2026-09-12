import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("SERVICEBOT_TOKEN", "")

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_TEMPLATE_PATH = BASE_DIR / "ui" / "assets" / "dashboard" / "dashboard_template_v2.png"
LEADERBOARD_TEMPLATE_PATH = BASE_DIR / "ui" / "assets" / "leaderboard" / "leaderboard_template_v2.png"


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
    11: {"name": "🛣️ Дальняя поездка", "priority": 2, "order": 4, "kind": "group", "children": [30, 31, 32, 33]},
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
    28: {"name": "🧢 Установка колпаков", "day_price": 93, "night_price": 83, "priority": 4, "order": 11},
    29: {"name": "🛠️ Замена предохранителей", "day_price": 75, "night_price": 59, "priority": 4, "order": 12},
    30: {"name": "Дальняя поездка до 1 часа", "day_price": 150, "night_price": 118, "hidden": True},
    31: {"name": "Дальняя поездка до 3 часов", "day_price": 648, "night_price": 512, "hidden": True},
    32: {"name": "Дальняя поездка до 5 часов", "day_price": 1147, "night_price": 905, "hidden": True},
    33: {"name": "Дальняя поездка до 10 часов", "day_price": 2243, "night_price": 1770, "hidden": True},
    34: {"name": "👨‍🔧 Развоз механика", "priority": 4, "order": 13, "kind": "group", "children": [35, 36, 37, 38]},
    35: {"name": "Развоз механика до 3 часов", "day_price": 374, "night_price": 295, "hidden": True},
    36: {"name": "Развоз механика до 5 часов", "day_price": 748, "night_price": 591, "hidden": True},
    37: {"name": "Развоз механика до 7 часов", "day_price": 1496, "night_price": 1181, "hidden": True},
    38: {"name": "Развоз механика от 7 часов", "day_price": 2243, "night_price": 1771, "hidden": True},
    39: {"name": "🚚 Перемещение ТС", "priority": 4, "order": 14, "kind": "group", "children": [40, 41, 42, 43, 44]},
    40: {"name": "Вывод в город", "day_price": 31, "night_price": 25, "hidden": True},
    41: {"name": "Перемещение ТС до 19,99 км", "day_price": 320, "night_price": 253, "hidden": True},
    42: {"name": "Перемещение ТС от 20 до 25,99 км", "day_price": 544, "night_price": 430, "hidden": True},
    43: {"name": "Перемещение ТС от 26 до 31,99 км", "day_price": 725, "night_price": 573, "hidden": True},
    44: {"name": "Перемещение ТС от 32 км", "day_price": 912, "night_price": 720, "hidden": True},
    45: {"name": "🧾 Заправка из канистры", "day_price": 278, "night_price": 278, "priority": 4, "order": 15},
    46: {"name": "🧾 Заправка из канистры (срочно)", "day_price": 498, "night_price": 609, "priority": 4, "order": 16},
    47: {"name": "🔧 Удалённая заправка", "day_price": 545, "night_price": 433, "priority": 4, "order": 17},
    48: {"name": "🚗 Обкатка ТС — 6 часов", "day_price": 1406, "night_price": 1111, "priority": 4, "order": 18},
    49: {"name": "🧢 Установка козырька", "day_price": 75, "night_price": 59, "priority": 4, "order": 19},
    50: {"name": "💡 Установка повторителя поворота", "day_price": 156, "night_price": 123, "priority": 4, "order": 20},
    51: {"name": "🛠️ Установка накладки ПТФ", "day_price": 75, "night_price": 59, "priority": 4, "order": 21},
    52: {"name": "🔑 Установка ключа", "day_price": 75, "night_price": 59, "priority": 4, "order": 22},
    53: {"name": "📝 Оформление ДТП до 1 часа", "day_price": 151, "night_price": 119, "priority": 4, "order": 23},
    54: {"name": "📝 Оформление ДТП до 2 часов", "day_price": 280, "night_price": 220, "priority": 4, "order": 24},
    55: {"name": "📝 Оформление ДТП до 3 часов", "day_price": 410, "night_price": 330, "priority": 4, "order": 25},
    56: {"name": "🪵 Закрепить фанеру в багажнике", "day_price": 75, "night_price": 59, "priority": 4, "order": 26},
    57: {"name": "🪞 Установка регулировки зеркал", "day_price": 125, "night_price": 99, "priority": 4, "order": 27},
    58: {"name": "🚛 Задача эвакуатор", "day_price": 208, "night_price": 165, "priority": 4, "order": 28},
    59: {"name": "📡 Фиксация телематики", "day_price": 75, "night_price": 59, "priority": 4, "order": 29},
    60: {"name": "🛞 Временный ремонт 1 колеса (жгут)", "day_price": 276, "night_price": 218, "priority": 4, "order": 30},
    61: {"name": "📝 Оформление ДТП до 4 часов", "day_price": 437, "night_price": 380, "priority": 4, "order": 31},
    62: {"name": "📝 Оформление ДТП более 5 часов", "day_price": 620, "night_price": 590, "priority": 4, "order": 32},
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


def validate_car_number(text: str, require_region: bool = False) -> tuple[bool, str, str]:
    """Проверка и нормализация номера машины."""
    if not text:
        return False, "", "Введите номер машины"

    import re

    normalized = normalize_car_number(text)
    if len(normalized) < 6:
        return False, normalized, f"Номер слишком короткий: {normalized}"

    pattern_full = rf'^[{RUS_LETTERS}]\d{{3}}[{RUS_LETTERS}]{{2}}\d{{3}}$'
    pattern_short = rf'^[{RUS_LETTERS}]\d{{3}}[{RUS_LETTERS}]{{2}}$'

    if re.match(pattern_short, normalized):
        if require_region:
            return False, normalized, "Укажите регион номера. Например: А123ВС777"
        return True, normalized, ""
    if re.match(pattern_full, normalized):
        return True, normalized, ""

    # Свободный формат (например, ХРУ340 или 340ХРУ)
    compact_letters = ''.join(ch for ch in normalized if ch in RUS_LETTERS)
    compact_digits = ''.join(ch for ch in normalized if ch.isdigit())
    if len(compact_letters) >= 3 and len(compact_digits) >= 3:
        rebuilt = compact_letters[0] + compact_digits[:3] + compact_letters[1:3]
        suffix = compact_digits[3:6]
        rebuilt += suffix
        if re.match(pattern_full, rebuilt) or (not require_region and re.match(pattern_short, rebuilt)):
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
