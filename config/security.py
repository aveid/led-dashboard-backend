"""security.py — безопасность: хеширование паролей и JWT-токены.

За что отвечает модуль:
    • хеширует и проверяет пароли (bcrypt через passlib);
    • выпускает и декодирует JWT access-токены.

Это инфраструктурная деталь: домен о JWT ничего не знает. Модуль используется
слоем представления (эндпоинт входа выдаёт токен, зависимость проверяет его).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from config.settings import get_settings

_settings = get_settings()

# Контекст хеширования паролей. bcrypt — надёжный медленный алгоритм (защита от перебора).
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Возвращает безопасный хеш пароля для хранения (никогда не храним пароль как есть)."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет, соответствует ли введённый пароль сохранённому хешу."""
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """Создаёт JWT access-токен для пользователя (subject — обычно логин/идентификатор).

    В токен кладём субъект (sub) и время истечения (exp). Подпись — секретом из
    настроек. Токен затем присылается клиентом в заголовке Authorization: Bearer.
    """
    expire = datetime.now(UTC) + timedelta(minutes=_settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, _settings.secret_key, algorithm=_settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Проверяет токен и возвращает субъект (sub). Бросает исключение, если токен невалиден.

    Ошибку декодирования ловит слой представления и превращает в HTTP 401.
    """
    payload = jwt.decode(token, _settings.secret_key, algorithms=[_settings.jwt_algorithm])
    return str(payload["sub"])
