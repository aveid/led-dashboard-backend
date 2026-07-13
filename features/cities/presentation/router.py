"""router.py — REST-эндпоинты справочника городов (prefix /api/cities).

Контракт (SSOT, синхронизируется с фронтендом):
    GET    /api/cities?only_active={bool}   → 200 CityRead[]
    POST   /api/cities   body:CityCreate    → 201 CityRead | 409
    PATCH  /api/cities/{id} body:CityUpdate → 200 CityRead | 404 | 409
    DELETE /api/cities/{id}                 → 204 | 404 | 409

Эндпоинты тонкие: вызывают use case / репозиторий и возвращают ответ.
Дубликат названия и удаление города с экранами → BusinessRuleViolation, который
слой ошибок (core/api/errors.py) переводит в HTTP 409. Все маршруты защищены JWT.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from core.api.auth import get_current_user, require_admin
from features.cities.application.dto import CreateCityInput, UpdateCityInput
from features.cities.application.use_cases import (
    CreateCityUseCase,
    ListCitiesUseCase,
    UpdateCityUseCase,
)
from features.cities.domain.repositories import CityRepository

from .deps import get_city_repository
from .mappers import city_to_read
from .schemas import CityCreate, CityRead, CityUpdate

router = APIRouter(
    prefix="/api/cities",
    tags=["Города"],
    dependencies=[Depends(get_current_user)],
)

Repo = Annotated[CityRepository, Depends(get_city_repository)]


@router.get("", response_model=list[CityRead], summary="Список городов")
def list_cities(repo: Repo, only_active: bool = False) -> list[CityRead]:
    """Возвращает города с числом привязанных экранов (при only_active — только активные)."""
    rows = ListCitiesUseCase(repo).execute(only_active)
    return [city_to_read(row.city, screens_count=row.screens_count) for row in rows]


@router.post(
    "",
    response_model=CityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать город",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def create_city(repo: Repo, payload: CityCreate) -> CityRead:
    """Создаёт новый город. Дубликат названия → 409."""
    city = CreateCityUseCase(repo).execute(CreateCityInput(name=payload.name))
    # У нового города экранов ещё нет.
    return city_to_read(city, screens_count=0)


@router.patch(
    "/{city_id}",
    response_model=CityRead,
    summary="Редактировать город",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def update_city(repo: Repo, city_id: int, payload: CityUpdate) -> CityRead:
    """Частично обновляет город. 404 — если нет, 409 — дубликат названия."""
    data = UpdateCityInput(city_id=city_id, name=payload.name, is_active=payload.is_active)
    city = UpdateCityUseCase(repo).execute(data)
    return city_to_read(city, screens_count=repo.count_screens(city_id))


@router.delete(
    "/{city_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить город",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def delete_city(repo: Repo, city_id: int) -> None:
    """Удаляет город. 404 — если нет, 409 — если к городу привязаны экраны."""
    repo.delete(city_id)
