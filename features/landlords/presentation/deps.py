"""deps.py — зависимости FastAPI модуля арендодателей."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db
from features.landlords.domain.repositories import LandlordRepository
from features.landlords.infrastructure.repositories import SqlAlchemyLandlordRepository


def get_landlord_repository(db: Annotated[Session, Depends(get_db)]) -> LandlordRepository:
    """Возвращает репозиторий арендодателей, привязанный к сессии текущего запроса."""
    return SqlAlchemyLandlordRepository(db)
