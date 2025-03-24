import json
import redis
import hashlib
from app.config import settings
from app.json_utils import dumps, loads
from typing import Optional
from datetime import datetime, timezone

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

URL_CACHE_PREFIX = "url:"  # Для кеширования соответствия short_code -> original_url

def get_url_cache_key(short_code: str) -> str:
    """Формирует ключ кеша для короткого кода"""
    return f"{URL_CACHE_PREFIX}{short_code}"

def get_cached_url(short_code: str) -> str:
    """Получает оригинальный URL из кеша по короткому коду"""
    key = get_url_cache_key(short_code)
    return redis_client.get(key)

def invalidate_url_cache(short_code: str) -> None:
    """Инвалидирует кеш URL при обновлении или удалении"""
    keys = [
        get_url_cache_key(short_code)
    ]

    if keys:
        redis_client.delete(*keys)
    
def add_popular_url(short_code: str) -> None:
    """Добавляет URL в список популярных"""
    redis_client.sadd("popular_urls", short_code)

def is_popular_url(short_code: str) -> bool:
    """Проверяет, является ли URL популярным"""
    return redis_client.sismember("popular_urls", short_code)

def increment_access_counter(short_code: str) -> int:
    """Инкрементирует счетчик доступов и отмечает для синхронизации"""
    counter_key = f"clicks:{short_code}"
    count = redis_client.incr(counter_key)
    
    last_access_key = f"last_access:{short_code}"
    redis_client.set(last_access_key, datetime.now(timezone.utc).isoformat())
    
    redis_client.sadd("links_to_sync", short_code)
    
    return count

def get_links_to_sync() -> set:
    """Получает множество ссылок, требующих синхронизации"""
    return redis_client.smembers("links_to_sync")

def get_buffered_clicks(short_code: str) -> int:
    """Получает количество буферизованных кликов из Redis"""
    counter_key = f"clicks:{short_code}"
    count = redis_client.get(counter_key)
    return int(count) if count else 0

def get_buffered_last_access(short_code: str) -> Optional[datetime]:
    """Получает буферизованное время последнего доступа из Redis"""
    last_access_key = f"last_access:{short_code}"
    last_access_str = redis_client.get(last_access_key)
    if last_access_str:
        try:
            return datetime.fromisoformat(last_access_str)
        except ValueError:
            return None
    return None

def reset_buffered_stats(short_code: str) -> None:
    """Сбрасывает буферизованную статистику для ссылки"""
    counter_key = f"clicks:{short_code}"
    last_access_key = f"last_access:{short_code}"
    redis_client.delete(counter_key, last_access_key)
    redis_client.srem("links_to_sync", short_code)

def add_click_details(short_code: str, client_info: dict) -> None:
    """Добавляет информацию о клике в список ожидающих"""
    click_data = {
        "short_code": short_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_address": client_info.get("ip_address", ""),
        "user_agent": client_info.get("user_agent", ""),
        "referer": client_info.get("referer", "")
    }
    redis_client.lpush(f"click_details:{short_code}", json.dumps(click_data))

def get_and_clear_click_details(short_code: str, limit: int = 100) -> list:
    """Получает и удаляет информацию о кликах"""
    key = f"click_details:{short_code}"
    details = []
    
    for _ in range(limit):
        data = redis_client.rpop(key)
        if not data:
            break
        try:
            details.append(json.loads(data))
        except json.JSONDecodeError:
            continue
    
    return details

def cache_url(short_code: str, original_url: str, expire: Optional[int] = None) -> None:
    """Кеширует соответствие короткого кода оригинальному URL с опциональным TTL"""
    key = get_url_cache_key(short_code)
    if expire:
        redis_client.set(key, original_url, ex=expire)
    else:
        redis_client.set(key, original_url, ex=settings.CACHE_EXPIRY)