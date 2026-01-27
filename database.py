import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

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
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id BIGINT UNIQUE,
            name TEXT,
            daily_target INTEGER DEFAULT 5000,
            progress_bar_enabled BOOLEAN DEFAULT 1
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            total_amount INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )""")
        # Добавь остальные таблицы (cars, services) по аналогии
    print("✅ SQLite база инициализирована")

class DatabaseManager:
    @staticmethod
    def get_user(telegram_id: int):
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            res = cur.fetchone()
            return dict(res) if res else None

    @staticmethod
    def register_user(telegram_id: int, name: str):
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO users (telegram_id, name) VALUES (?, ?)", (telegram_id, name))
