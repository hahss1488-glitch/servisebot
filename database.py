import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

DB_PATH = "service_bot.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_connection()
    cur = conn.cursor()
    
    # Таблица пользователей
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id BIGINT UNIQUE NOT NULL,
        name TEXT NOT NULL,
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
    
    conn.commit()
    conn.close()
    print("✅ База данных создана")

class DatabaseManager:
    # ========== ПОЛЬЗОВАТЕЛИ ==========
    @staticmethod
    def get_user(telegram_id: int) -> Optional[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def register_user(telegram_id: int, name: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO users (telegram_id, name) VALUES (?, ?)",
            (telegram_id, name)
        )
        conn.commit()
        conn.close()

    # ========== СМЕНЫ ==========
    @staticmethod
    def start_shift(user_id: int) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO shifts (user_id, start_time) VALUES (?, ?)",
            (user_id, datetime.now())
        )
        shift_id = cur.lastrowid
        conn.commit()
        conn.close()
        return shift_id

    @staticmethod
    def get_active_shift(user_id: int) -> Optional[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM shifts WHERE user_id = ? AND status = 'active' ORDER BY start_time DESC LIMIT 1",
            (user_id,)
        )
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_shift_cars(shift_id: int) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM cars WHERE shift_id = ? ORDER BY created_at",
            (shift_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_shift_total(shift_id: int) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(total_amount), 0) FROM cars WHERE shift_id = ?",
            (shift_id,)
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

    @staticmethod
    def get_user_shifts(user_id: int, limit: int = 10) -> List[Dict]:
        conn = get_connection()
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
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ========== МАШИНЫ ==========
    @staticmethod
    def add_car(shift_id: int, car_number: str) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO cars (shift_id, car_number) VALUES (?, ?)",
            (shift_id, car_number)
        )
        car_id = cur.lastrowid
        conn.commit()
        conn.close()
        return car_id

    @staticmethod
    def get_car(car_id: int) -> Optional[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM cars WHERE id = ?", (car_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_car_services(car_id: int) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM car_services WHERE car_id = ? ORDER BY created_at",
            (car_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ========== УСЛУГИ ==========
    @staticmethod
    def add_service_to_car(car_id: int, service_id: int, service_name: str, price: int) -> int:
        conn = get_connection()
        cur = conn.cursor()
        
        # Проверяем, есть ли уже такая услуга
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
        else:
            # Добавляем новую услугу
            cur.execute(
                """INSERT INTO car_services (car_id, service_id, service_name, price, quantity) 
                VALUES (?, ?, ?, ?, 1)""",
                (car_id, service_id, service_name, price)
            )
        
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
        
        conn.commit()
        conn.close()
        return price

    @staticmethod
    def clear_car_services(car_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM car_services WHERE car_id = ?", (car_id,))
        cur.execute("UPDATE cars SET total_amount = 0 WHERE id = ?", (car_id,))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    init_database()
    print("База данных готова")
