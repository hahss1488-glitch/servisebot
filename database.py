"""
ГИБРИДНАЯ БАЗА ДАННЫХ: PostgreSQL или память
С поддержкой закрепленных сообщений и прогресса
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Проверяем, есть ли доступ к PostgreSQL
USE_POSTGRESQL = False

try:
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
        
        # Инициализация таблиц
        def init_postgresql():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Пользователи
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            telegram_id BIGINT UNIQUE NOT NULL,
                            name VARCHAR(100) NOT NULL,
                            daily_target INTEGER DEFAULT 5000,
                            progress_bar_enabled BOOLEAN DEFAULT TRUE,
                            pinned_message_id INTEGER DEFAULT NULL,
                            last_progress_notification INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    
                    # Смены
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
                    
                    # Машины
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS cars (
                            id SERIAL PRIMARY KEY,
                            shift_id INTEGER REFERENCES shifts(id),
                            car_number VARCHAR(20) NOT NULL,
                            total_amount INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    
                    # Услуги машин
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
        print("✅ Используется PostgreSQL")
        
except Exception as e:
    print(f"ℹ️ PostgreSQL недоступен: {e}")
    print("✅ Используется хранение в памяти")

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
        def register_user(telegram_id: int, name: str) -> int:
            """Регистрация пользователя"""
            if telegram_id in storage['users']:
                return storage['users'][telegram_id]['id']
            
            user_id = storage['next_ids']['user']
            storage['users'][telegram_id] = {
                'id': user_id,
                'telegram_id': telegram_id,
                'name': name,
                'daily_target': 5000,
                'progress_bar_enabled': True,
                'pinned_message_id': None,
                'last_progress_notification': 0,
                'created_at': datetime.now()
            }
            storage['next_ids']['user'] += 1
            return user_id
        
        @staticmethod
        def get_user(telegram_id: int) -> Optional[Dict]:
            """Получить пользователя"""
            return storage['users'].get(telegram_id)
        
        @staticmethod
        def get_user_by_id(user_id: int) -> Optional[Dict]:
            """Получить пользователя по ID"""
            for user in storage['users'].values():
                if user['id'] == user_id:
                    return user
            return None
        
        @staticmethod
        def update_user_setting(telegram_id: int, setting: str, value: Any):
            """Обновить настройки пользователя"""
            if telegram_id in storage['users']:
                if setting == 'daily_target':
                    storage['users'][telegram_id]['daily_target'] = int(value)
                elif setting == 'progress_bar_enabled':
                    storage['users'][telegram_id]['progress_bar_enabled'] = bool(value)
                elif setting == 'pinned_message_id':
                    storage['users'][telegram_id]['pinned_message_id'] = value
                elif setting == 'last_progress_notification':
                    storage['users'][telegram_id]['last_progress_notification'] = value
        
        @staticmethod
        def start_shift(user_id: int) -> int:
            """Начать новую смену"""
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
        def get_active_shift(user_id: int) -> Optional[Dict]:
            """Получить активную смену"""
            for shift in storage['shifts'].values():
                if shift['user_id'] == user_id and shift['status'] == 'active':
                    return shift
            return None
        
        @staticmethod
        def get_shift(shift_id: int) -> Optional[Dict]:
            """Получить смену по ID"""
            return storage['shifts'].get(shift_id)
        
        @staticmethod
        def get_user_shifts(user_id: int, limit: int = 20) -> List[Dict]:
            """Получить смены пользователя"""
            shifts = []
            for shift in storage['shifts'].values():
                if shift['user_id'] == user_id:
                    shifts.append(shift)
            
            shifts.sort(key=lambda x: x['created_at'], reverse=True)
            return shifts[:limit]
        
        @staticmethod
        def add_car(shift_id: int, car_number: str) -> Optional[int]:
            """Добавить машину в смену"""
            if shift_id not in storage['shifts']:
                return None
            
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
        def get_car(car_id: int) -> Optional[Dict]:
            """Получить машину"""
            return storage['cars'].get(car_id)
        
        @staticmethod
        def get_shift_cars(shift_id: int) -> List[Dict]:
            """Получить машины смены"""
            return [car for car in storage['cars'].values() if car['shift_id'] == shift_id]
        
        @staticmethod
        def add_service_to_car(car_id: int, service_id: int, service_name: str, price: int) -> int:
            """Добавить услугу к машине"""
            if car_id not in storage['cars']:
                return 0
            
            # Ищем существующую услугу
            existing_id = None
            for service in storage['car_services'].values():
                if service['car_id'] == car_id and service['service_id'] == service_id:
                    existing_id = service['id']
                    break
            
            if existing_id:
                storage['car_services'][existing_id]['quantity'] += 1
            else:
                service_id_new = storage['next_ids']['car_service']
                storage['car_services'][service_id_new] = {
                    'id': service_id_new,
                    'car_id': car_id,
                    'service_id': service_id,
                    'service_name': service_name,
                    'price': price,
                    'quantity': 1,
                    'created_at': datetime.now()
                }
                storage['next_ids']['car_service'] += 1
            
            # Пересчитываем сумму машины
            car_total = 0
            for service in storage['car_services'].values():
                if service['car_id'] == car_id:
                    car_total += service['price'] * service['quantity']
            
            storage['cars'][car_id]['total_amount'] = car_total
            
            # Обновляем сумму смены
            shift_id = storage['cars'][car_id]['shift_id']
            shift_total = DatabaseManager.get_shift_total(shift_id)
            if shift_id in storage['shifts']:
                storage['shifts'][shift_id]['total_amount'] = shift_total
            
            return car_total
        
        @staticmethod
        def remove_last_service(car_id: int) -> int:
            """Удалить последнюю добавленную услугу"""
            if car_id not in storage['cars']:
                return 0
            
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
            
            # Обновляем сумму смены
            shift_id = storage['cars'][car_id]['shift_id']
            shift_total = DatabaseManager.get_shift_total(shift_id)
            if shift_id in storage['shifts']:
                storage['shifts'][shift_id]['total_amount'] = shift_total
            
            return car_total
        
        @staticmethod
        def clear_car_services(car_id: int) -> int:
            """Очистить все услуги машины"""
            if car_id not in storage['cars']:
                return 0
            
            # Удаляем все услуги машины
            services_to_delete = []
            for service_id, service in storage['car_services'].items():
                if service['car_id'] == car_id:
                    services_to_delete.append(service_id)
            
            for service_id in services_to_delete:
                del storage['car_services'][service_id]
            
            storage['cars'][car_id]['total_amount'] = 0
            
            # Обновляем сумму смены
            shift_id = storage['cars'][car_id]['shift_id']
            shift_total = DatabaseManager.get_shift_total(shift_id)
            if shift_id in storage['shifts']:
                storage['shifts'][shift_id]['total_amount'] = shift_total
            
            return 0
        
        @staticmethod
        def get_car_services(car_id: int) -> List[Dict]:
            """Получить услуги машины"""
            return [s for s in storage['car_services'].values() if s['car_id'] == car_id]
        
        @staticmethod
        def get_shift_total(shift_id: int) -> int:
            """Получить общую сумму смены"""
            total = 0
            for car in storage['cars'].values():
                if car['shift_id'] == shift_id:
                    total += car['total_amount']
            return total
        
        @staticmethod
        def delete_car(car_id: int) -> bool:
            """Удалить машину"""
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
                
                # Обновляем сумму смены
                shift_total = DatabaseManager.get_shift_total(shift_id)
                if shift_id in storage['shifts']:
                    storage['shifts'][shift_id]['total_amount'] = shift_total
                
                return True
            return False
        
        @staticmethod
        def delete_shift(shift_id: int) -> bool:
            """Удалить смену"""
            if shift_id in storage['shifts']:
                # Удаляем все машины смены
                cars_to_delete = []
                for car_id, car in storage['cars'].items():
                    if car['shift_id'] == shift_id:
                        cars_to_delete.append(car_id)
                
                for car_id in cars_to_delete:
                    DatabaseManager.delete_car(car_id)
                
                del storage['shifts'][shift_id]
                return True
            return False
        
        @staticmethod
        def end_shift(shift_id: int) -> Optional[Dict]:
            """Завершить смену"""
            if shift_id in storage['shifts']:
                storage['shifts'][shift_id]['end_time'] = datetime.now()
                storage['shifts'][shift_id]['status'] = 'completed'
                return storage['shifts'][shift_id]
            return None
        
        @staticmethod
        def get_user_stats(user_id: int, days: int = 30) -> Dict[str, Any]:
            """Статистика пользователя"""
            cutoff_date = datetime.now() - timedelta(days=days)
            
            shift_count = 0
            total_earned = 0
            cars_count = 0
            
            for shift in storage['shifts'].values():
                if (shift['user_id'] == user_id and 
                    shift['status'] == 'completed' and
                    shift['created_at'] >= cutoff_date):
                    
                    shift_count += 1
                    total_earned += shift.get('total_amount', 0)
                    
                    # Считаем машины в смене
                    cars_in_shift = len(DatabaseManager.get_shift_cars(shift['id']))
                    cars_count += cars_in_shift
            
            avg_per_shift = total_earned / shift_count if shift_count > 0 else 0
            
            return {
                'shift_count': shift_count,
                'total_earned': total_earned,
                'cars_count': cars_count,
                'avg_per_shift': int(avg_per_shift)
            }
        
        @staticmethod
        def get_shift_report(shift_id: int) -> Dict[str, Any]:
            """Отчёт по смене"""
            shift = DatabaseManager.get_shift(shift_id)
            if not shift:
                return {}
            
            cars = DatabaseManager.get_shift_cars(shift_id)
            all_services = []
            
            for car in cars:
                car_services = DatabaseManager.get_car_services(car['id'])
                all_services.extend(car_services)
            
            # Статистика услуг
            service_stats = {}
            for service in all_services:
                name = service['service_name']
                if name not in service_stats:
                    service_stats[name] = {'count': 0, 'total': 0}
                service_stats[name]['count'] += service['quantity']
                service_stats[name]['total'] += service['price'] * service['quantity']
            
            # Топ-3 услуги
            top_services = sorted(service_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:3]
            
            return {
                'shift': shift,
                'cars': cars,
                'total': DatabaseManager.get_shift_total(shift_id),
                'service_stats': service_stats,
                'top_services': top_services
            }
        
        @staticmethod
        def save_backup():
            """Сохранить резервную копию"""
            try:
                backup_data = {
                    'users': storage['users'],
                    'shifts': storage['shifts'],
                    'cars': storage['cars'],
                    'car_services': storage['car_services'],
                    'next_ids': storage['next_ids'],
                    'backup_time': datetime.now().isoformat()
                }
                
                # Конвертируем datetime в строки
                for key in ['users', 'shifts', 'cars', 'car_services']:
                    for item_id, item in backup_data[key].items():
                        for field, value in item.items():
                            if isinstance(value, datetime):
                                backup_data[key][item_id][field] = value.isoformat()
                
                with open('backup.json', 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=2)
                
                return True
            except Exception as e:
                print(f"Ошибка при сохранении backup: {e}")
                return False
    
    print("✅ Используется хранение в памяти")

else:
    # ========== РЕАЛИЗАЦИЯ PostgreSQL ==========
    
    class DatabaseManager:
        """Версия для PostgreSQL"""
        
        @staticmethod
        def register_user(telegram_id: int, name: str) -> int:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO users (telegram_id, name) 
                        VALUES (%s, %s)
                        ON CONFLICT (telegram_id) DO UPDATE SET name = EXCLUDED.name
                        RETURNING id
                    """, (telegram_id, name))
                    result = cur.fetchone()
                    return result['id'] if result else None
        
        @staticmethod
        def get_user(telegram_id: int) -> Optional[Dict]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                    return cur.fetchone()
        
        @staticmethod
        def get_user_by_id(user_id: int) -> Optional[Dict]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                    return cur.fetchone()
        
        @staticmethod
        def update_user_setting(telegram_id: int, setting: str, value: Any):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    if setting == 'daily_target':
                        cur.execute("UPDATE users SET daily_target = %s WHERE telegram_id = %s", 
                                  (int(value), telegram_id))
                    elif setting == 'progress_bar_enabled':
                        cur.execute("UPDATE users SET progress_bar_enabled = %s WHERE telegram_id = %s", 
                                  (bool(value), telegram_id))
                    elif setting == 'pinned_message_id':
                        cur.execute("UPDATE users SET pinned_message_id = %s WHERE telegram_id = %s", 
                                  (value, telegram_id))
                    elif setting == 'last_progress_notification':
                        cur.execute("UPDATE users SET last_progress_notification = %s WHERE telegram_id = %s", 
                                  (int(value), telegram_id))
        
        @staticmethod
        def start_shift(user_id: int) -> int:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO shifts (user_id, start_time, status) 
                        VALUES (%s, NOW(), 'active')
                        RETURNING id
                    """, (user_id,))
                    return cur.fetchone()['id']
        
        @staticmethod
        def get_active_shift(user_id: int) -> Optional[Dict]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM shifts 
                        WHERE user_id = %s AND status = 'active'
                        ORDER BY id DESC LIMIT 1
                    """, (user_id,))
                    return cur.fetchone()
        
        @staticmethod
        def get_shift(shift_id: int) -> Optional[Dict]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM shifts WHERE id = %s", (shift_id,))
                    return cur.fetchone()
        
        @staticmethod
        def get_user_shifts(user_id: int, limit: int = 20) -> List[Dict]:
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
        def add_car(shift_id: int, car_number: str) -> Optional[int]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO cars (shift_id, car_number) 
                        VALUES (%s, %s)
                        RETURNING id
                    """, (shift_id, car_number))
                    result = cur.fetchone()
                    return result['id'] if result else None
        
        @staticmethod
        def get_car(car_id: int) -> Optional[Dict]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM cars WHERE id = %s", (car_id,))
                    return cur.fetchone()
        
        @staticmethod
        def get_shift_cars(shift_id: int) -> List[Dict]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM cars 
                        WHERE shift_id = %s 
                        ORDER BY created_at
                    """, (shift_id,))
                    return cur.fetchall()
        
        @staticmethod
        def add_service_to_car(car_id: int, service_id: int, service_name: str, price: int) -> int:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Проверяем, есть ли уже такая услуга
                    cur.execute("""
                        SELECT id, quantity FROM car_services 
                        WHERE car_id = %s AND service_id = %s
                    """, (car_id, service_id))
                    
                    existing = cur.fetchone()
                    
                    if existing:
                        new_quantity = existing['quantity'] + 1
                        cur.execute("""
                            UPDATE car_services 
                            SET quantity = %s 
                            WHERE id = %s
                        """, (new_quantity, existing['id']))
                    else:
                        cur.execute("""
                            INSERT INTO car_services (car_id, service_id, service_name, price, quantity) 
                            VALUES (%s, %s, %s, %s, 1)
                        """, (car_id, service_id, service_name, price))
                    
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
        def remove_last_service(car_id: int) -> int:
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
        def clear_car_services(car_id: int) -> int:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM car_services WHERE car_id = %s", (car_id,))
                    cur.execute("UPDATE cars SET total_amount = 0 WHERE id = %s", (car_id,))
                    return 0
        
        @staticmethod
        def get_car_services(car_id: int) -> List[Dict]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM car_services 
                        WHERE car_id = %s 
                        ORDER BY id
                    """, (car_id,))
                    return cur.fetchall()
        
        @staticmethod
        def get_shift_total(shift_id: int) -> int:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COALESCE(SUM(total_amount), 0) as total
                        FROM cars 
                        WHERE shift_id = %s
                    """, (shift_id,))
                    return cur.fetchone()['total']
        
        @staticmethod
        def delete_car(car_id: int) -> bool:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute("DELETE FROM car_services WHERE car_id = %s", (car_id,))
                        cur.execute("DELETE FROM cars WHERE id = %s", (car_id,))
                        return True
                    except:
                        return False
        
        @staticmethod
        def delete_shift(shift_id: int) -> bool:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        # Удаляем услуги машин смены
                        cur.execute("""
                            DELETE FROM car_services 
                            WHERE car_id IN (
                                SELECT id FROM cars WHERE shift_id = %s
                            )
                        """, (shift_id,))
                        # Удаляем машины смены
                        cur.execute("DELETE FROM cars WHERE shift_id = %s", (shift_id,))
                        # Удаляем смену
                        cur.execute("DELETE FROM shifts WHERE id = %s", (shift_id,))
                        return True
                    except:
                        return False
        
        @staticmethod
        def end_shift(shift_id: int) -> Optional[Dict]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE shifts 
                        SET end_time = NOW(), status = 'completed'
                        WHERE id = %s
                        RETURNING *
                    """, (shift_id,))
                    return cur.fetchone()
        
        @staticmethod
        def get_user_stats(user_id: int, days: int = 30) -> Dict[str, Any]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(s.id) as shift_count,
                            COALESCE(SUM(s.total_amount), 0) as total_earned,
                            COALESCE(AVG(s.total_amount), 0) as avg_per_shift
                        FROM shifts s
                        WHERE s.user_id = %s 
                        AND s.status = 'completed'
                        AND s.created_at >= NOW() - INTERVAL '%s days'
                    """, (user_id, days))
                    
                    stats = cur.fetchone()
                    
                    # Считаем машины
                    cur.execute("""
                        SELECT COUNT(c.id) as cars_count
                        FROM shifts s
                        JOIN cars c ON s.id = c.shift_id
                        WHERE s.user_id = %s 
                        AND s.status = 'completed'
                        AND s.created_at >= NOW() - INTERVAL '%s days'
                    """, (user_id, days))
                    
                    cars_result = cur.fetchone()
                    
                    return {
                        'shift_count': stats['shift_count'] if stats else 0,
                        'total_earned': stats['total_earned'] if stats else 0,
                        'cars_count': cars_result['cars_count'] if cars_result else 0,
                        'avg_per_shift': int(stats['avg_per_shift']) if stats and stats['avg_per_shift'] else 0
                    }
        
        @staticmethod
        def get_shift_report(shift_id: int) -> Dict[str, Any]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Получаем смену
                    cur.execute("SELECT * FROM shifts WHERE id = %s", (shift_id,))
                    shift = cur.fetchone()
                    
                    if not shift:
                        return {}
                    
                    # Получаем машины
                    cars = DatabaseManager.get_shift_cars(shift_id)
                    
                    # Статистика услуг
                    cur.execute("""
                        SELECT 
                            cs.service_name,
                            SUM(cs.quantity) as total_quantity,
                            SUM(cs.price * cs.quantity) as total_amount
                        FROM car_services cs
                        JOIN cars c ON cs.car_id = c.id
                        WHERE c.shift_id = %s
                        GROUP BY cs.service_name
                        ORDER BY total_amount DESC
                    """, (shift_id,))
                    
                    service_stats = cur.fetchall()
                    
                    return {
                        'shift': shift,
                        'cars': cars,
                        'total': DatabaseManager.get_shift_total(shift_id),
                        'service_stats': service_stats,
                        'top_services': service_stats[:3] if service_stats else []
                    }

def init_database():
    """Инициализация базы данных"""
    if USE_POSTGRESQL:
        print("✅ PostgreSQL инициализирован")
        # Автосохранение каждые 10 минут
        import threading
        def auto_save():
            if not USE_POSTGRESQL:
                DatabaseManager.save_backup()
            threading.Timer(600, auto_save).start()
        
        auto_save()
    else:
        print("✅ Режим в памяти активирован")
