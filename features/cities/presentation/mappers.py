"""mappers.py (presentation) — доменный City → схема CityRead."""

from __future__ import annotations

from features.cities.domain.entities import City

from .schemas import CityRead


def city_to_read(city: City, screens_count: int = 0) -> CityRead:
    """Доменный City → схема ответа API.

    screens_count передаётся отдельно (это агрегат из запроса, не поле сущности);
    по умолчанию 0 — например, когда город отдаётся вложенным в карточку экрана.
    """
    return CityRead(
        id=city.id,
        name=city.name,
        is_active=city.is_active,
        screens_count=screens_count,
    )
