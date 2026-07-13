"""dto.py — DTO прикладного слоя модуля кампаний."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateCampaignInput:
    """Данные для создания кампании (FR-3.10)."""

    name: str


@dataclass(frozen=True)
class UpdateCampaignInput:
    """Данные для редактирования кампании."""

    campaign_id: UUID
    name: str
