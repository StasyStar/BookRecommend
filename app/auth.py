import hashlib
import secrets
from datetime import datetime, timedelta, timezone


def get_password_hash(password: str) -> str:
    """Простое хэширование пароля для демонстрации"""
    salt = "book_recommendation_salt"
    return hashlib.sha256((password + salt).encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return get_password_hash(plain_password) == hashed_password


def generate_session_token() -> str:
    """Генерация уникального токена сессии"""
    return secrets.token_urlsafe(32)


def get_session_expiry() -> datetime:
    """Время истечения сессии (7 дней)"""
    return datetime.now(timezone.utc) + timedelta(days=7)
