"""schemas.py — Pydantic-схемы (контракты HTTP) модуля городов.

Контракт (SSOT для фронтенда):
    CityRead   = { id, name, is_active, screens_count }
    CityCreate = { name }
    CityUpdate = { name?, is_active? }
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CityRead(BaseModel):
    """Город в ответе API. screens_count — число привязанных экранов."""

    id: int
    name: str
    is_active: bool
    screens_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class CityCreate(BaseModel):
    """Тело запроса на создание города."""

    name: str = Field(min_length=1, max_length=120)


class CityUpdate(BaseModel):
    """Тело запроса на редактирование города. Все поля необязательны."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
