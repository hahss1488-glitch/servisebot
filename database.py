import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional

DB_PATH = "service_bot.db"
DB_TIMEZONE = "Europe/Moscow"
LOCAL_TZ = ZoneInfo(DB_TIMEZONE)


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)

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

    # Таблица настроек пользователя
    cur.execute("""CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        daily_goal INTEGER DEFAULT 0,
        price_mode TEXT DEFAULT 'day',
        last_decade_notified TEXT DEFAULT '',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    # Миграции для уже существующей таблицы user_settings
    cur.execute("PRAGMA table_info(user_settings)")
    columns = {row[1] for row in cur.fetchall()}
    if "price_mode" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN price_mode TEXT DEFAULT 'day'")
    if "last_decade_notified" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN last_decade_notified TEXT DEFAULT ''")
    
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
            (user_id, now_local())
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

    @staticmethod
    def get_shift(shift_id: int) -> Optional[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def close_shift(shift_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE shifts SET end_time = ?, status = 'closed' WHERE id = ?",
            (now_local(), shift_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_daily_goal(user_id: int) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT daily_goal FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if row and row["daily_goal"] is not None:
            return int(row["daily_goal"])
        return 0

    @staticmethod
    def set_daily_goal(user_id: int, goal: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO user_settings (user_id, daily_goal)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET daily_goal = excluded.daily_goal""",
            (user_id, goal)
        )
        conn.commit()
        conn.close()


    @staticmethod
    def get_price_mode(user_id: int) -> str:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT price_mode FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if row and row["price_mode"] in {"day", "night"}:
            return row["price_mode"]
        return "day"

    @staticmethod
    def set_price_mode(user_id: int, mode: str):
        normalized_mode = "night" if mode == "night" else "day"
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO user_settings (user_id, price_mode)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET price_mode = excluded.price_mode""",
            (user_id, normalized_mode)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_last_decade_notified(user_id: int) -> str:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT last_decade_notified FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return row["last_decade_notified"] if row and row["last_decade_notified"] else ""

    @staticmethod
    def set_last_decade_notified(user_id: int, decade_key: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO user_settings (user_id, last_decade_notified)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_decade_notified = excluded.last_decade_notified""",
            (user_id, decade_key)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_user_total_for_date(user_id: int, date_str: str) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT COALESCE(SUM(c.total_amount), 0)
            FROM shifts s
            LEFT JOIN cars c ON s.id = c.shift_id
            WHERE s.user_id = ? AND date(s.start_time) = date(?)""",
            (user_id, date_str)
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

    @staticmethod
    def get_active_leaderboard(limit: int = 10) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT u.name,
            COUNT(DISTINCT s.id) as shift_count,
            COALESCE(SUM(c.total_amount), 0) as total_amount
            FROM users u
            JOIN shifts s ON s.user_id = u.id AND s.status = 'active'
            LEFT JOIN cars c ON c.shift_id = s.id
            GROUP BY u.id
            ORDER BY total_amount DESC
            LIMIT ?""",
            (limit,)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_user_total_between_dates(user_id: int, start_date: str, end_date: str) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT COALESCE(SUM(c.total_amount), 0)
            FROM shifts s
            LEFT JOIN cars c ON s.id = c.shift_id
            WHERE s.user_id = ? AND date(s.start_time) BETWEEN date(?) AND date(?)""",
            (user_id, start_date, end_date)
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

    @staticmethod
    def get_service_stats(user_id: int, limit: int = 10) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT cs.service_name,
            SUM(cs.quantity) as total_count,
            SUM(cs.price * cs.quantity) as total_amount
            FROM shifts s
            JOIN cars c ON c.shift_id = s.id
            JOIN car_services cs ON cs.car_id = c.id
            WHERE s.user_id = ?
            GROUP BY cs.service_name
            ORDER BY total_amount DESC
            LIMIT ?""",
            (user_id, limit)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_car_stats(user_id: int, limit: int = 10) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT c.car_number,
            COUNT(c.id) as visits,
            SUM(c.total_amount) as total_amount
            FROM shifts s
            JOIN cars c ON c.shift_id = s.id
            WHERE s.user_id = ?
            GROUP BY c.car_number
            ORDER BY total_amount DESC
            LIMIT ?""",
            (user_id, limit)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_shift_report_rows(user_id: int) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT s.id as shift_id,
            s.start_time,
            s.end_time,
            c.car_number,
            c.total_amount,
            GROUP_CONCAT(cs.service_name || ' x' || cs.quantity, '; ') as services
            FROM shifts s
            LEFT JOIN cars c ON c.shift_id = s.id
            LEFT JOIN car_services cs ON cs.car_id = c.id
            WHERE s.user_id = ?
            GROUP BY s.id, c.id
            ORDER BY s.start_time DESC""",
            (user_id,)
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
    def delete_car(car_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM car_services WHERE car_id = ?", (car_id,))
        cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
        conn.commit()
        conn.close()

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
    def remove_service_from_car(car_id: int, service_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, quantity FROM car_services
            WHERE car_id = ? AND service_id = ?
            ORDER BY created_at DESC
            LIMIT 1""",
            (car_id, service_id)
        )
        existing = cur.fetchone()
        if not existing:
            conn.close()
            return False

        if existing["quantity"] > 1:
            new_quantity = existing["quantity"] - 1
            cur.execute(
                "UPDATE car_services SET quantity = ? WHERE id = ?",
                (new_quantity, existing["id"])
            )
        else:
            cur.execute("DELETE FROM car_services WHERE id = ?", (existing["id"],))

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
        return True

    @staticmethod
    def clear_car_services(car_id: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM car_services WHERE car_id = ?", (car_id,))
        cur.execute("UPDATE cars SET total_amount = 0 WHERE id = ?", (car_id,))
        conn.commit()
        conn.close()


    @staticmethod
    def get_month_days_with_totals(user_id: int, year: int, month: int) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT date(s.start_time) as day,
            COUNT(c.id) as cars_count,
            COALESCE(SUM(c.total_amount), 0) as total_amount
            FROM shifts s
            LEFT JOIN cars c ON c.shift_id = s.id
            WHERE s.user_id = ?
              AND strftime('%Y', s.start_time) = ?
              AND strftime('%m', s.start_time) = ?
            GROUP BY day
            ORDER BY day DESC""",
            (user_id, f"{year:04d}", f"{month:02d}")
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_cars_for_day(user_id: int, day: str) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT c.id, c.car_number, c.total_amount, c.shift_id, c.created_at
            FROM cars c
            JOIN shifts s ON s.id = c.shift_id
            WHERE s.user_id = ? AND date(s.start_time) = date(?)
            ORDER BY c.created_at""",
            (user_id, day)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def delete_car_for_user(user_id: int, car_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT c.id
            FROM cars c
            JOIN shifts s ON s.id = c.shift_id
            WHERE c.id = ? AND s.user_id = ?""",
            (car_id, user_id)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        cur.execute("DELETE FROM car_services WHERE car_id = ?", (car_id,))
        cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def delete_day_data(user_id: int, day: str) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT c.id
            FROM cars c
            JOIN shifts s ON s.id = c.shift_id
            WHERE s.user_id = ? AND date(s.start_time) = date(?)""",
            (user_id, day)
        )
        car_ids = [row[0] for row in cur.fetchall()]
        for car_id in car_ids:
            cur.execute("DELETE FROM car_services WHERE car_id = ?", (car_id,))
            cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
        conn.commit()
        conn.close()
        return len(car_ids)

    @staticmethod
    def get_user_months_with_data(user_id: int, limit: int = 12) -> List[str]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT DISTINCT strftime('%Y-%m', start_time) as ym
            FROM shifts
            WHERE user_id = ?
            ORDER BY ym DESC
            LIMIT ?""",
            (user_id, limit)
        )
        rows = cur.fetchall()
        conn.close()
        return [row["ym"] for row in rows if row["ym"]]


    @staticmethod
    def prune_empty_shifts_for_user(user_id: int) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT s.id
            FROM shifts s
            LEFT JOIN cars c ON c.shift_id = s.id
            WHERE s.user_id = ?
            GROUP BY s.id
            HAVING COUNT(c.id) = 0""",
            (user_id,)
        )
        shift_ids = [row[0] for row in cur.fetchall()]
        for shift_id in shift_ids:
            cur.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
        conn.commit()
        conn.close()
        return len(shift_ids)


if __name__ == "__main__":
    init_database()
    print("База данных готова")
