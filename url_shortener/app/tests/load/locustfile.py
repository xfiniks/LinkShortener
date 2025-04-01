from locust import HttpUser, task, between, events
import random
import string
import json
import time
from datetime import datetime

results = {
    "NoCacheUser": {"response_times": [], "total_time": 0, "request_count": 0},
    "CacheUser": {"response_times": [], "total_time": 0, "request_count": 0}
}

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("Начало тестирования эффективности кеширования...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n=== Результаты тестирования кеширования ===")
    
    for user_type, data in results.items():
        if data["request_count"] > 0:
            avg_time = data["total_time"] / data["request_count"]
            print(f"\n{user_type}:")
            print(f"Общее количество запросов: {data['request_count']}")
            print(f"Среднее время ответа: {avg_time:.4f} сек")
            
            sorted_times = sorted(data["response_times"])
            p50 = sorted_times[int(len(sorted_times) * 0.5)] if sorted_times else 0
            p95 = sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0
            p99 = sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0
            
            print(f"P50 (медиана): {p50:.4f} сек")
            print(f"P95: {p95:.4f} сек")
            print(f"P99: {p99:.4f} сек")
    
    if results["NoCacheUser"]["request_count"] > 0 and results["CacheUser"]["request_count"] > 0:
        no_cache_avg = results["NoCacheUser"]["total_time"] / results["NoCacheUser"]["request_count"]
        cache_avg = results["CacheUser"]["total_time"] / results["CacheUser"]["request_count"]
        
        improvement = ((no_cache_avg - cache_avg) / no_cache_avg) * 100
        print(f"\nУлучшение производительности благодаря кешированию: {improvement:.2f}%")


class NoCacheUser(HttpUser):    
    wait_time = between(0.5, 1.5)
    
    def on_start(self):
        # Логин и получение токена
        self.login()
        # Хранилище для коротких кодов
        self.short_codes = []
    
    def login(self):
        # Регистрация пользователя с уникальным именем
        username = f"nocache_{random.randint(1000, 9999)}"
        self.client.post(
            "/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "password123"
            }
        )
        
        # Логин для получения токена
        response = self.client.post(
            "/auth/token",
            data={
                "username": username,
                "password": "password123"
            }
        )
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
        else:
            self.token = None
    
    @task
    def create_and_access_short_link(self):
        # Генерация случайного URL
        random_path = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        original_url = f"https://example.com/nocache/{random_path}/{datetime.now().timestamp()}"
        
        # Создание короткой ссылки
        create_start = time.time()
        response = self.client.post(
            "/links/shorten",
            json={"original_url": original_url},
            headers={"Authorization": f"Bearer {self.token}"}
        )
        create_time = time.time() - create_start
        
        if response.status_code == 201:
            short_code = response.json()["short_code"]
            self.short_codes.append(short_code)
            
            # Замер времени доступа
            access_start = time.time()
            self.client.get(f"/{short_code}", allow_redirects=False)
            access_time = time.time() - access_start
            
            # Сохранение результатов
            results["NoCacheUser"]["response_times"].append(access_time)
            results["NoCacheUser"]["total_time"] += access_time
            results["NoCacheUser"]["request_count"] += 1
            
            # Ограничение количества хранимых кодов
            if len(self.short_codes) > 20:
                self.short_codes = self.short_codes[-20:]


class CacheUser(HttpUser):    
    wait_time = between(0.5, 1.5)
    
    def on_start(self):
        # Логин и получение токена
        self.login()
        
        # Создание нескольких фиксированных ссылок для тестирования кеширования
        self.short_codes = []
        for i in range(5):
            response = self.client.post(
                "/links/shorten",
                json={"original_url": f"https://example.com/cache/page{i}"},
                headers={"Authorization": f"Bearer {self.token}"}
            )
            if response.status_code == 201:
                self.short_codes.append(response.json()["short_code"])
        
        # Пре-доступ к ссылкам для их кеширования 
        # (согласно текущей имплементации, ссылка кешируется 
        # после достижения settings.POPULAR_URL_THRESHOLD обращений)
        for short_code in self.short_codes:
            for _ in range(15):  # Предполагая, что POPULAR_URL_THRESHOLD = 10
                self.client.get(f"/{short_code}", allow_redirects=False)
    
    def login(self):
        # Регистрация пользователя с уникальным именем
        username = f"cache_{random.randint(1000, 9999)}"
        self.client.post(
            "/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "password123"
            }
        )
        
        # Логин для получения токена
        response = self.client.post(
            "/auth/token",
            data={
                "username": username,
                "password": "password123"
            }
        )
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
        else:
            self.token = None
    
    @task
    def access_cached_link(self):
        if self.short_codes:
            # Выбор случайной короткой ссылки из фиксированного набора
            short_code = random.choice(self.short_codes)
            
            # Замер времени доступа
            access_start = time.time()
            self.client.get(f"/{short_code}", allow_redirects=False)
            access_time = time.time() - access_start
            
            # Сохранение результатов
            results["CacheUser"]["response_times"].append(access_time)
            results["CacheUser"]["total_time"] += access_time
            results["CacheUser"]["request_count"] += 1