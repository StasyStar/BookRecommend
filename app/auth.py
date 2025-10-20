import hashlib
import secrets
from datetime import datetime, timedelta, timezone


def get_password_hash(password: str) -> str:
    """Простое хеширование пароля для демонстрации"""
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


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Проверка сложности пароля"""
    if len(password) < 6:
        return False, "Пароль должен содержать минимум 6 символов"

    if len(password) > 50:
        return False, "Пароль слишком длинный"

    if not any(char.isdigit() for char in password):
        return False, "Пароль должен содержать хотя бы одну цифру"

    if not any(char.isalpha() for char in password):
        return False, "Пароль должен содержать хотя бы одну букву"

    return True, "Пароль надежен"
