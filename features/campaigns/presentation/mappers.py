"""mappers.py (presentation) — доменная Campaign → схема CampaignRead."""

from __future__ import annotations

from features.campaigns.domain.entities import Campaign

from .schemas import CampaignRead


def campaign_to_read(campaign: Campaign) -> CampaignRead:
    """Доменная Campaign → схема ответа API."""
    return CampaignRead(id=campaign.id, name=campaign.name)
