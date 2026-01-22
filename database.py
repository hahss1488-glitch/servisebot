"""
ГИБРИДНАЯ ВЕРСИЯ: PostgreSQL если доступно, иначе память
"""

import os
from datetime import datetime

# Проверяем, есть ли доступ к PostgreSQL
USE_POSTGRESQL = False
POSTGRES_CONNECTION = None

try:
    # Bothost на платном тарифе добавляет DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    
    if database_url and 'postgresql' in database_url:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from contextlib import contextmanager
        
        @contextmanager
        def get_connection():
            """Подключение к PostgreSQL"""
            conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()
        
        # Инициализируем таблицы если нужно
        def init_postgresql():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Таблицы как в полной версии
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
                    
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS cars (
                            id SERIAL PRIMARY KEY,
                            shift_id INTEGER REFERENCES shifts(id),
                            car_number VARCHAR(20) NOT NULL,
                            total_amount INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    
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
        
        init_postgresql()
        USE_POSTGRESQL = True
        print("✅ Используется PostgreSQL (платный тариф Bothost)")
        
except Exception as e:
    print(f"ℹ️ PostgreSQL недоступен: {e}")
    print("✅ Используется хранение в памяти (бесплатный тариф)")

# ========== РЕАЛИЗАЦИЯ В ПАМЯТИ ==========

if not USE_POSTGRESQL:
    # Хранилище в памяти
    storage = {
        'users': {},
        'shifts': {},
        'cars': {},
        'car_services': {},
        'next_ids': {'user': 1, 'shift': 1, 'car': 1, 'car_service': 1}
    }
    
    class DatabaseManager:
        """Версия для хранения в памяти"""
        
        @staticmethod
        def register_user(telegram_id, name):
            if telegram_id in storage['users']:
                return storage['users'][telegram_id]['id']
            
            user_id = storage['next_ids']['user']
            storage['users'][telegram_id] = {
                'id': user_id,
                'telegram_id': telegram_id,
                'name': name,
                'daily_target': 5000,
                'progress_bar_enabled': True,
                'created_at': datetime.now()
            }
            storage['next_ids']['user'] += 1
            return user_id
        
        @staticmethod
        def get_user(telegram_id):
            return storage['users'].get(telegram_id)
        
        @staticmethod
        def start_shift(user_id):
            shift_id = storage['next_ids']['shift']
            storage['shifts'][shift_id] = {
                'id': shift_id,
                'user_id': user_id,
                'start_time': datetime.now(),
                'end_time': None,
                'total_amount': 0,
                'status': 'active',
                'created_at': datetime.now()
            }
            storage['next_ids']['shift'] += 1
            return shift_id
        
        @staticmethod
        def get_active_shift(user_id):
            for shift in storage['shifts'].values():
                if shift['user_id'] == user_id and shift['status'] == 'active':
                    return shift
            return None
        
        @staticmethod
        def add_car(shift_id, car_number):
            car_id = storage['next_ids']['car']
            storage['cars'][car_id] = {
                'id': car_id,
                'shift_id': shift_id,
                'car_number': car_number,
                'total_amount': 0,
                'created_at': datetime.now()
            }
            storage['next_ids']['car'] += 1
            return car_id
        
        @staticmethod
        def get_car(car_id):
            return storage['cars'].get(car_id)
        
        @staticmethod
        def add_service_to_car(car_id, service_id, service_name, price, quantity=1):
            # Ищем существующую услугу
            existing_id = None
            for service in storage['car_services'].values():
                if service['car_id'] == car_id and service['service_id'] == service_id:
                    existing_id = service['id']
                    break
            
            if existing_id:
                storage['car_services'][existing_id]['quantity'] += quantity
            else:
                service_id_new = storage['next_ids']['car_service']
                storage['car_services'][service_id_new] = {
                    'id': service_id_new,
                    'car_id': car_id,
                    'service_id': service_id,
                    'service_name': service_name,
                    'price': price,
                    'quantity': quantity,
                    'created_at': datetime.now()
                }
                storage['next_ids']['car_service'] += 1
            
            # Пересчитываем сумму
            car_total = 0
            for service in storage['car_services'].values():
                if service['car_id'] == car_id:
                    car_total += service['price'] * service['quantity']
            
            storage['cars'][car_id]['total_amount'] = car_total
            return car_total
        
        @staticmethod
        def remove_last_service(car_id):
            # Находим последнюю услугу
            last_service = None
            for service in storage['car_services'].values():
                if service['car_id'] == car_id:
                    if not last_service or service['id'] > last_service['id']:
                        last_service = service
            
            if not last_service:
                return 0
            
            if last_service['quantity'] > 1:
                last_service['quantity'] -= 1
            else:
                del storage['car_services'][last_service['id']]
            
            # Пересчитываем сумму
            car_total = 0
            for service in storage['car_services'].values():
                if service['car_id'] == car_id:
                    car_total += service['price'] * service['quantity']
            
            storage['cars'][car_id]['total_amount'] = car_total
            return car_total
        
        @staticmethod
        def get_car_services(car_id):
            return [s for s in storage['car_services'].values() if s['car_id'] == car_id]
        
        @staticmethod
        def get_shift_cars(shift_id):
            return [c for c in storage['cars'].values() if c['shift_id'] == shift_id]
        
        @staticmethod
        def get_shift_total(shift_id):
            total = 0
            for car in storage['cars'].values():
                if car['shift_id'] == shift_id:
                    total += car['total_amount']
            return total
        
        @staticmethod
        def update_shift_total(shift_id):
            total = DatabaseManager.get_shift_total(shift_id)
            if shift_id in storage['shifts']:
                storage['shifts'][shift_id]['total_amount'] = total
            return total
        
        @staticmethod
        def delete_car(car_id):
            if car_id in storage['cars']:
                shift_id = storage['cars'][car_id]['shift_id']
                
                # Удаляем все услуги машины
                services_to_delete = []
                for service_id, service in storage['car_services'].items():
                    if service['car_id'] == car_id:
                        services_to_delete.append(service_id)
                
                for service_id in services_to_delete:
                    del storage['car_services'][service_id]
                
                del storage['cars'][car_id]
                DatabaseManager.update_shift_total(shift_id)
                return shift_id
            return None
        
        @staticmethod
        def end_shift(shift_id, end_time=None):
            if shift_id in storage['shifts']:
                storage['shifts'][shift_id]['end_time'] = end_time or datetime.now()
                storage['shifts'][shift_id]['status'] = 'completed'
                return storage['shifts'][shift_id]
            return None
        
        @staticmethod
        def get_user_shifts(user_id, limit=10):
            shifts = []
            for shift in storage['shifts'].values():
                if shift['user_id'] == user_id:
                    shifts.append(shift)
            
            shifts.sort(key=lambda x: x['created_at'], reverse=True)
            return shifts[:limit]
        
        @staticmethod
        def update_user_setting(telegram_id, setting_name, value):
            user = DatabaseManager.get_user(telegram_id)
            if user:
                if setting_name == 'daily_target':
                    storage['users'][telegram_id]['daily_target'] = int(value)
                elif setting_name == 'progress_bar_enabled':
                    storage['users'][telegram_id]['progress_bar_enabled'] = bool(value)
        
        @staticmethod
        def get_user_stats(user_id, days=30):
            shift_count = 0
            total_earned = 0
            
            for shift in storage['shifts'].values():
                if shift['user_id'] == user_id and shift['status'] == 'completed':
                    shift_count += 1
                    total_earned += shift.get('total_amount', 0)
            
            avg_per_shift = total_earned / shift_count if shift_count > 0 else 0
            
            return {
                'shift_count': shift_count,
                'total_earned': total_earned,
                'avg_per_shift': avg_per_shift
            }
    
    print("✅ Используется хранение в памяти (бесплатный тариф)")

else:
    # ========== РЕАЛИЗАЦИЯ PostgreSQL ==========
    
    class DatabaseManager:
        """Версия для PostgreSQL"""
        
        @staticmethod
        def register_user(telegram_id, name):
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
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                    return cur.fetchone()
        
        @staticmethod
        def start_shift(user_id):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO shifts (user_id, start_time, status) 
                        VALUES (%s, NOW(), 'active')
                        RETURNING id
                    """, (user_id,))
                    return cur.fetchone()['id']
        
        @staticmethod
        def get_active_shift(user_id):
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
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM cars WHERE id = %s", (car_id,))
                    return cur.fetchone()
        
        @staticmethod
        def add_service_to_car(car_id, service_id, service_name, price, quantity=1):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Проверяем, есть ли уже такая услуга
                    cur.execute("""
                        SELECT id, quantity FROM car_services 
                        WHERE car_id = %s AND service_id = %s
                    """, (car_id, service_id))
                    
                    existing = cur.fetchone()
                    
                    if existing:
                        new_quantity = existing['quantity'] + quantity
                        cur.execute("""
                            UPDATE car_services 
                            SET quantity = %s 
                            WHERE id = %s
                        """, (new_quantity, existing['id']))
                    else:
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
                        cur.execute("""
                            UPDATE car_services 
                            SET quantity = quantity - 1 
                            WHERE id = %s
                        """, (service['id'],))
                    else:
                        cur.execute("DELETE FROM car_services WHERE id = %s", (service['id'],))
                    
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
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM cars 
                        WHERE shift_id = %s 
                        ORDER BY created_at
                    """, (shift_id,))
                    return cur.fetchall()
        
        @staticmethod
        def get_shift_total(shift_id):
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
        def delete_car(car_id):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM car_services WHERE car_id = %s", (car_id,))
                    cur.execute("DELETE FROM cars WHERE id = %s RETURNING shift_id", (car_id,))
                    return cur.fetchone()['shift_id']
        
        @staticmethod
        def end_shift(shift_id, end_time=None):
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
        def get_user_shifts(user_id, limit=10):
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
        def update_user_setting(telegram_id, setting_name, value):
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
        
        @staticmethod
        def get_user_stats(user_id, days=30):
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

def init_database():
    """Инициализация базы данных"""
    if USE_POSTGRESQL:
        print("✅ PostgreSQL инициализирован")
    else:
        print("✅ Режим в памяти активирован")
