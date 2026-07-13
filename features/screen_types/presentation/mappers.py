"""mappers.py (presentation) — доменный ScreenType → схема ScreenTypeRead."""

from __future__ import annotations

from features.screen_types.domain.entities import ScreenType

from .schemas import ScreenTypeRead


def screen_type_to_read(screen_type: ScreenType) -> ScreenTypeRead:
    """Доменный ScreenType → схема ответа API.

    created_at/updated_at у сохранённого типа всегда проставлены БД (NOT NULL),
    поэтому здесь они не None.
    """
    return ScreenTypeRead(
        id=screen_type.id,
        name=screen_type.name,
        code=screen_type.code,
        created_at=screen_type.created_at,
        updated_at=screen_type.updated_at,
    )
