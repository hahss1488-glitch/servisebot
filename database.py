"""
ВЕРСИЯ БЕЗ БАЗЫ ДАННЫХ (работает в памяти)
"""

import json
import os
from datetime import datetime

# Хранилище в памяти
storage = {
    'users': {},
    'shifts': {},
    'cars': {},
    'car_services': {},
    'next_ids': {
        'user': 1,
        'shift': 1,
        'car': 1,
        'car_service': 1
    }
}

class DatabaseManager:
    """Менеджер для работы с данными в памяти"""
    
    @staticmethod
    def register_user(telegram_id, name):
        """Регистрация нового пользователя"""
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
        """Получение информации о пользователе"""
        return storage['users'].get(telegram_id)
    
    @staticmethod
    def start_shift(user_id):
        """Начало новой смены"""
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
        """Получение активной смены пользователя"""
        for shift in storage['shifts'].values():
            if shift['user_id'] == user_id and shift['status'] == 'active':
                return shift
        return None
    
    @staticmethod
    def add_car(shift_id, car_number):
        """Добавление машины в смену"""
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
        """Получение информации о машине"""
        return storage['cars'].get(car_id)
    
    @staticmethod
    def add_service_to_car(car_id, service_id, service_name, price, quantity=1):
        """Добавление услуги к машине"""
        # Ищем существующую услугу
        existing_id = None
        for service in storage['car_services'].values():
            if service['car_id'] == car_id and service['service_id'] == service_id:
                existing_id = service['id']
                break
        
        if existing_id:
            # Обновляем количество
            storage['car_services'][existing_id]['quantity'] += quantity
        else:
            # Добавляем новую услугу
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
        
        # Пересчитываем сумму машины
        car_total = 0
        for service in storage['car_services'].values():
            if service['car_id'] == car_id:
                car_total += service['price'] * service['quantity']
        
        storage['cars'][car_id]['total_amount'] = car_total
        return car_total
    
    @staticmethod
    def remove_last_service(car_id):
        """Удаление последней добавленной услуги"""
        # Находим последнюю услугу для этой машины
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
        
        # Пересчитываем сумму машины
        car_total = 0
        for service in storage['car_services'].values():
            if service['car_id'] == car_id:
                car_total += service['price'] * service['quantity']
        
        storage['cars'][car_id]['total_amount'] = car_total
        return car_total
    
    @staticmethod
    def get_car_services(car_id):
        """Получение всех услуг машины"""
        return [s for s in storage['car_services'].values() if s['car_id'] == car_id]
    
    @staticmethod
    def get_shift_cars(shift_id):
        """Получение всех машин в смене"""
        return [c for c in storage['cars'].values() if c['shift_id'] == shift_id]
    
    @staticmethod
    def get_shift_total(shift_id):
        """Подсчёт общей суммы смены"""
        total = 0
        for car in storage['cars'].values():
            if car['shift_id'] == shift_id:
                total += car['total_amount']
        return total
    
    @staticmethod
    def update_shift_total(shift_id):
        """Обновление общей суммы смены"""
        total = DatabaseManager.get_shift_total(shift_id)
        if shift_id in storage['shifts']:
            storage['shifts'][shift_id]['total_amount'] = total
        return total
    
    @staticmethod
    def delete_car(car_id):
        """Удаление машины и всех её услуг"""
        if car_id in storage['cars']:
            shift_id = storage['cars'][car_id]['shift_id']
            
            # Удаляем все услуги машины
            services_to_delete = []
            for service_id, service in storage['car_services'].items():
                if service['car_id'] == car_id:
                    services_to_delete.append(service_id)
            
            for service_id in services_to_delete:
                del storage['car_services'][service_id]
            
            # Удаляем машину
            del storage['cars'][car_id]
            
            # Обновляем сумму смены
            DatabaseManager.update_shift_total(shift_id)
            
            return shift_id
        return None
    
    @staticmethod
    def end_shift(shift_id, end_time=None):
        """Завершение смены"""
        if shift_id in storage['shifts']:
            storage['shifts'][shift_id]['end_time'] = end_time or datetime.now()
            storage['shifts'][shift_id]['status'] = 'completed'
            return storage['shifts'][shift_id]
        return None
    
    @staticmethod
    def get_user_shifts(user_id, limit=10):
        """Получение последних смен пользователя"""
        shifts = []
        for shift in storage['shifts'].values():
            if shift['user_id'] == user_id:
                shifts.append(shift)
        
        # Сортируем по дате создания (новые сначала)
        shifts.sort(key=lambda x: x['created_at'], reverse=True)
        return shifts[:limit]
    
    @staticmethod
    def update_user_setting(telegram_id, setting_name, value):
        """Обновление настроек пользователя"""
        user = DatabaseManager.get_user(telegram_id)
        if user:
            if setting_name == 'daily_target':
                storage['users'][telegram_id]['daily_target'] = int(value)
            elif setting_name == 'progress_bar_enabled':
                storage['users'][telegram_id]['progress_bar_enabled'] = bool(value)
    
    @staticmethod
    def get_user_stats(user_id, days=30):
        """Получение статистики пользователя"""
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

def init_database():
    """Инициализация базы данных (ничего не делает для версии в памяти)"""
    print("✅ Используется хранение данных в памяти")
