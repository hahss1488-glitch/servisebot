import sqlite3
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Dict, List, Optional, Any

DB_PATH = "service_bot.db"

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_database():
    with get_connection() as conn:
        cur = conn.cursor()
        # Таблица пользователей
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id BIGINT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            daily_target INTEGER DEFAULT 5000,
            progress_bar_enabled BOOLEAN DEFAULT 1,
            pinned_message_id INTEGER,
            last_progress_notification INTEGER DEFAULT 0,
            settings TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        # Таблица смен
        cur.execute("""CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        # Таблица машин
        cur.execute("""CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id INTEGER NOT NULL,
            car_number TEXT NOT NULL,
            total_amount INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shift_id) REFERENCES shifts(id) ON DELETE CASCADE
        )""")
        # Таблица услуг
        cur.execute("""CREATE TABLE IF NOT EXISTS car_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
        )""")
        # Индексы для ускорения запросов
        cur.execute("CREATE INDEX IF NOT EXISTS idx_shifts_user_id ON shifts(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_shifts_status ON shifts(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cars_shift_id ON cars(shift_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_car_services_car_id ON car_services(car_id)")
    print("✅ База данных SQLite инициализирована")

class DatabaseManager:
    # ========== ПОЛЬЗОВАТЕЛИ ==========
    @staticmethod
    def get_user(telegram_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def register_user(telegram_id: int, name: str):
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO users (telegram_id, name) VALUES (?, ?)",
                (telegram_id, name)
            )
            return cur.lastrowid

    @staticmethod
    def update_user_setting(telegram_id: int, setting: str, value: Any):
        with get_connection() as conn:
            cur = conn.cursor()
            if setting in ['daily_target', 'progress_bar_enabled', 'pinned_message_id', 'last_progress_notification']:
                cur.execute(
                    f"UPDATE users SET {setting} = ? WHERE telegram_id = ?",
                    (value, telegram_id)
                )
            else:
                # Для других настроек храним в JSON
                cur.execute("SELECT settings FROM users WHERE telegram_id = ?", (telegram_id,))
                row = cur.fetchone()
                settings = json.loads(row[0]) if row and row[0] else {}
                settings[setting] = value
                cur.execute(
                    "UPDATE users SET settings = ? WHERE telegram_id = ?",
                    (json.dumps(settings), telegram_id)
                )

    # ========== СМЕНЫ ==========
    @staticmethod
    def start_shift(user_id: int) -> int:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO shifts (user_id, start_time) VALUES (?, ?)",
                (user_id, datetime.now())
            )
            return cur.lastrowid

    @staticmethod
    def get_active_shift(user_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT * FROM shifts 
                WHERE user_id = ? AND status = 'active' 
                ORDER BY start_time DESC LIMIT 1""",
                (user_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_shift(shift_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def end_shift(shift_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE shifts SET end_time = ?, status = 'completed' WHERE id = ?",
                (datetime.now(), shift_id)
            )
            # Возвращаем обновлённую смену
            cur.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_shifts(user_id: int, limit: int = 100) -> List[Dict]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT s.*, COALESCE(SUM(c.total_amount), 0) as total_amount
                FROM shifts s
                LEFT JOIN cars c ON s.id = c.shift_id
                WHERE s.user_id = ?
                GROUP BY s.id
                ORDER BY s.start_time DESC
                LIMIT ?""",
                (user_id, limit)
            )
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def delete_shift(shift_id: int) -> bool:
        with get_connection() as conn:
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
                return cur.rowcount > 0
            except:
                return False

    @staticmethod
    def get_shift_cars(shift_id: int) -> List[Dict]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM cars WHERE shift_id = ? ORDER BY created_at",
                (shift_id,)
            )
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def get_shift_total(shift_id: int) -> int:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(SUM(total_amount), 0) FROM cars WHERE shift_id = ?",
                (shift_id,)
            )
            row = cur.fetchone()
            return row[0] if row else 0

    @staticmethod
    def get_shift_report(shift_id: int) -> Dict[str, Any]:
        with get_connection() as conn:
            cur = conn.cursor()
            # Общая сумма и количество машин
            cur.execute(
                """SELECT 
                    COUNT(*) as car_count,
                    COALESCE(SUM(total_amount), 0) as total
                FROM cars WHERE shift_id = ?""",
                (shift_id,)
            )
            summary = dict(cur.fetchone())
            
            # Список машин
            cars = DatabaseManager.get_shift_cars(shift_id)
            
            # Топ услуг
            cur.execute(
                """SELECT 
                    service_name,
                    COUNT(*) as count,
                    SUM(price * quantity) as total
                FROM car_services cs
                JOIN cars c ON cs.car_id = c.id
                WHERE c.shift_id = ?
                GROUP BY service_name
                ORDER BY total DESC
                LIMIT 3""",
                (shift_id,)
            )
            top_services = []
            for row in cur.fetchall():
                top_services.append({
                    'name': row['service_name'],
                    'count': row['count'],
                    'total': row['total']
                })
            
            return {
                'cars': cars,
                'total': summary['total'],
                'car_count': summary['car_count'],
                'top_services': top_services
            }

    # ========== МАШИНЫ ==========
    @staticmethod
    def add_car(shift_id: int, car_number: str) -> int:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO cars (shift_id, car_number) VALUES (?, ?)",
                (shift_id, car_number)
            )
            return cur.lastrowid

    @staticmethod
    def get_car(car_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM cars WHERE id = ?", (car_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def delete_car(car_id: int) -> bool:
        with get_connection() as conn:
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
                return cur.rowcount > 0
            except:
                return False

    @staticmethod
    def get_car_services(car_id: int) -> List[Dict]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT * FROM car_services 
                WHERE car_id = ? 
                ORDER BY created_at""",
                (car_id,)
            )
            return [dict(row) for row in cur.fetchall()]

    # ========== УСЛУГИ ==========
    @staticmethod
    def add_service_to_car(car_id: int, service_id: int, service_name: str, price: int) -> int:
        with get_connection() as conn:
            cur = conn.cursor()
            # Проверяем, есть ли уже такая услуга у машины
            cur.execute(
                """SELECT id, quantity FROM car_services 
                WHERE car_id = ? AND service_id = ? AND price = ?""",
                (car_id, service_id, price)
            )
            existing = cur.fetchone()
            
            if existing:
                # Увеличиваем количество
                new_quantity = existing['quantity'] + 1
                cur.execute(
                    "UPDATE car_services SET quantity = ? WHERE id = ?",
                    (new_quantity, existing['id'])
                )
                service_total = price * new_quantity
            else:
                # Добавляем новую услугу
                cur.execute(
                    """INSERT INTO car_services 
                    (car_id, service_id, service_name, price, quantity) 
                    VALUES (?, ?, ?, ?, 1)""",
                    (car_id, service_id, service_name, price)
                )
                service_total = price
            
            # Обновляем общую сумму машины
            cur.execute(
                """UPDATE cars 
                SET total_amount = (
                    SELECT COALESCE(SUM(price * quantity), 0) 
                    FROM car_services 
                    WHERE car_id = ?
                ) WHERE id = ?""",
                (car_id, car_id)
            )
            
            return service_total

    @staticmethod
    def remove_last_service(car_id: int) -> int:
        with get_connection() as conn:
            cur = conn.cursor()
            # Находим последнюю добавленную услугу
            cur.execute(
                """SELECT id, price, quantity FROM car_services 
                WHERE car_id = ? 
                ORDER BY created_at DESC, id DESC 
                LIMIT 1""",
                (car_id,)
            )
            service = cur.fetchone()
            
            if not service:
                return 0
            
            new_quantity = service['quantity'] - 1
            
            if new_quantity <= 0:
                # Удаляем услугу полностью
                cur.execute("DELETE FROM car_services WHERE id = ?", (service['id'],))
                removed_total = service['price'] * service['quantity']
            else:
                # Уменьшаем количество
                cur.execute(
                    "UPDATE car_services SET quantity = ? WHERE id = ?",
                    (new_quantity, service['id'])
                )
                removed_total = service['price']
            
            # Обновляем общую сумму машины
            cur.execute(
                """UPDATE cars 
                SET total_amount = (
                    SELECT COALESCE(SUM(price * quantity), 0) 
                    FROM car_services 
                    WHERE car_id = ?
                ) WHERE id = ?""",
                (car_id, car_id)
            )
            
            return removed_total

    @staticmethod
    def clear_car_services(car_id: int):
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM car_services WHERE car_id = ?", (car_id,))
            cur.execute("UPDATE cars SET total_amount = 0 WHERE id = ?", (car_id,))

    # ========== СТАТИСТИКА ==========
    @staticmethod
    def get_user_stats(user_id: int, days: int = 30) -> Dict[str, Any]:
        with get_connection() as conn:
            cur = conn.cursor()
            start_date = datetime.now() - timedelta(days=days)
            
            # Общая статистика
            cur.execute(
                """SELECT 
                    COUNT(DISTINCT s.id) as shift_count,
                    COUNT(DISTINCT c.id) as cars_count,
                    COALESCE(SUM(c.total_amount), 0) as total_earned
                FROM shifts s
                LEFT JOIN cars c ON s.id = c.shift_id
                WHERE s.user_id = ? AND s.start_time >= ?""",
                (user_id, start_date)
            )
            stats = dict(cur.fetchone())
            
            # Среднее за смену
            if stats['shift_count'] > 0:
                stats['avg_per_shift'] = stats['total_earned'] // stats['shift_count']
            else:
                stats['avg_per_shift'] = 0
            
            return stats

if __name__ == "__main__":
    init_database()
    print("Тестирование базы данных...")
    # Пример создания тестового пользователя
    test_id = DatabaseManager.register_user(123456, "Тестовый пользователь")
    print(f"Создан пользователь с ID: {test_id}")
