"""entities.py — доменная сущность «Пользователь» (User) и роль (UserRole).

За что отвечает модуль:
    Описывает пользователя системы и его роль в терминах бизнес-правил RBAC
    (NFR-8): ровно две роли — администратор (полный доступ) и наблюдатель
    (только чтение/просмотр/экспорт). Раньше пользователь существовал лишь как
    демо-учётка в настройках; теперь это полноценная доменная сущность.

Здесь только чистый Python: ни FastAPI, ни SQLAlchemy, ни Pydantic (правило
CONTEXT.md — доменный слой остаётся «чистым»). Хеширование пароля — забота
инфраструктуры/приложения; домен хранит только уже готовый `password_hash`.

Об идентификаторе: у пользователей целочисленный автоинкрементный id (маленький
стабильный справочник учёток), поэтому User НЕ наследует базовый Entity (UUID).
Равенство/хеш — по id.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from core.domain.exceptions import ValidationError


class UserRole(str, Enum):
    """Роль пользователя. Значение-строка лежит в JSON и БД как есть.

    ADMIN — полный доступ (любые изменения данных + раздел «Пользователи»).
    USER  — «наблюдатель»: только чтение/просмотр/экспорт, никаких мутаций.
    GUEST — «гость»: доступ как у USER (только чтение/просмотр/экспорт), но на
            выходе роутера ответы редактируются — цены форсятся в null, а
            договор/документы (вложения не-PHOTO) скрыты. Редакция живёт только в
            presentation-слое; домен/сценарии ролью GUEST не параметризуются.
    """

    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"  # NEW


class User:
    """Пользователь системы.

    Поля:
        id            — идентификатор (int). None у ещё не сохранённого.
        username      — логин (уникальный, регистронезависимо, непустой).
        password_hash — хеш пароля (никогда не отдаётся наружу; домен его не считает).
        role          — роль (UserRole). По умолчанию USER.
        is_active     — активен ли пользователь (деактивированный не проходит auth).
        created_at    — момент создания (проставляет БД). None у несохранённого.
    """

    def __init__(
        self,
        username: str,
        password_hash: str,
        role: UserRole = UserRole.USER,
        is_active: bool = True,
        id: int | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Создаёт пользователя, проверяя непустой логин."""
        normalized = username.strip()
        if not normalized:
            raise ValidationError("У пользователя должен быть непустой логин.")
        self.id = id
        self.username = normalized
        self.password_hash = password_hash
        self.role = role
        self.is_active = is_active
        self.created_at = created_at

    @property
    def is_admin(self) -> bool:
        """Активный администратор — единственный, кому разрешены мутации."""
        return self.role is UserRole.ADMIN and self.is_active

    def set_password_hash(self, password_hash: str) -> None:
        """Заменяет хеш пароля (сам хеш считает приложение через hasher)."""
        self.password_hash = password_hash

    def __eq__(self, other: object) -> bool:
        """Пользователи равны, если это User с тем же непустым id."""
        if not isinstance(other, User):
            return NotImplemented
        if self.id is None or other.id is None:
            return self is other
        return self.id == other.id

    def __hash__(self) -> int:
        """Хеш по id — чтобы пользователя можно было класть в set/dict."""
        return hash(self.id)
