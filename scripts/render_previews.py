import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image

from ui.premium_renderer import render_dashboard_image_bytes, render_leaderboard_image_bytes

def main():
    out = Path('reports/previews')
    out.mkdir(parents=True, exist_ok=True)

    dashboard_payload = {
        'decade_title': '1-я декада: 1–10 марта · 01.03–10.03',
        'decade_earned': 29529,
        'decade_goal': 50000,
        'completion_percent': 0.59058,
        'pace_text': '106%',
        'pace_delta_text': '+1 751 ₽ к плану',
        'decade_metrics': [
            ('Осталось до цели', '20 471 ₽', (244, 248, 255, 255)),
            ('Осталось смен', '8', (244, 248, 255, 255)),
            ('Нужно в смену', '2 559 ₽', (244, 248, 255, 255)),
            ('Средний план', '4 167 ₽', (244, 248, 255, 255)),
            ('Опережение / отставание', '+1 751 ₽', (99, 245, 210, 255)),
            ('Темп к плану', '106%', (99, 245, 210, 255)),
        ],
        'mini': ['Смен: 12', 'Машин: 117', 'Средний чек: 1 993 ₽'],
    }
    b = render_dashboard_image_bytes('closed', dashboard_payload)
    (out / 'dashboard_preview.png').write_bytes(b.getvalue())

    leaders = [
        {'telegram_id': 1, 'name': 'Александр Очень-Длинная Фамилия С Невероятным Хвостом', 'total_amount': 152340, 'total_hours': 122, 'avg_per_hour': 1249, 'run_rate': 1.14, 'shifts_count': 12},
        {'telegram_id': 2, 'name': 'Мария Лебедева', 'total_amount': 143100, 'total_hours': 153, 'avg_per_hour': 935, 'run_rate': 0.98, 'shifts_count': 14},
        {'telegram_id': 3, 'name': 'Илья', 'total_amount': 129870, 'total_hours': 118, 'avg_per_hour': 1100, 'run_rate': None, 'shifts_count': 11},
        {'telegram_id': 4, 'name': 'Владислав Нестандартное Имя Чтобы Проверить Fit', 'total_amount': 121500, 'total_hours': 144, 'avg_per_hour': 844, 'run_rate': 0.93, 'shifts_count': 13},
        {'telegram_id': 5, 'name': 'Алина', 'total_amount': 99700, 'total_hours': 90, 'avg_per_hour': 1108, 'run_rate': 1.21, 'shifts_count': 9},
        {'telegram_id': 6, 'name': 'Никита', 'total_amount': 85110, 'total_hours': 100, 'avg_per_hour': 851, 'run_rate': 0.87, 'shifts_count': 10},
    ]

    avatars = {1: Image.new('RGB', (128, 128), '#5E92FF'), 2: None, 3: Image.new('RGB', (128, 128), '#56D8CA')}
    l = render_leaderboard_image_bytes('1-я декада: 1–10 марта', leaders, top3_avatars=avatars)
    (out / 'leaderboard_preview.png').write_bytes(l.getvalue())

    print('saved previews to', out)


if __name__ == '__main__':
    main()