"""dto.py — DTO прикладного слоя модуля городов.

Простые неизменяемые контейнеры данных для входа сценариев, отвязанные от HTTP
и БД.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CreateCityInput:
    """Данные для создания города."""

    name: str


@dataclass(frozen=True)
class UpdateCityInput:
    """Данные для редактирования города. None-поля не меняются."""

    city_id: int
    name: str | None = None
    is_active: bool | None = None
