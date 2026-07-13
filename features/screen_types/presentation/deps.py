"""deps.py — зависимости FastAPI справочника типов экрана."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db
from features.screen_types.domain.repositories import ScreenTypeRepository
from features.screen_types.infrastructure.repositories import (
    SqlAlchemyScreenTypeRepository,
)


def get_screen_type_repository(
    db: Annotated[Session, Depends(get_db)],
) -> ScreenTypeRepository:
    """Возвращает репозиторий типов экрана, привязанный к сессии текущего запроса."""
    return SqlAlchemyScreenTypeRepository(db)
