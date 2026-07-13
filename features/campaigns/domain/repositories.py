"""repositories.py — порт (интерфейс) репозитория кампаний."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from .entities import Campaign


class CampaignRepository(ABC):
    """Контракт хранилища кампаний."""

    @abstractmethod
    def get_by_id(self, campaign_id: UUID) -> Campaign:
        """Вернуть кампанию по id или бросить NotFoundError."""
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[Campaign]:
        """Вернуть все кампании (для справочника)."""
        raise NotImplementedError

    @abstractmethod
    def add(self, campaign: Campaign) -> Campaign:
        """Сохранить новую кампанию и вернуть её (с присвоенным id)."""
        raise NotImplementedError

    @abstractmethod
    def update(self, campaign: Campaign) -> Campaign:
        """Сохранить изменения существующей кампании."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, campaign_id: UUID) -> None:
        """Удалить кампанию по id."""
        raise NotImplementedError
