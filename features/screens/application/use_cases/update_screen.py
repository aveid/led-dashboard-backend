"""update_screen.py — сценарий «Редактировать экран» (FR-10.2).

За что отвечает: загружает экран, применяет присланные изменения (только
переданные поля) и сохраняет. Пересобирает координаты через value object GeoPoint,
поэтому некорректные данные будут отклонены доменом.

Смена локации точкой на карте — отдельный узкий сценарий (update_screen_location).

Перевод в статус «активный» здесь разрешён как обычный переход: договор больше
не является предусловием активации. Полный сценарий «оформить аренду» (с
фиксацией договора и прочими инвариантами FR-4.2) остаётся отдельным
(ActivateScreenUseCase).
"""

from __future__ import annotations

from features.screens.application.dto import UpdateScreenInput
from features.screens.domain.entities import Screen
from features.screens.domain.enums import ScreenStatus
from features.screens.domain.repositories import ScreenRepository
from features.screen_types.domain.repositories import ScreenTypeRepository
from core.application.use_case import UseCase
from core.domain.exceptions import UnprocessableEntityError
from core.domain.value_objects import GeoPoint


class UpdateScreenUseCase(UseCase[UpdateScreenInput, Screen]):
    """Применяет частичные изменения к экрану и сохраняет его."""

    def __init__(
        self,
        repository: ScreenRepository,
        screen_type_repository: ScreenTypeRepository,
    ) -> None:
        """Внедряем репозитории через конструктор (DIP).

        Репозиторий типов нужен, чтобы проверить существование screen_type_id
        (форма всегда его шлёт, §4.2) и вернуть 422 на несуществующий тип.
        """
        self._repository = repository
        self._screen_types = screen_type_repository

    def execute(self, data: UpdateScreenInput) -> Screen:
        """Загрузить экран, применить изменения, сохранить."""
        screen = self._repository.get_by_id(data.screen_id)

        # size и screen_type_id форма шлёт всегда (§4.2): применяем безусловно.
        # Существование типа проверяем явно → 422 на несуществующий (§5).
        if not self._screen_types.exists(data.screen_type_id):
            raise UnprocessableEntityError("Указанный тип экрана не найден")
        screen.size = data.size
        screen.screen_type_id = data.screen_type_id

        if data.name is not None:
            screen.name = data.name
        if data.city_id is not None:
            screen.city_id = data.city_id
        if data.comment is not None:
            screen.comment = data.comment
        if data.landlord_id is not None:
            screen.landlord_id = data.landlord_id
        if data.contact_id is not None:
            screen.contact_id = data.contact_id
        if data.campaign_ids is not None:
            screen.campaign_ids = list(data.campaign_ids)
        # Дату окончания аренды применяем только если фронт её действительно прислал
        # (флаг из model_fields_set): так явный null очищает дату (реактивация, §6),
        # а её отсутствие в PATCH не затирает уже сохранённое значение.
        if data.apply_rental_end_date:
            screen.rental_end_date = data.rental_end_date

        self._apply_location(screen, data)
        self._apply_status(screen, data)

        return self._repository.update(screen)

    def _apply_location(self, screen: Screen, data: UpdateScreenInput) -> None:
        """Пересобирает координаты, если пришла широта и/или долгота."""
        if data.latitude is None and data.longitude is None:
            return
        screen.location = GeoPoint(
            latitude=data.latitude if data.latitude is not None else screen.location.latitude,
            longitude=data.longitude if data.longitude is not None else screen.location.longitude,
        )

    def _apply_status(self, screen: Screen, data: UpdateScreenInput) -> None:
        """Меняет статус безопасными переходами через доменные методы.

        Перевод в «активный» идёт через screen.mark_active(), который теперь сам
        проверяет единый инвариант активации (арендодатель + фото + сумма аренды +
        дата окончания, FR-4.2 + §5) и бросает BusinessRuleViolation → 409, если он
        не выполнен. Так PATCH status=active больше не может «тихо» обойти
        инварианты. Договор при этом не фиксируется — полный сценарий «оформить
        аренду» остаётся отдельным (ActivateScreenUseCase).

        rental_end_date применяется в execute() ДО этого вызова, поэтому свежая
        дата (или её явная очистка) уже учтена гардом mark_active().
        """
        if data.status is None:
            return
        # Разрешённые переходы через доменные методы (сохраняют инварианты).
        transitions = {
            ScreenStatus.ACTIVE: screen.mark_active,
            ScreenStatus.INACTIVE: screen.deactivate,
            ScreenStatus.POTENTIAL: screen.mark_potential,
            ScreenStatus.ARCHIVED: screen.archive,
        }
        transitions[data.status]()
