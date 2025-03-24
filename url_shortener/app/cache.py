import json
import redis
import hashlib
from app.config import settings
from app.json_utils import dumps, loads

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

URL_CACHE_PREFIX = "url:"  # Для кеширования соответствия short_code -> original_url
STATS_CACHE_PREFIX = "stats:"  # Для кеширования статистики ссылок
SEARCH_CACHE_PREFIX = "search:"  # Для кеширования результатов поиска

def get_url_cache_key(short_code: str) -> str:
    """Формирует ключ кеша для короткого кода"""
    return f"{URL_CACHE_PREFIX}{short_code}"

def get_stats_cache_key(short_code: str) -> str:
    """Формирует ключ кеша для статистики ссылки"""
    return f"{STATS_CACHE_PREFIX}{short_code}"

def get_search_cache_key(original_url: str) -> str:
    """Формирует ключ кеша для поиска ссылки по оригинальному URL"""
    url_hash = hashlib.md5(original_url.encode()).hexdigest()
    return f"{SEARCH_CACHE_PREFIX}{url_hash}"

def cache_url(short_code: str, original_url: str, expire: int = settings.CACHE_EXPIRY) -> None:
    """Кеширует соответствие короткого кода оригинальному URL"""
    key = get_url_cache_key(short_code)
    redis_client.set(key, original_url, ex=expire)

def get_cached_url(short_code: str) -> str:
    """Получает оригинальный URL из кеша по короткому коду"""
    key = get_url_cache_key(short_code)
    return redis_client.get(key)

def cache_stats(short_code: str, stats_data: dict, expire: int = settings.CACHE_EXPIRY) -> None:
    """Кеширует статистику ссылки"""
    key = get_stats_cache_key(short_code)
    redis_client.set(key, dumps(stats_data), ex=expire)

def get_cached_stats(short_code: str) -> dict:
    """Получает статистику ссылки из кеша"""
    key = get_stats_cache_key(short_code)
    data = redis_client.get(key)
    return loads(data) if data else None

def cache_search_result(original_url: str, short_code: str, expire: int = settings.CACHE_EXPIRY) -> None:
    """Кеширует результат поиска по оригинальному URL"""
    key = get_search_cache_key(original_url)
    redis_client.set(key, dumps({"short_code": short_code}), ex=expire)

def get_cached_search_result(original_url: str) -> str:
    """Получает короткий код из кеша по оригинальному URL"""
    key = get_search_cache_key(original_url)
    return redis_client.get(key)

def invalidate_stats_cache(short_code: str) -> None:
    """Инвалидирует только кеш статистики"""
    key = get_stats_cache_key(short_code)
    redis_client.delete(key)

def invalidate_url_cache(short_code: str) -> None:
    """Инвалидирует кеш URL при обновлении или удалении"""
    keys = [
        get_url_cache_key(short_code),
        get_stats_cache_key(short_code)
    ]

    if keys:
        redis_client.delete(*keys)
    
def increment_click_count(short_code: str) -> int:
    """Инкрементирует счетчик кликов в кеше"""
    key = f"clicks:{short_code}"
    return redis_client.incr(key)

def get_cached_click_count(short_code: str) -> int:
    """Получает количество кликов из кеша"""
    key = f"clicks:{short_code}"
    count = redis_client.get(key)
    return int(count) if count else 0

def add_popular_url(short_code: str) -> None:
    """Добавляет URL в список популярных"""
    redis_client.sadd("popular_urls", short_code)

def is_popular_url(short_code: str) -> bool:
    """Проверяет, является ли URL популярным"""
    return redis_client.sismember("popular_urls", short_code)

def check_and_update_popularity(short_code: str, click_count: int) -> None:
    """Проверяет популярность ссылки и обновляет кеш если нужно"""
    if click_count >= settings.POPULAR_URL_THRESHOLD and not is_popular_url(short_code):
        add_popular_url(short_code)