"""mappers.py — преобразование ORM-модели города в доменную сущность."""

from __future__ import annotations

from features.cities.domain.entities import City

from .models import CityModel


def city_to_domain(model: CityModel) -> City:
    """Строка cities (ORM) → доменный City."""
    return City(
        name=model.name,
        is_active=model.is_active,
        id=model.id,
    )
