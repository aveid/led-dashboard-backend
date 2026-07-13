"""entities.py — доменная сущность «Кампания» (Campaign), FR-3.10.

Кампания — то, что крутится на экране. Простой справочник: id + название.
Связь экран↔кампания (M2M, задел на несколько — Q4) реализована в модуле screens.
"""

from __future__ import annotations

from uuid import UUID

from core.domain.entity import Entity
from core.domain.exceptions import ValidationError


class Campaign(Entity):
    """Рекламная кампания: название (FR-3.10)."""

    def __init__(self, name: str, id: UUID | None = None) -> None:
        """Создаёт кампанию и проверяет, что название не пустое."""
        super().__init__(id=id)
        if not name.strip():
            raise ValidationError("У кампании должно быть непустое название.")
        self.name = name
