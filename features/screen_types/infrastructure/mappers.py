"""mappers.py — преобразование ORM-модели типа экрана в доменную сущность."""

from __future__ import annotations

from features.screen_types.domain.entities import ScreenType

from .models import ScreenTypeModel


def screen_type_to_domain(model: ScreenTypeModel) -> ScreenType:
    """Строка screen_types (ORM) → доменный ScreenType."""
    return ScreenType(
        name=model.name,
        code=model.code,
        created_at=model.created_at,
        updated_at=model.updated_at,
        id=model.id,
    )
