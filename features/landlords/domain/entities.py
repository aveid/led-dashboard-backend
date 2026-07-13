"""entities.py — доменная сущность «Арендодатель» (Landlord), FR-8.

За что отвечает модуль:
    Описывает арендодателя — организацию/человека, у которого арендуется экран.
    К экрану привязан один арендодатель (Q2). Здесь только данные и простая
    проверка (имя обязательно); поведение справочника минимально.
"""

from __future__ import annotations

from uuid import UUID

from core.domain.entity import Entity
from core.domain.exceptions import ValidationError


class Landlord(Entity):
    """Арендодатель: название и контактные данные (FR-8.1, FR-8.2)."""

    def __init__(
        self,
        name: str,                 # название организации/имя (FR-8.1)
        contact_person: str = "",  # контактное лицо (FR-8.2)
        phone: str = "",           # телефон (FR-8.2)
        email: str = "",           # email (FR-8.2)
        id: UUID | None = None,
    ) -> None:
        """Создаёт арендодателя и проверяет, что название не пустое."""
        super().__init__(id=id)
        if not name.strip():
            raise ValidationError("У арендодателя должно быть непустое название.")
        self.name = name
        self.contact_person = contact_person
        self.phone = phone
        self.email = email
