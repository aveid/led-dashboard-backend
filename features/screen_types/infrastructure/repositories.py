"""repositories.py — реализация ScreenTypeRepository на SQLAlchemy.

Работа с таблицей screen_types. Наружу отдаёт доменные сущности ScreenType.
Конфликты уникальности (name/code) переводятся в UnprocessableEntityError (→ 422,
по контракту §5), а запрет удаления используемого типа — в ScreenTypeInUseError
(→ 409, §6). Число ссылающихся экранов считается по таблице screens.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.domain.exceptions import NotFoundError, UnprocessableEntityError
from features.screen_types.domain.entities import ScreenType
from features.screen_types.domain.exceptions import ScreenTypeInUseError
from features.screen_types.domain.repositories import ScreenTypeRepository
from features.screens.infrastructure.models import ScreenModel

from .mappers import screen_type_to_domain
from .models import ScreenTypeModel

# Единые сообщения о конфликте уникальности (для POST и PATCH).
_DUPLICATE_NAME_MESSAGE = "Тип экрана с таким названием уже существует"
_DUPLICATE_CODE_MESSAGE = "Тип экрана с таким кодом уже существует"


class SqlAlchemyScreenTypeRepository(ScreenTypeRepository):
    """Хранилище типов экрана поверх SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Получает сессию БД (внедряется на время HTTP-запроса)."""
        self._session = session

    def list_paginated(
        self, search: str | None, limit: int, offset: int
    ) -> tuple[list[ScreenType], int]:
        """Возвращает страницу типов и общее число подходящих записей.

        Поиск по name — регистронезависимая подстрока (ILIKE). total считается по
        тому же фильтру, но без limit/offset (для meta.total на фронте).
        """
        conditions = []
        if search:
            conditions.append(ScreenTypeModel.name.ilike(f"%{search}%"))

        total = self._session.scalar(
            select(func.count()).select_from(ScreenTypeModel).where(*conditions)
        )

        stmt = (
            select(ScreenTypeModel)
            .where(*conditions)
            .order_by(ScreenTypeModel.name)
            .limit(limit)
            .offset(offset)
        )
        models = self._session.scalars(stmt).all()
        return [screen_type_to_domain(m) for m in models], int(total or 0)

    def get_by_id(self, screen_type_id: int) -> ScreenType:
        """Возвращает тип по id или бросает NotFoundError (→ 404)."""
        model = self._session.get(ScreenTypeModel, screen_type_id)
        if model is None:
            raise NotFoundError(f"Тип экрана с id={screen_type_id} не найден.")
        return screen_type_to_domain(model)

    def exists(self, screen_type_id: int) -> bool:
        """Проверяет наличие типа по id (для валидации screen_type_id у экрана)."""
        return self._session.get(ScreenTypeModel, screen_type_id) is not None

    def add(self, screen_type: ScreenType) -> ScreenType:
        """Сохраняет новый тип; дубликат name/code → UnprocessableEntityError (422)."""
        self._guard_unique(screen_type)
        model = ScreenTypeModel(name=screen_type.name, code=screen_type.code)
        self._session.add(model)
        self._commit_unique(model)
        self._session.refresh(model)
        return screen_type_to_domain(model)

    def update(self, screen_type: ScreenType) -> ScreenType:
        """Обновляет тип; дубликат name/code → UnprocessableEntityError (422)."""
        model = self._session.get(ScreenTypeModel, screen_type.id)
        if model is None:
            raise NotFoundError(f"Тип экрана с id={screen_type.id} не найден.")
        self._guard_unique(screen_type, exclude_id=screen_type.id)
        model.name = screen_type.name
        model.code = screen_type.code
        self._commit_unique(model)
        self._session.refresh(model)
        return screen_type_to_domain(model)

    def delete(self, screen_type_id: int) -> None:
        """Удаляет тип. 404 — если нет; 409 (ScreenTypeInUseError) — если используется.

        Предпроверка COUNT(screens) даёт понятную ошибку с числом ссылок; на уровне
        БД тем же барьером стоит внешний ключ screens.screen_type_id ON DELETE RESTRICT.
        """
        model = self._session.get(ScreenTypeModel, screen_type_id)
        if model is None:
            raise NotFoundError(f"Тип экрана с id={screen_type_id} не найден.")
        used_by = self._count_screens(screen_type_id)
        if used_by > 0:
            raise ScreenTypeInUseError(used_by_count=used_by)
        self._session.delete(model)
        self._session.commit()

    # --- Вспомогательные методы ---

    def _count_screens(self, screen_type_id: int) -> int:
        """Число экранов, ссылающихся на тип (для запрета удаления, §6)."""
        stmt = select(func.count()).select_from(ScreenModel).where(
            ScreenModel.screen_type_id == screen_type_id
        )
        return int(self._session.scalar(stmt) or 0)

    def _guard_unique(self, screen_type: ScreenType, exclude_id: int | None = None) -> None:
        """Регистронезависимая проверка уникальности name и точная — code.

        Даёт аккуратную 422 ещё до попытки INSERT/UPDATE. UNIQUE-индексы в БД —
        второй барьер (ловится в _commit_unique).
        """
        name_stmt = select(ScreenTypeModel.id).where(
            func.lower(ScreenTypeModel.name) == screen_type.name.lower()
        )
        if exclude_id is not None:
            name_stmt = name_stmt.where(ScreenTypeModel.id != exclude_id)
        if self._session.scalar(name_stmt) is not None:
            raise UnprocessableEntityError(_DUPLICATE_NAME_MESSAGE)

        if screen_type.code is not None:
            code_stmt = select(ScreenTypeModel.id).where(
                ScreenTypeModel.code == screen_type.code
            )
            if exclude_id is not None:
                code_stmt = code_stmt.where(ScreenTypeModel.id != exclude_id)
            if self._session.scalar(code_stmt) is not None:
                raise UnprocessableEntityError(_DUPLICATE_CODE_MESSAGE)

    def _commit_unique(self, model: ScreenTypeModel) -> None:
        """commit с переводом гонки по UNIQUE-индексу в UnprocessableEntityError (422)."""
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            message = (
                _DUPLICATE_CODE_MESSAGE
                if model.code is not None and "code" in str(exc.orig).lower()
                else _DUPLICATE_NAME_MESSAGE
            )
            raise UnprocessableEntityError(message) from exc
