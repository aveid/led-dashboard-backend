"""auth.py — общие зависимости аутентификации и авторизации для всех модулей.

За что отвечает:
    • get_current_user — проверяет JWT и загружает АКТУАЛЬНОГО пользователя из БД
      (не только из claim токена), возвращая доменную сущность User с ролью и
      признаком активности. Деактивированный пользователь не проходит (→ 401).
    • require_admin — гейт «только администратор» для мутаций и раздела users
      (не-admin → 403 ADMIN_ONLY). Роль берётся из свежей записи БД, поэтому
      понижение/деактивация действуют немедленно, даже если старый токен ещё жив.

Вынесено в core, чтобы любой модуль (screens, landlords, campaigns, users)
защищал маршруты одинаково, не завися друг от друга. Роль в JWT НЕ кладём —
авторитет всегда за БД (иначе понижение роли не действовало бы до истечения токена).

"""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from config.database import get_db
from config.security import decode_access_token
from features.users.domain.entities import User, UserRole
from features.users.infrastructure.repositories import SqlAlchemyUserRepository

# Клиент присылает Bearer-токен; tokenUrl — эндпоинт получения токена.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

_INVALID_TOKEN = "Недействительный или просроченный токен."


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Проверяет токен и возвращает АКТИВНОГО пользователя из БД. Иначе 401.

    Роль/активность резолвятся из свежей записи, а не из токена: деактивированный
    или удалённый пользователь получает 401, даже если предъявил ещё живой токен.
    """
    try:
        username = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = SqlAlchemyUserRepository(db).get_by_username(username)
    if user is None or not user.is_active:
        # Пользователь удалён/деактивирован → токен больше не действителен.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Гейт «только администратор»: не-admin → 403 ADMIN_ONLY (не 401 — не разлогинивает).

    403 ≠ 401: токен валиден, пользователь аутентифицирован, но прав недостаточно.
    Фронт по 403 НЕ должен разлогинивать (важно для UX). Роль — из свежей записи БД.
    """
    if current_user.role is not UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ADMIN_ONLY", "message": "Требуются права администратора"},
        )
    return current_user


def require_non_guest(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Гейт «недоступно гостю»: роль guest → 403 GUEST_FORBIDDEN (не 401 — не разлогинивает).

    Строится поверх get_current_user (свежая запись БД), поэтому демоут admin/user →
    guest действует немедленно, как и для require_admin. 403 ≠ 401: токен валиден, но
    раздел закрыт для гостевой роли — фронтовый интерсептор по 403 не разлогинивает.
    Зависимость сознательно generic — переиспользуема на будущих guest-запрещённых ридах.
    """
    if current_user.role is UserRole.GUEST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "GUEST_FORBIDDEN", "message": "Раздел недоступен для гостевой роли"},
        )
    return current_user
