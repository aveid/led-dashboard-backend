"""router.py — REST-эндпоинт границы Кыргызстана (prefix /api/geo).

Контракт (SSOT, синхронизируется с фронтендом):
    GET /api/geo/kyrgyzstan → 200 KgBoundaryRead   (JWT; без токена — 401)

Presentation-only: БД не нужна (без `Depends(get_db)`), sync `def`. Данные —
статический ассет `assets/kyrgyzstan_adm0.min.json` (внешний контур КР). Ассет
читается и валидируется ОДИН раз (кэш в памяти) и отдаётся с `Cache-Control`.

Fail-fast: если ассет отсутствует/битый — падаем на ИМПОРТЕ модуля (при старте
приложения), а не 500 в рантайме. Это статика: либо файл есть и валиден, либо
деплой сломан.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, Response

from core.api.auth import get_current_user

from .schemas import BBox, KgBoundaryRead

router = APIRouter(
    prefix="/api/geo",
    tags=["Гео"],
    dependencies=[Depends(get_current_user)],
)

_ASSET = Path(__file__).parent / "assets" / "kyrgyzstan_adm0.min.json"


def _compute_bbox(rings: list[list[list[float]]]) -> BBox:
    """Считает bbox из точек ВСЕХ колец (min/max lng/lat). На бэке — чтобы фронт
    и для рамки, и для маски использовал одни и те же числа."""
    lngs = [pt[0] for ring in rings for pt in ring]
    lats = [pt[1] for ring in rings for pt in ring]
    if not lngs:
        raise ValueError("Гео-ассет КР не содержит точек контура.")
    return BBox(
        min_lng=min(lngs),
        min_lat=min(lats),
        max_lng=max(lngs),
        max_lat=max(lats),
    )


@lru_cache(maxsize=1)
def _load_boundary() -> KgBoundaryRead:
    """Читает ассет один раз, считает bbox из колец и валидирует по контракту."""
    data = json.loads(_ASSET.read_text(encoding="utf-8"))
    return KgBoundaryRead(
        name=data["name"],
        iso3=data["iso3"],
        rings=data["rings"],
        bbox=_compute_bbox(data["rings"]),
    )


# fail-fast на импорте: гарантируем, что ассет есть и валиден при старте.
_load_boundary()


@router.get(
    "/kyrgyzstan",
    response_model=KgBoundaryRead,
    summary="Граница Кыргызстана (bbox + контур)",
)
def get_kyrgyzstan_boundary(response: Response) -> KgBoundaryRead:
    """Отдаёт границу КР — единый источник правды для фронта (рамка карты + маска)."""
    response.headers["Cache-Control"] = "public, max-age=86400"  # статика
    return _load_boundary()
