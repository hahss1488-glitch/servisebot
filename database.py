import sqlite3
import json
import calendar
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional

DB_PATH = "service_bot.db"
DB_TIMEZONE = "Europe/Moscow"
LOCAL_TZ = ZoneInfo(DB_TIMEZONE)
SHIFT_WORK_DAY_EXPR = "COALESCE(NULLIF(s.work_date, ''), date(s.start_time, '+3 hours'))"


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
        shift_target INTEGER DEFAULT 0,
        work_date TEXT DEFAULT '',
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
        decade_goal INTEGER DEFAULT 0,
        price_mode TEXT DEFAULT 'day',
        last_decade_notified TEXT DEFAULT '',
        is_blocked INTEGER DEFAULT 0,
        include_in_leaderboard INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS app_content (
        key TEXT PRIMARY KEY,
        value TEXT DEFAULT ''
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS banned_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id BIGINT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reason TEXT DEFAULT ''
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS user_calendar_overrides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        day TEXT NOT NULL,
        day_type TEXT NOT NULL,
        UNIQUE(user_id, day),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    # Таблица пользовательских комбинаций услуг
    cur.execute("""CREATE TABLE IF NOT EXISTS user_combos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        service_ids TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    # Миграции для уже существующей таблицы user_settings
    cur.execute("PRAGMA table_info(user_settings)")
    columns = {row[1] for row in cur.fetchall()}
    if "price_mode" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN price_mode TEXT DEFAULT 'day'")
    if "last_decade_notified" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN last_decade_notified TEXT DEFAULT ''")
    if "is_blocked" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN is_blocked INTEGER DEFAULT 0")
    if "include_in_leaderboard" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN include_in_leaderboard INTEGER DEFAULT 1")
    if "goal_enabled" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN goal_enabled INTEGER DEFAULT 0")
    if "goal_chat_id" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN goal_chat_id BIGINT DEFAULT 0")
    if "goal_message_id" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN goal_message_id BIGINT DEFAULT 0")
    if "price_mode_lock_until" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN price_mode_lock_until TEXT DEFAULT ''")
    if "subscription_expires_at" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN subscription_expires_at TEXT DEFAULT ''")
    if "work_anchor_date" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN work_anchor_date TEXT DEFAULT ''")
    if "decade_goal" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN decade_goal INTEGER DEFAULT 0")
    if "shift_goal" not in columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN shift_goal INTEGER DEFAULT 0")

    cur.execute("PRAGMA table_info(shifts)")
    shift_columns = {row[1] for row in cur.fetchall()}
    if "shift_target" not in shift_columns:
        cur.execute("ALTER TABLE shifts ADD COLUMN shift_target INTEGER DEFAULT 0")
    if "pause_started_at" not in shift_columns:
        cur.execute("ALTER TABLE shifts ADD COLUMN pause_started_at TEXT DEFAULT ''")
    if "paused_seconds" not in shift_columns:
        cur.execute("ALTER TABLE shifts ADD COLUMN paused_seconds INTEGER DEFAULT 0")
    if "work_date" not in shift_columns:
        cur.execute("ALTER TABLE shifts ADD COLUMN work_date TEXT DEFAULT ''")
    cur.execute(
        """UPDATE shifts
        SET work_date = date(start_time, '+3 hours')
        WHERE COALESCE(work_date, '') = ''"""
    )
    cur.execute(
        """UPDATE shifts
        SET work_date = date(start_time, '+3 hours')
        WHERE date(work_date) <> date(start_time, '+3 hours')"""
    )

    cur.execute("PRAGMA table_info(user_settings)")
    settings_columns = {row[1] for row in cur.fetchall()}
    if "broadcast_enabled" not in settings_columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN broadcast_enabled INTEGER DEFAULT 1")
    if "images_enabled" not in settings_columns:
        cur.execute("ALTER TABLE user_settings ADD COLUMN images_enabled INTEGER DEFAULT 1")
    
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

    @staticmethod
    def update_user_name(user_id: int, name: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET name = ? WHERE id = ?", (str(name).strip(), user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def is_user_blocked(user_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT is_blocked FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return bool(row and int(row["is_blocked"] or 0) == 1)

    @staticmethod
    def set_user_blocked(user_id: int, blocked: bool) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, is_blocked)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET is_blocked = excluded.is_blocked""",
            (user_id, 1 if blocked else 0)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_users_with_stats() -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT u.id, u.telegram_id, u.name, u.created_at,
            COALESCE(us.is_blocked, 0) as is_blocked,
            COALESCE(us.include_in_leaderboard, 1) as include_in_leaderboard,
            COALESCE(us.broadcast_enabled, 1) as broadcast_enabled,
            COALESCE(COUNT(DISTINCT s.id), 0) as shifts_count,
            COALESCE(SUM(c.total_amount), 0) as total_amount
            FROM users u
            LEFT JOIN user_settings us ON us.user_id = u.id
            LEFT JOIN shifts s ON s.user_id = u.id
            LEFT JOIN cars c ON c.shift_id = s.id
            GROUP BY u.id
            ORDER BY u.created_at DESC"""
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def is_telegram_banned(telegram_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM banned_users WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        conn.close()
        return bool(row)

    @staticmethod
    def get_banned_users() -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT telegram_id, name, banned_at, reason
            FROM banned_users
            ORDER BY banned_at DESC"""
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def unban_telegram_user(telegram_id: int) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM banned_users WHERE telegram_id = ?", (telegram_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def ban_and_delete_user(user_id: int, reason: str = "") -> None:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT telegram_id, name FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return

        telegram_id = int(row["telegram_id"])
        name = str(row["name"] or "Пользователь")

        cur.execute(
            """INSERT INTO banned_users (telegram_id, name, reason)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                name = excluded.name,
                reason = excluded.reason,
                banned_at = CURRENT_TIMESTAMP""",
            (telegram_id, name, reason),
        )

        cur.execute(
            """DELETE FROM car_services
            WHERE car_id IN (
                SELECT c.id
                FROM cars c
                JOIN shifts s ON s.id = c.shift_id
                WHERE s.user_id = ?
            )""",
            (user_id,),
        )
        cur.execute("DELETE FROM cars WHERE shift_id IN (SELECT id FROM shifts WHERE user_id = ?)", (user_id,))
        cur.execute("DELETE FROM shifts WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM user_calendar_overrides WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM user_combos WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))

        conn.commit()
        conn.close()

    # ========== СМЕНЫ ==========
    @staticmethod
    def start_shift(user_id: int) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO shifts (user_id, start_time, work_date) VALUES (?, ?, ?)",
            (user_id, now_local(), now_local().date().isoformat())
        )
        shift_id = cur.lastrowid
        conn.commit()
        conn.close()
        return shift_id

    @staticmethod
    def set_shift_target(shift_id: int, shift_target: int) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE shifts SET shift_target = ? WHERE id = ?", (int(shift_target or 0), shift_id))
        conn.commit()
        conn.close()

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
    def get_shift_top_services(shift_id: int, limit: int = 3) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT cs.service_name,
            SUM(cs.quantity) as total_count,
            SUM(cs.price * cs.quantity) as total_amount
            FROM cars c
            JOIN car_services cs ON cs.car_id = c.id
            WHERE c.shift_id = ?
            GROUP BY cs.service_name
            ORDER BY total_amount DESC
            LIMIT ?""",
            (shift_id, limit)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_user_shifts(user_id: int, limit: int = 10) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT s.*, COALESCE(SUM(c.total_amount), 0) as total_amount
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
        row = DatabaseManager.get_shift(shift_id)
        paused_seconds = int((row or {}).get("paused_seconds") or 0)
        pause_started_at = (row or {}).get("pause_started_at")
        if pause_started_at:
            try:
                started_dt = datetime.fromisoformat(str(pause_started_at))
                paused_seconds += max(0, int((now_local() - started_dt).total_seconds()))
            except Exception:
                pass
        cur.execute(
            "UPDATE shifts SET end_time = ?, status = 'closed', pause_started_at = '', paused_seconds = ? WHERE id = ?",
            (now_local(), paused_seconds, shift_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def toggle_shift_pause(shift_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT pause_started_at, paused_seconds FROM shifts WHERE id = ?", (shift_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False

        pause_started_at = str(row["pause_started_at"] or "").strip()
        paused_seconds = int(row["paused_seconds"] or 0)
        if pause_started_at:
            try:
                started_dt = datetime.fromisoformat(pause_started_at)
                paused_seconds += max(0, int((now_local() - started_dt).total_seconds()))
            except Exception:
                pass
            cur.execute(
                "UPDATE shifts SET pause_started_at = '', paused_seconds = ? WHERE id = ?",
                (paused_seconds, shift_id),
            )
            conn.commit()
            conn.close()
            return False

        cur.execute(
            "UPDATE shifts SET pause_started_at = ? WHERE id = ?",
            (now_local().isoformat(), shift_id),
        )
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def get_shift_effective_hours(shift: Dict) -> float:
        start_time = shift.get("start_time")
        end_time = shift.get("end_time") or now_local().isoformat()
        try:
            start_dt = datetime.fromisoformat(str(start_time))
            end_dt = datetime.fromisoformat(str(end_time))
        except Exception:
            return 0.01

        total_seconds = max(0.0, (end_dt - start_dt).total_seconds())
        paused_seconds = int(shift.get("paused_seconds") or 0)
        pause_started_at = str(shift.get("pause_started_at") or "").strip()
        if pause_started_at and not shift.get("end_time"):
            try:
                pause_dt = datetime.fromisoformat(pause_started_at)
                paused_seconds += max(0, int((now_local() - pause_dt).total_seconds()))
            except Exception:
                pass
        effective_seconds = max(36.0, total_seconds - max(0, paused_seconds))
        return effective_seconds / 3600.0

    @staticmethod
    def delete_shift(shift_id: int) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM car_services WHERE car_id IN (SELECT id FROM cars WHERE shift_id = ?)", (shift_id,))
        cur.execute("DELETE FROM cars WHERE shift_id = ?", (shift_id,))
        cur.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
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
    def get_shift_goal(user_id: int) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT shift_goal FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if row and row["shift_goal"] is not None:
            return int(row["shift_goal"])
        return 0

    @staticmethod
    def set_daily_goal(user_id: int, goal: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, daily_goal)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET daily_goal = excluded.daily_goal""",
            (user_id, goal)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def set_shift_goal(user_id: int, goal: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, shift_goal)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET shift_goal = excluded.shift_goal""",
            (user_id, int(goal or 0))
        )
        conn.commit()
        conn.close()


    @staticmethod
    def get_decade_goal(user_id: int) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT decade_goal FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if row and row["decade_goal"] is not None:
            return int(row["decade_goal"])
        return 0

    @staticmethod
    def set_decade_goal(user_id: int, goal: int):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, decade_goal)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET decade_goal = excluded.decade_goal""",
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
    def set_price_mode(user_id: int, mode: str, lock_until: str = ""):
        normalized_mode = "night" if mode == "night" else "day"
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, price_mode, price_mode_lock_until)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                price_mode = excluded.price_mode,
                price_mode_lock_until = excluded.price_mode_lock_until""",
            (user_id, normalized_mode, lock_until or "")
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
            f"""INSERT INTO user_settings (user_id, last_decade_notified)
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
            f"""SELECT COALESCE(SUM(c.total_amount), 0)
            FROM cars c
            JOIN shifts s ON s.id = c.shift_id
            WHERE s.user_id = ? AND {SHIFT_WORK_DAY_EXPR} = date(?)""",
            (user_id, date_str)
        )
        row = cur.fetchone()
        conn.close()
        return int(row[0] or 0) if row else 0

    @staticmethod
    def get_user_cars_count_for_date(user_id: int, date_str: str) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT COUNT(c.id)
            FROM cars c
            JOIN shifts s ON s.id = c.shift_id
            WHERE s.user_id = ? AND {SHIFT_WORK_DAY_EXPR} = date(?)""",
            (user_id, date_str)
        )
        row = cur.fetchone()
        conn.close()
        return int(row[0] or 0) if row else 0

    @staticmethod
    def get_active_leaderboard(limit: int = 10) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT u.name, u.telegram_id,
            COUNT(DISTINCT s.id) as shift_count,
            COALESCE(SUM(c.total_amount), 0) as total_amount
            FROM users u
            JOIN shifts s ON s.user_id = u.id AND s.status = 'active'
            LEFT JOIN cars c ON c.shift_id = s.id
            LEFT JOIN user_settings us ON us.user_id = u.id
            WHERE COALESCE(us.is_blocked, 0) = 0
              AND COALESCE(us.include_in_leaderboard, 1) = 1
            GROUP BY u.id
            ORDER BY total_amount DESC
            LIMIT ?""",
            (limit,)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_decade_leaderboard(year: int, month: int, decade_index: int, limit: int = 10) -> List[Dict]:
        if decade_index == 1:
            start_day, end_day = 1, 10
        elif decade_index == 2:
            start_day, end_day = 11, 20
        else:
            start_day, end_day = 21, calendar.monthrange(year, month)[1]

        start_date = f"{year:04d}-{month:02d}-{start_day:02d}"
        end_date = f"{year:04d}-{month:02d}-{end_day:02d}"

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT u.name, u.telegram_id,
            COUNT(DISTINCT s.id) as shift_count,
            COALESCE(SUM(c.total_amount), 0) as total_amount
            FROM users u
            JOIN shifts s ON s.user_id = u.id
            JOIN cars c ON c.shift_id = s.id
            LEFT JOIN user_settings us ON us.user_id = u.id
            WHERE COALESCE(us.is_blocked, 0) = 0
              AND COALESCE(us.include_in_leaderboard, 1) = 1
              AND {SHIFT_WORK_DAY_EXPR} BETWEEN date(?) AND date(?)
            GROUP BY u.id
            ORDER BY total_amount DESC
            LIMIT ?""",
            (start_date, end_date, limit)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_decade_leaderboard_daily(year: int, month: int, decade_index: int, limit: int = 10) -> List[Dict]:
        if decade_index == 1:
            start_day, end_day = 1, 10
        elif decade_index == 2:
            start_day, end_day = 11, 20
        else:
            start_day, end_day = 21, calendar.monthrange(year, month)[1]

        start_date = f"{year:04d}-{month:02d}-{start_day:02d}"
        end_date = f"{year:04d}-{month:02d}-{end_day:02d}"
        total_days = max(end_day - start_day + 1, 1)
        current_day = now_local().day if (now_local().year == year and now_local().month == month) else end_day
        elapsed_days = min(max(current_day - start_day + 1, 0), total_days)
        elapsed_ratio = (elapsed_days / total_days) if total_days > 0 else 1.0

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT u.id as user_id, u.name, u.telegram_id,
            COALESCE(SUM(c.total_amount), 0) as total_amount,
            COUNT(DISTINCT s.id) as shift_count,
            COALESCE(us.decade_goal, 0) as decade_goal
            FROM users u
            JOIN shifts s ON s.user_id = u.id
            JOIN cars c ON c.shift_id = s.id
            LEFT JOIN user_settings us ON us.user_id = u.id
            WHERE COALESCE(us.is_blocked, 0) = 0
              AND COALESCE(us.include_in_leaderboard, 1) = 1
              AND {SHIFT_WORK_DAY_EXPR} BETWEEN date(?) AND date(?)
            GROUP BY u.id
            ORDER BY total_amount DESC
            LIMIT ?""",
            (start_date, end_date, limit)
        )
        users = [dict(row) for row in cur.fetchall()]
        if not users:
            conn.close()
            return []

        user_ids = [u["user_id"] for u in users]
        placeholders = ",".join("?" for _ in user_ids)
        cur.execute(
            f"""SELECT s.user_id as user_id,
            CAST(strftime('%d', {SHIFT_WORK_DAY_EXPR}) AS INTEGER) as day,
            COALESCE(SUM(c.total_amount), 0) as total_amount
            FROM cars c
            JOIN shifts s ON s.id = c.shift_id
            WHERE s.user_id IN ({placeholders})
              AND {SHIFT_WORK_DAY_EXPR} BETWEEN date(?) AND date(?)
            GROUP BY s.user_id, day""",
            [*user_ids, start_date, end_date]
        )
        per_day = cur.fetchall()

        now_str = now_local().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            f"""SELECT s.user_id as user_id,
            COALESCE(SUM(((julianday(COALESCE(s.end_time, ?)) - julianday(s.start_time)) * 24.0) - ((COALESCE(s.paused_seconds,0) + CASE WHEN COALESCE(s.pause_started_at,'') <> '' AND s.end_time IS NULL THEN (julianday(?) - julianday(s.pause_started_at)) * 86400 ELSE 0 END) / 3600.0)), 0) as total_hours
            FROM shifts s
            WHERE s.user_id IN ({placeholders})
              AND EXISTS (
                SELECT 1 FROM cars c
                WHERE c.shift_id = s.id
                  AND {SHIFT_WORK_DAY_EXPR} BETWEEN date(?) AND date(?)
              )
            GROUP BY s.user_id""",
            [now_str, now_str, *user_ids, start_date, end_date]
        )
        hours_rows = cur.fetchall()
        conn.close()

        day_map: Dict[int, Dict[int, int]] = {}
        for row in per_day:
            uid = int(row["user_id"])
            day_map.setdefault(uid, {})[int(row["day"])] = int(row["total_amount"] or 0)

        hours_map: Dict[int, float] = {}
        for row in hours_rows:
            uid = int(row["user_id"])
            hours_map[uid] = max(float(row["total_hours"] or 0.0), 0.0)

        for row in users:
            uid = int(row["user_id"])
            total_amount = int(row.get("total_amount") or 0)
            total_hours = float(hours_map.get(uid, 0.0))
            avg_per_hour = int(total_amount / total_hours) if total_hours > 0 else 0
            decade_goal = int(row.get("decade_goal") or 0)
            progress_pct = 100 if decade_goal <= 0 else min(200, int((total_amount * 100) / max(decade_goal, 1)))
            run_rate = None
            if decade_goal > 0 and elapsed_ratio > 0:
                expected_now = max(1.0, decade_goal * elapsed_ratio)
                run_rate = max(0.0, min(2.0, total_amount / expected_now))
            row["daily_amounts"] = day_map.get(uid, {})
            row["avg_per_hour"] = avg_per_hour
            row["total_hours"] = round(total_hours, 1)
            row["progress_pct"] = progress_pct
            row["run_rate"] = run_rate
            row["shifts_count"] = int(row.get("shift_count") or 0)
        return users

    @staticmethod
    def is_user_in_leaderboard(user_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT include_in_leaderboard FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if not row or row["include_in_leaderboard"] is None:
            return True
        return int(row["include_in_leaderboard"]) == 1

    @staticmethod
    def set_user_in_leaderboard(user_id: int, include: bool) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, include_in_leaderboard)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET include_in_leaderboard = excluded.include_in_leaderboard""",
            (user_id, 1 if include else 0)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def is_user_in_broadcast(user_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT broadcast_enabled FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if not row or row["broadcast_enabled"] is None:
            return True
        return int(row["broadcast_enabled"]) == 1

    @staticmethod
    def set_user_in_broadcast(user_id: int, include: bool) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, broadcast_enabled)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET broadcast_enabled = excluded.broadcast_enabled""",
            (user_id, 1 if include else 0)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def is_images_enabled(user_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT images_enabled FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if not row or row["images_enabled"] is None:
            return True
        return int(row["images_enabled"]) == 1

    @staticmethod
    def set_images_enabled(user_id: int, enabled: bool) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, images_enabled)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET images_enabled = excluded.images_enabled""",
            (user_id, 1 if enabled else 0)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_user_total_between_dates(user_id: int, start_date: str, end_date: str) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT COALESCE(SUM(c.total_amount), 0)
            FROM shifts s
            LEFT JOIN cars c ON s.id = c.shift_id
            WHERE s.user_id = ? AND {SHIFT_WORK_DAY_EXPR} BETWEEN date(?) AND date(?)""",
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
            f"""SELECT cs.service_name,
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
            f"""SELECT c.car_number,
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
            f"""SELECT s.id as shift_id,
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
    def get_previous_car_with_services(shift_id: int, current_car_id: int) -> Optional[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT c.*
            FROM cars c
            WHERE c.shift_id = ?
              AND c.id < ?
              AND EXISTS (SELECT 1 FROM car_services cs WHERE cs.car_id = c.id)
            ORDER BY c.id DESC
            LIMIT 1""",
            (shift_id, current_car_id)
        )
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
            f"""SELECT id, quantity FROM car_services 
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
            f"""UPDATE cars 
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
            f"""SELECT id, quantity FROM car_services
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
            f"""UPDATE cars
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
            f"""SELECT date(s.start_time) as day,
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
            f"""SELECT c.id, c.car_number, c.total_amount, c.shift_id, c.created_at
            FROM cars c
            JOIN shifts s ON s.id = c.shift_id
            WHERE s.user_id = ? AND {SHIFT_WORK_DAY_EXPR} = date(?)
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
            f"""SELECT c.id
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
            f"""SELECT c.id
            FROM cars c
            JOIN shifts s ON s.id = c.shift_id
            WHERE s.user_id = ? AND {SHIFT_WORK_DAY_EXPR} = date(?)""",
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
    def get_decades_with_data(user_id: int, limit: int = 18) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT
            CAST(strftime('%Y', {SHIFT_WORK_DAY_EXPR}) AS INTEGER) as year,
            CAST(strftime('%m', {SHIFT_WORK_DAY_EXPR}) AS INTEGER) as month,
            CASE
                WHEN CAST(strftime('%d', {SHIFT_WORK_DAY_EXPR}) AS INTEGER) <= 10 THEN 1
                WHEN CAST(strftime('%d', {SHIFT_WORK_DAY_EXPR}) AS INTEGER) <= 20 THEN 2
                ELSE 3
            END as decade_index,
            COUNT(c.id) as cars_count,
            COALESCE(SUM(c.total_amount), 0) as total_amount
            FROM shifts s
            JOIN cars c ON c.shift_id = s.id
            WHERE s.user_id = ?
            GROUP BY year, month, decade_index
            ORDER BY year DESC, month DESC, decade_index DESC
            LIMIT ?""",
            (user_id, limit)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ========== МАШИНЫ ==========
    @staticmethod
    def get_days_for_decade(user_id: int, year: int, month: int, decade_index: int) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()

        if decade_index == 1:
            start_day, end_day = 1, 10
        elif decade_index == 2:
            start_day, end_day = 11, 20
        else:
            start_day = 21
            end_day = calendar.monthrange(year, month)[1]

        start_date = f"{year:04d}-{month:02d}-{start_day:02d}"
        end_date = f"{year:04d}-{month:02d}-{end_day:02d}"

        cur.execute(
            f"""SELECT {SHIFT_WORK_DAY_EXPR} as day,
            COUNT(c.id) as cars_count,
            COALESCE(SUM(c.total_amount), 0) as total_amount
            FROM shifts s
            JOIN cars c ON c.shift_id = s.id
            WHERE s.user_id = ?
              AND {SHIFT_WORK_DAY_EXPR} BETWEEN date(?) AND date(?)
            GROUP BY day
            ORDER BY day""",
            (user_id, start_date, end_date)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_user_months_with_data(user_id: int, limit: int = 12) -> List[str]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT DISTINCT strftime('%Y-%m', {SHIFT_WORK_DAY_EXPR}) as ym
            FROM shifts s
            WHERE s.user_id = ?
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
            f"""SELECT s.id
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

    @staticmethod
    def reset_user_data(user_id: int) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM shifts WHERE user_id = ?", (user_id,))
        shift_ids = [row[0] for row in cur.fetchall()]

        if shift_ids:
            placeholders = ",".join("?" for _ in shift_ids)
            cur.execute(f"SELECT id FROM cars WHERE shift_id IN ({placeholders})", shift_ids)
            car_ids = [row[0] for row in cur.fetchall()]
            if car_ids:
                car_ph = ",".join("?" for _ in car_ids)
                cur.execute(f"DELETE FROM car_services WHERE car_id IN ({car_ph})", car_ids)
            cur.execute(f"DELETE FROM cars WHERE shift_id IN ({placeholders})", shift_ids)

        cur.execute("DELETE FROM shifts WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM user_combos WHERE user_id = ?", (user_id,))
        cur.execute(
            f"""INSERT INTO user_settings (user_id, daily_goal, shift_goal, decade_goal, price_mode, last_decade_notified)
            VALUES (?, 0, 0, 0, 'day', '')
            ON CONFLICT(user_id) DO UPDATE SET
                daily_goal = 0,
                shift_goal = 0,
                decade_goal = 0,
                price_mode = 'day',
                last_decade_notified = ''""",
            (user_id,)
        )

        conn.commit()
        conn.close()


    @staticmethod
    def get_user_service_usage(user_id: int) -> Dict[int, int]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT cs.service_id, COALESCE(SUM(cs.quantity), 0) AS qty
            FROM car_services cs
            JOIN cars c ON c.id = cs.car_id
            JOIN shifts s ON s.id = c.shift_id
            WHERE s.user_id = ?
            GROUP BY cs.service_id""",
            (user_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return {int(row["service_id"]): int(row["qty"]) for row in rows}



    @staticmethod
    def get_top_services_between_dates(user_id: int, start_date: str, end_date: str, limit: int = 5) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT cs.service_name,
            SUM(cs.quantity) as total_count,
            SUM(cs.price * cs.quantity) as total_amount
            FROM shifts s
            JOIN cars c ON c.shift_id = s.id
            JOIN car_services cs ON cs.car_id = c.id
            WHERE s.user_id = ? AND {SHIFT_WORK_DAY_EXPR} BETWEEN date(?) AND date(?)
            GROUP BY cs.service_name
            ORDER BY total_amount DESC
            LIMIT ?""",
            (user_id, start_date, end_date, limit)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_top_cars_between_dates(user_id: int, start_date: str, end_date: str, limit: int = 5) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT c.car_number,
            COUNT(c.id) as visits,
            SUM(c.total_amount) as total_amount
            FROM shifts s
            JOIN cars c ON c.shift_id = s.id
            WHERE s.user_id = ? AND {SHIFT_WORK_DAY_EXPR} BETWEEN date(?) AND date(?)
            GROUP BY c.car_number
            ORDER BY total_amount DESC
            LIMIT ?""",
            (user_id, start_date, end_date, limit)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def save_user_combo(user_id: int, name: str, service_ids: List[int]) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO user_combos (user_id, name, service_ids) VALUES (?, ?, ?)",
            (user_id, name, json.dumps(service_ids, ensure_ascii=False))
        )
        combo_id = cur.lastrowid
        conn.commit()
        conn.close()
        return int(combo_id)

    @staticmethod
    def get_user_combos(user_id: int) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM user_combos WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,)
        )
        rows = cur.fetchall()
        conn.close()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["service_ids"] = json.loads(item.get("service_ids") or "[]")
            except json.JSONDecodeError:
                item["service_ids"] = []
            result.append(item)
        return result

    @staticmethod
    def get_combo(combo_id: int, user_id: int) -> Optional[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_combos WHERE id = ? AND user_id = ?", (combo_id, user_id))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        item = dict(row)
        try:
            item["service_ids"] = json.loads(item.get("service_ids") or "[]")
        except json.JSONDecodeError:
            item["service_ids"] = []
        return item

    @staticmethod
    def update_combo_name(combo_id: int, user_id: int, new_name: str) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_combos SET name = ? WHERE id = ? AND user_id = ?",
            (new_name, combo_id, user_id)
        )
        updated = cur.rowcount
        conn.commit()
        conn.close()
        return bool(updated)

    @staticmethod
    def update_combo_services(combo_id: int, user_id: int, service_ids: List[int]) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_combos SET service_ids = ? WHERE id = ? AND user_id = ?",
            (json.dumps(service_ids, ensure_ascii=False), combo_id, user_id)
        )
        updated = cur.rowcount
        conn.commit()
        conn.close()
        return bool(updated)


    @staticmethod
    def delete_combo(combo_id: int, user_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM user_combos WHERE id = ? AND user_id = ?", (combo_id, user_id))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        return bool(deleted)


    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_subscription_expires_at(user_id: int) -> str:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT subscription_expires_at FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return str(row["subscription_expires_at"]) if row and row["subscription_expires_at"] else ""

    @staticmethod
    def set_subscription_expires_at(user_id: int, expires_at: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, subscription_expires_at)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET subscription_expires_at = excluded.subscription_expires_at""",
            (user_id, expires_at or "")
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_work_anchor_date(user_id: int) -> str:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT work_anchor_date FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return str(row["work_anchor_date"]) if row and row["work_anchor_date"] else ""

    @staticmethod
    def set_work_anchor_date(user_id: int, anchor_date: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, work_anchor_date)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET work_anchor_date = excluded.work_anchor_date""",
            (user_id, anchor_date or "")
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_calendar_overrides(user_id: int) -> Dict[str, str]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT day, day_type FROM user_calendar_overrides WHERE user_id = ?", (user_id,))
        rows = cur.fetchall()
        conn.close()
        return {str(r["day"]): str(r["day_type"]) for r in rows}

    @staticmethod
    def set_calendar_override(user_id: int, day: str, day_type: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        if day_type not in {"off", "extra", "planned"}:
            cur.execute("DELETE FROM user_calendar_overrides WHERE user_id = ? AND day = ?", (user_id, day))
        else:
            cur.execute(
                """INSERT INTO user_calendar_overrides (user_id, day, day_type)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, day) DO UPDATE SET day_type = excluded.day_type""",
                (user_id, day, day_type)
            )
        conn.commit()
        conn.close()

    @staticmethod
    def is_goal_enabled(user_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT goal_enabled FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return bool(row and int(row["goal_enabled"] or 0) == 1)

    @staticmethod
    def set_goal_enabled(user_id: int, enabled: bool) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, goal_enabled)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET goal_enabled = excluded.goal_enabled""",
            (user_id, 1 if enabled else 0)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_goal_message_binding(user_id: int) -> tuple[int, int]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT goal_chat_id, goal_message_id FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return 0, 0
        return int(row["goal_chat_id"] or 0), int(row["goal_message_id"] or 0)

    @staticmethod
    def set_goal_message_binding(user_id: int, chat_id: int, message_id: int) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, goal_chat_id, goal_message_id)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET goal_chat_id = excluded.goal_chat_id, goal_message_id = excluded.goal_message_id""",
            (user_id, int(chat_id), int(message_id))
        )
        conn.commit()
        conn.close()

    @staticmethod
    def clear_goal_message_binding(user_id: int) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO user_settings (user_id, goal_chat_id, goal_message_id)
            VALUES (?, 0, 0)
            ON CONFLICT(user_id) DO UPDATE SET goal_chat_id = 0, goal_message_id = 0""",
            (user_id,)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_price_mode_lock_until(user_id: int) -> str:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT price_mode_lock_until FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return str(row["price_mode_lock_until"]) if row and row["price_mode_lock_until"] else ""

    @staticmethod
    def get_shifts_count_between_dates(user_id: int, start_date: str, end_date: str) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT COUNT(s.id)
            FROM shifts s
            WHERE s.user_id = ? AND {SHIFT_WORK_DAY_EXPR} BETWEEN date(?) AND date(?)""",
            (user_id, start_date, end_date)
        )
        row = cur.fetchone()
        conn.close()
        return int(row[0] or 0) if row else 0

    @staticmethod
    def get_cars_count_between_dates(user_id: int, start_date: str, end_date: str) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT COUNT(c.id)
            FROM cars c
            JOIN shifts s ON s.id = c.shift_id
            WHERE s.user_id = ? AND {SHIFT_WORK_DAY_EXPR} BETWEEN date(?) AND date(?)""",
            (user_id, start_date, end_date)
        )
        row = cur.fetchone()
        conn.close()
        return int(row[0] or 0) if row else 0

    @staticmethod
    def get_shift_repeated_services(shift_id: int) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT c.id as car_id, c.car_number, cs.service_name, SUM(cs.quantity) as total_count
            FROM cars c JOIN car_services cs ON cs.car_id = c.id
            WHERE c.shift_id = ?
            GROUP BY c.id, c.car_number, cs.service_name
            HAVING SUM(cs.quantity) > 1
            ORDER BY c.created_at ASC, total_count DESC""",
            (shift_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_days_for_month(user_id: int, year_month: str) -> List[Dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""SELECT {SHIFT_WORK_DAY_EXPR} as day,
            COUNT(DISTINCT s.id) as shifts_count,
            COALESCE(SUM(c.total_amount),0) as total_amount
            FROM shifts s
            JOIN cars c ON c.shift_id = s.id
            WHERE s.user_id = ? AND strftime('%Y-%m', {SHIFT_WORK_DAY_EXPR}) = ?
            GROUP BY {SHIFT_WORK_DAY_EXPR}
            ORDER BY day""",
            (user_id, year_month)
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_app_content(key: str, default: str = "") -> str:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_content WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return str(row["value"]) if row and row["value"] is not None else default

    @staticmethod
    def set_app_content(key: str, value: str) -> None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO app_content (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, value)
        )
        conn.commit()
        conn.close()


if __name__ == "__main__":
    init_database()
    print("База данных готова")
