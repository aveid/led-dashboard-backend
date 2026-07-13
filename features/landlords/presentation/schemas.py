"""schemas.py — Pydantic-схемы (контракты HTTP) модуля арендодателей."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class LandlordCreate(BaseModel):
    """Тело запроса на создание арендодателя (FR-8)."""

    name: str
    contact_person: str = ""
    phone: str = ""
    email: str = ""


class LandlordUpdate(BaseModel):
    """Тело запроса на редактирование арендодателя. Все поля необязательны."""

    name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None


class LandlordRead(BaseModel):
    """Арендодатель в ответе API."""

    id: UUID
    name: str
    contact_person: str
    phone: str
    email: str
