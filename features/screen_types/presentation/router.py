"""router.py — REST-эндпоинты справочника типов экрана (prefix /api/screen-types).

Контракт (SSOT, синхронизируется с фронтендом):
    GET    /api/screen-types?search=&page=&per_page=  → 200 {data, meta}
    GET    /api/screen-types/{id}                      → 200 ScreenTypeRead | 404
    POST   /api/screen-types   body:ScreenTypeCreate   → 201 ScreenTypeRead | 422
    PATCH  /api/screen-types/{id} body:ScreenTypeUpdate→ 200 ScreenTypeRead | 404 | 422
    DELETE /api/screen-types/{id}                       → 204 | 404 | 409

Эндпоинты тонкие: вызывают use case / репозиторий и возвращают ответ. Дубликат
name/code → UnprocessableEntityError (422 через глобальный обработчик). Удаление
используемого типа → 409 с машиночитаемым телом (собирается здесь, как у вложений).
Все маршруты защищены JWT.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.api.auth import get_current_user, require_admin
from features.screen_types.application.dto import (
    CreateScreenTypeInput,
    ListScreenTypesInput,
    UpdateScreenTypeInput,
)
from features.screen_types.application.use_cases import (
    CreateScreenTypeUseCase,
    ListScreenTypesUseCase,
    UpdateScreenTypeUseCase,
)
from features.screen_types.domain.exceptions import ScreenTypeInUseError
from features.screen_types.domain.repositories import ScreenTypeRepository

from .deps import get_screen_type_repository
from .mappers import screen_type_to_read
from .schemas import (
    ScreenTypeCreate,
    ScreenTypeListMeta,
    ScreenTypeListResponse,
    ScreenTypeRead,
    ScreenTypeUpdate,
)

router = APIRouter(
    prefix="/api/screen-types",
    tags=["Типы экранов"],
    dependencies=[Depends(get_current_user)],
)

Repo = Annotated[ScreenTypeRepository, Depends(get_screen_type_repository)]


@router.get("", response_model=ScreenTypeListResponse, summary="Список типов экрана")
def list_screen_types(
    repo: Repo,
    search: Annotated[str | None, Query(description="Поиск по названию")] = None,
    page: Annotated[int, Query(ge=1, description="Номер страницы (с 1)")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Размер страницы")] = 20,
) -> ScreenTypeListResponse:
    """Возвращает страницу типов с поиском по названию и метаданными пагинации."""
    result = ListScreenTypesUseCase(repo).execute(
        ListScreenTypesInput(search=search, page=page, per_page=per_page)
    )
    return ScreenTypeListResponse(
        data=[screen_type_to_read(t) for t in result.items],
        meta=ScreenTypeListMeta(
            total=result.total, page=result.page, per_page=result.per_page
        ),
    )


@router.post(
    "",
    response_model=ScreenTypeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать тип экрана",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def create_screen_type(repo: Repo, payload: ScreenTypeCreate) -> ScreenTypeRead:
    """Создаёт новый тип экрана. Дубликат name/code → 422."""
    screen_type = CreateScreenTypeUseCase(repo).execute(
        CreateScreenTypeInput(name=payload.name, code=payload.code)
    )
    return screen_type_to_read(screen_type)


@router.get(
    "/{screen_type_id}", response_model=ScreenTypeRead, summary="Один тип экрана"
)
def get_screen_type(repo: Repo, screen_type_id: int) -> ScreenTypeRead:
    """Возвращает один тип по id. Если нет — 404."""
    return screen_type_to_read(repo.get_by_id(screen_type_id))


@router.patch(
    "/{screen_type_id}",
    response_model=ScreenTypeRead,
    summary="Редактировать тип экрана",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def update_screen_type(
    repo: Repo, screen_type_id: int, payload: ScreenTypeUpdate
) -> ScreenTypeRead:
    """Частично обновляет тип. 404 — если нет, 422 — дубликат name/code."""
    screen_type = UpdateScreenTypeUseCase(repo).execute(
        UpdateScreenTypeInput(
            screen_type_id=screen_type_id, name=payload.name, code=payload.code
        )
    )
    return screen_type_to_read(screen_type)


@router.delete(
    "/{screen_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить тип экрана",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def delete_screen_type(repo: Repo, screen_type_id: int) -> None:
    """Удаляет тип. 404 — если нет; 409 — если на тип ссылаются экраны (§6).

    Тело 409 машиночитаемое (собирается здесь, как ATTACHMENT_LIMIT_EXCEEDED):
    {"code": "screen_type_in_use", "message": ..., "used_by_count": N}.
    """
    try:
        repo.delete(screen_type_id)
    except ScreenTypeInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "screen_type_in_use",
                "message": str(exc),
                "used_by_count": exc.used_by_count,
            },
        ) from exc
