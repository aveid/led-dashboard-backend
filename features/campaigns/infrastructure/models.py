"""models.py — ORM-модель кампании (таблица campaigns).

Владелец таблицы campaigns — этот модуль. Таблица-связка screen_campaigns
(M2M с экранами) объявлена в модуле screens (там, где живёт агрегат Screen),
и ссылается на campaigns.id по имени таблицы, не импортируя эту модель.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class CampaignModel(Base):
    """Таблица рекламных кампаний (FR-3.10)."""

    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
