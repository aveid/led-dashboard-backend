"""deps.py — зависимости FastAPI модуля кампаний."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db
from features.campaigns.domain.repositories import CampaignRepository
from features.campaigns.infrastructure.repositories import SqlAlchemyCampaignRepository


def get_campaign_repository(db: Annotated[Session, Depends(get_db)]) -> CampaignRepository:
    """Возвращает репозиторий кампаний, привязанный к сессии текущего запроса."""
    return SqlAlchemyCampaignRepository(db)
