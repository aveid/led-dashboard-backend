"""deps.py — зависимости FastAPI модуля городов."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db
from features.cities.domain.repositories import CityRepository
from features.cities.infrastructure.repositories import SqlAlchemyCityRepository


def get_city_repository(db: Annotated[Session, Depends(get_db)]) -> CityRepository:
    """Возвращает репозиторий городов, привязанный к сессии текущего запроса."""
    return SqlAlchemyCityRepository(db)
