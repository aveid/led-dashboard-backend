"""repositories.py — реализация CampaignRepository на SQLAlchemy."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.domain.exceptions import NotFoundError
from features.campaigns.domain.entities import Campaign
from features.campaigns.domain.repositories import CampaignRepository

from .mappers import campaign_to_domain
from .models import CampaignModel


class SqlAlchemyCampaignRepository(CampaignRepository):
    """Хранилище кампаний поверх SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Получает сессию БД (внедряется на время HTTP-запроса)."""
        self._session = session

    def get_by_id(self, campaign_id: UUID) -> Campaign:
        """Возвращает кампанию по id или бросает NotFoundError (→ 404)."""
        model = self._session.get(CampaignModel, campaign_id)
        if model is None:
            raise NotFoundError(f"Кампания с id={campaign_id} не найдена.")
        return campaign_to_domain(model)

    def list(self) -> list[Campaign]:
        """Возвращает все кампании, отсортированные по названию."""
        stmt = select(CampaignModel).order_by(CampaignModel.name)
        return [campaign_to_domain(m) for m in self._session.scalars(stmt).all()]

    def add(self, campaign: Campaign) -> Campaign:
        """Сохраняет новую кампанию и возвращает её с присвоенным id."""
        model = CampaignModel(name=campaign.name)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return campaign_to_domain(model)

    def update(self, campaign: Campaign) -> Campaign:
        """Обновляет существующую кампанию."""
        model = self._session.get(CampaignModel, campaign.id)
        if model is None:
            raise NotFoundError(f"Кампания с id={campaign.id} не найдена.")
        model.name = campaign.name
        self._session.commit()
        self._session.refresh(model)
        return campaign_to_domain(model)

    def delete(self, campaign_id: UUID) -> None:
        """Удаляет кампанию по id.

        Связь со screen_campaigns удалится каскадно (ondelete=CASCADE на FK
        campaign_id в таблице-связке) — экраны при этом не удаляются.
        """
        model = self._session.get(CampaignModel, campaign_id)
        if model is None:
            raise NotFoundError(f"Кампания с id={campaign_id} не найдена.")
        self._session.delete(model)
        self._session.commit()
