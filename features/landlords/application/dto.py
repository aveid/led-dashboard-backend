"""dto.py — DTO прикладного слоя модуля арендодателей.

Простые контейнеры данных для входа сценариев, отвязанные от HTTP и БД.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateLandlordInput:
    """Данные для создания арендодателя (FR-8)."""

    name: str
    contact_person: str = ""
    phone: str = ""
    email: str = ""


@dataclass(frozen=True)
class UpdateLandlordInput:
    """Данные для редактирования арендодателя. None-поля не меняются."""

    landlord_id: UUID
    name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
