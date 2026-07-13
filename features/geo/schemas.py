"""schemas.py — Pydantic-схемы гео-фичи (OpenAPI SSOT для фронта).

Контракт `GET /api/geo/kyrgyzstan`. Координаты — пары `[lng, lat]`, тип `float`
(порядок как у `POINT(lng lat)`; правило «деньги только Decimal» на гео НЕ
распространяется). Ключи — snake_case (конвенция проекта).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Габаритная рамка границы (min/max по lng/lat). Авторитетна для фронта:
    используется и как `CameraConstraint.contain`, и для маски «затемнить всё,
    кроме КР» — фронт берёт ОДНИ и те же числа. Считается на бэке из точек колец.
    """

    min_lng: float
    min_lat: float
    max_lng: float
    max_lat: float


class KgBoundaryRead(BaseModel):
    """Граница Кыргызстана: bbox + контур (`rings`).

    `rings` — список колец; `rings[0]` — внешний контур, доп. элементы (если есть)
    — части мультиполигона. Каждый inner-элемент кольца = пара `[lng, lat]` (float).
    Кольцо может быть НЕ замкнуто (последняя точка ≠ первой) — потребитель
    замыкает сам. Внутренние анклавы/эксклавы в контур не входят (только внешний).
    """

    name: str
    iso3: str
    bbox: BBox
    rings: list[list[list[float]]] = Field(
        description="Список колец; каждый элемент кольца = [lng, lat]. rings[0] — внешний контур."
    )
