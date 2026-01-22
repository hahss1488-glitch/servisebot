"""
Работа с базой данных
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import config

@contextmanager
def get_connection():
    """Подключение к базе данных"""
    if config.DATABASE_URL:
        # Используем базу данных от Bothost
        conn = psycopg2.connect(config.DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        # Локальная база для тестирования
        conn = psycopg2.connect(
            dbname="service_bot",
            user="postgres",
            password="",
            host="localhost",
            cursor_factory=RealDictCursor
        )
    
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_database():
    """Инициализация базы данных - создание таблиц"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Таблица пользователей
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    daily_target INTEGER DEFAULT 5000,
                    progress_bar_enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Таблица смен
            cur.execute("""
                CREATE TABLE IF NOT EXISTS shifts (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    total_amount INTEGER DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Таблица машин
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cars (
                    id SERIAL PRIMARY KEY,
                    shift_id INTEGER REFERENCES shifts(id),
                    car_number VARCHAR(20) NOT NULL,
                    total_amount INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Таблица услуг машины
            cur.execute("""
                CREATE TABLE IF NOT EXISTS car_services (
                    id SERIAL PRIMARY KEY,
                    car_id INTEGER REFERENCES cars(id),
                    service_id INTEGER NOT NULL,
                    service_name VARCHAR(100) NOT NULL,
                    price INTEGER NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            print("✅ Таблицы созданы успешно")

class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    @staticmethod
    def register_user(telegram_id, name):
        """Регистрация нового пользователя"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (telegram_id, name) 
                    VALUES (%s, %s)
                    ON CONFLICT (telegram_id) DO NOTHING
                    RETURNING id
                """, (telegram_id, name))
                
                result = cur.fetchone()
                return result['id'] if result else None
    
    @staticmethod
    def get_user(telegram_id):
        """Получение информации о пользователе"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM users WHERE telegram_id = %s
                """, (telegram_id,))
                return cur.fetchone()
    
    @staticmethod
    def start_shift(user_id):
        """Начало новой смены"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO shifts (user_id, start_time, status) 
                    VALUES (%s, NOW(), 'active')
                    RETURNING id
                """, (user_id,))
                return cur.fetchone()['id']
    
    @staticmethod
    def end_shift(shift_id, end_time=None):
        """Завершение смены"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE shifts 
                    SET end_time = COALESCE(%s, NOW()), 
                        status = 'completed'
                    WHERE id = %s
                    RETURNING *
                """, (end_time, shift_id))
                return cur.fetchone()
    
    @staticmethod
    def get_active_shift(user_id):
        """Получение активной смены пользователя"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM shifts 
                    WHERE user_id = %s AND status = 'active'
                    ORDER BY id DESC LIMIT 1
                """, (user_id,))
                return cur.fetchone()
    
    @staticmethod
    def add_car(shift_id, car_number):
        """Добавление машины в смену"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO cars (shift_id, car_number) 
                    VALUES (%s, %s)
                    RETURNING id
                """, (shift_id, car_number))
                return cur.fetchone()['id']
    
    @staticmethod
    def get_car(car_id):
        """Получение информации о машине"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM cars WHERE id = %s
                """, (car_id,))
                return cur.fetchone()
    
    @staticmethod
    def add_service_to_car(car_id, service_id, service_name, price, quantity=1):
        """Добавление услуги к машине"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Проверяем, есть ли уже такая услуга у машины
                cur.execute("""
                    SELECT id, quantity FROM car_services 
                    WHERE car_id = %s AND service_id = %s
                """, (car_id, service_id))
                
                existing = cur.fetchone()
                
                if existing:
                    # Обновляем количество
                    new_quantity = existing['quantity'] + quantity
                    cur.execute("""
                        UPDATE car_services 
                        SET quantity = %s 
                        WHERE id = %s
                    """, (new_quantity, existing['id']))
                else:
                    # Добавляем новую услугу
                    cur.execute("""
                        INSERT INTO car_services (car_id, service_id, service_name, price, quantity) 
                        VALUES (%s, %s, %s, %s, %s)
                    """, (car_id, service_id, service_name, price, quantity))
                
                # Обновляем сумму машины
                cur.execute("""
                    UPDATE cars 
                    SET total_amount = (
                        SELECT COALESCE(SUM(price * quantity), 0) 
                        FROM car_services 
                        WHERE car_id = %s
                    )
                    WHERE id = %s
                    RETURNING total_amount
                """, (car_id, car_id))
                
                return cur.fetchone()['total_amount']
    
    @staticmethod
    def remove_last_service(car_id):
        """Удаление последней добавленной услуги"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Находим последнюю добавленную услугу
                cur.execute("""
                    SELECT id, quantity, price 
                    FROM car_services 
                    WHERE car_id = %s 
                    ORDER BY id DESC 
                    LIMIT 1
                """, (car_id,))
                
                service = cur.fetchone()
                
                if not service:
                    return 0
                
                if service['quantity'] > 1:
                    # Уменьшаем количество на 1
                    cur.execute("""
                        UPDATE car_services 
                        SET quantity = quantity - 1 
                        WHERE id = %s
                    """, (service['id'],))
                else:
                    # Удаляем услугу полностью
                    cur.execute("""
                        DELETE FROM car_services WHERE id = %s
                    """, (service['id'],))
                
                # Обновляем сумму машины
                cur.execute("""
                    UPDATE cars 
                    SET total_amount = (
                        SELECT COALESCE(SUM(price * quantity), 0) 
                        FROM car_services 
                        WHERE car_id = %s
                    )
                    WHERE id = %s
                    RETURNING total_amount
                """, (car_id, car_id))
                
                return cur.fetchone()['total_amount']
    
    @staticmethod
    def get_car_services(car_id):
        """Получение всех услуг машины"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM car_services 
                    WHERE car_id = %s 
                    ORDER BY id
                """, (car_id,))
                return cur.fetchall()
    
    @staticmethod
    def get_shift_cars(shift_id):
        """Получение всех машин в смене"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM cars 
                    WHERE shift_id = %s 
                    ORDER BY created_at
                """, (shift_id,))
                return cur.fetchall()
    
    @staticmethod
    def delete_car(car_id):
        """Удаление машины и всех её услуг"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM car_services WHERE car_id = %s", (car_id,))
                cur.execute("DELETE FROM cars WHERE id = %s RETURNING shift_id", (car_id,))
                return cur.fetchone()['shift_id']
    
    @staticmethod
    def get_user_shifts(user_id, limit=10):
        """Получение последних смен пользователя"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM shifts 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT %s
                """, (user_id, limit))
                return cur.fetchall()
    
    @staticmethod
    def get_shift_total(shift_id):
        """Подсчёт общей суммы смены"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COALESCE(SUM(total_amount), 0) as total
                    FROM cars 
                    WHERE shift_id = %s
                """, (shift_id,))
                return cur.fetchone()['total']
    
    @staticmethod
    def update_shift_total(shift_id):
        """Обновление общей суммы смены"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                total = DatabaseManager.get_shift_total(shift_id)
                cur.execute("""
                    UPDATE shifts 
                    SET total_amount = %s 
                    WHERE id = %s
                """, (total, shift_id))
                return total
    
    @staticmethod
    def get_user_stats(user_id, days=30):
        """Получение статистики пользователя"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as shift_count,
                        COALESCE(SUM(total_amount), 0) as total_earned,
                        COALESCE(AVG(total_amount), 0) as avg_per_shift
                    FROM shifts 
                    WHERE user_id = %s 
                    AND status = 'completed'
                    AND created_at >= NOW() - INTERVAL '%s days'
                """, (user_id, days))
                return cur.fetchone()
    
    @staticmethod
    def update_user_setting(telegram_id, setting_name, value):
        """Обновление настроек пользователя"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                if setting_name == 'daily_target':
                    cur.execute("""
                        UPDATE users 
                        SET daily_target = %s 
                        WHERE telegram_id = %s
                    """, (value, telegram_id))
                elif setting_name == 'progress_bar_enabled':
                    cur.execute("""
                        UPDATE users 
                        SET progress_bar_enabled = %s 
                        WHERE telegram_id = %s
                    """, (value, telegram_id))
