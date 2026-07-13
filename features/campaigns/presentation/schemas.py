"""schemas.py — Pydantic-схемы (контракты HTTP) модуля кампаний."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class CampaignCreate(BaseModel):
    """Тело запроса на создание кампании (FR-3.10)."""

    name: str


class CampaignUpdate(BaseModel):
    """Тело запроса на переименование кампании."""

    name: str


class CampaignRead(BaseModel):
    """Кампания в ответе API."""

    id: UUID
    name: str
