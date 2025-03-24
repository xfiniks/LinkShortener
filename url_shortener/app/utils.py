import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_short_code(length: int = settings.DEFAULT_SHORT_CODE_LENGTH) -> str:
    """Генерирует случайный короткий код указанной длины"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет соответствие пароля хешу"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Хеширует пароль"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создает JWT токен доступа"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def build_short_url(short_code: str) -> str:
    """Создает полный короткий URL с базовым URL приложения"""
    return f"{settings.BASE_URL}/{short_code}"

def is_expired(expires_at: Optional[datetime]) -> bool:
    """Проверяет, истек ли срок действия ссылки"""
    if not expires_at:
        return False
    
    now = datetime.now(timezone.utc)
    
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    return now > expires_at

def extract_client_info(request) -> dict:
    """Извлекает информацию о клиенте из запроса"""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "referer": request.headers.get("referer"),
        "timestamp": datetime.now(timezone.utc)
    }