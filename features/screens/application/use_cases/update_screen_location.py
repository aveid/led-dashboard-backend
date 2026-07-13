"""update_screen_location.py — сценарий «Сменить локацию экрана» (FR-3.3).

За что отвечает: загружает экран по id, переносит его в новую точку на карте
(Screen.relocate) и сохраняет. Это узкий идемпотентный сценарий «перетащить пин
и сохранить» — в отличие от общего редактирования (update_screen) он меняет только
координаты и не допускает overposting остальных полей.

Почему логика тут, а не во вьюхе: смена локации — сценарий приложения. Вьюха лишь
принимает HTTP-запрос (lng/lat) и делегирует сюда; так сценарий переиспользуется и
тестируется без HTTP.
"""

from __future__ import annotations

from features.screens.application.dto import UpdateScreenLocationInput
from features.screens.domain.entities import Screen
from features.screens.domain.repositories import ScreenRepository
from core.application.use_case import UseCase
from core.domain.value_objects import GeoPoint


class UpdateScreenLocationUseCase(UseCase[UpdateScreenLocationInput, Screen]):
    """Меняет координаты существующего экрана и сохраняет его."""

    def __init__(self, repository: ScreenRepository) -> None:
        """Внедряем репозиторий через конструктор (DIP)."""
        self._repository = repository

    def execute(self, data: UpdateScreenLocationInput) -> Screen:
        """Загрузить экран, перенести пин, сохранить.

        get_by_id бросает доменную NotFoundError (→ HTTP 404), если экрана нет.
        GeoPoint проверяет диапазоны координат (→ ValidationError, если бы Pydantic
        не поймал их раньше). Возвращает обновлённый доменный Screen — presigned-url
        для вложений соберёт слой представления (screen_to_read), как в остальных
        Read-путях.
        """
        screen = self._repository.get_by_id(data.screen_id)
        screen.relocate(GeoPoint(latitude=data.latitude, longitude=data.longitude))
        return self._repository.update(screen)
