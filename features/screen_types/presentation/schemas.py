"""schemas.py — Pydantic-схемы (контракты HTTP) справочника типов экрана.

Контракт (SSOT для фронтенда, snake_case — конвенция проекта):
    ScreenTypeRead     = { id, name, code, created_at, updated_at }
    ScreenTypeCreate   = { name, code? }
    ScreenTypeUpdate   = { name?, code? }
    ScreenTypeListResponse = { data: ScreenTypeRead[], meta: {total, page, per_page} }

Тот же ScreenTypeRead отдаётся и вложенным в карточку экрана (screen.screen_type).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Машинный код: строчные латинские буквы/цифры/`_`/`-`, до 50 символов (§5).
_CODE_PATTERN = r"^[a-z0-9_-]+$"


class ScreenTypeRead(BaseModel):
    """Тип экрана в ответе API."""

    id: int
    name: str
    code: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScreenTypeCreate(BaseModel):
    """Тело запроса на создание типа. code необязателен."""

    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50, pattern=_CODE_PATTERN)


class ScreenTypeUpdate(BaseModel):
    """Тело запроса на редактирование типа. Все поля необязательны."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50, pattern=_CODE_PATTERN)


class ScreenTypeListMeta(BaseModel):
    """Метаданные пагинации списка типов."""

    total: int
    page: int
    per_page: int


class ScreenTypeListResponse(BaseModel):
    """Ответ списка типов: страница данных + метаданные пагинации."""

    data: list[ScreenTypeRead]
    meta: ScreenTypeListMeta
