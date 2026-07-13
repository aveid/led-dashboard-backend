"""list_screens_by_landlord.py — сценарий «Список экранов арендодателя» (FR-8.5).

За что отвечает: по одному арендодателю отдаёт плоский список его экранов в
облегчённом виде (LandlordScreenBrief) для раскрытия карточки на экране
«Арендодатели». Счётчик «Экранов: N» (FR-8.3) фронт считает как длину этого
списка — отдельный агрегат не нужен.

Presign/FileStoragePort здесь НЕ участвует (§2 инструкции): вложения в брифы не
входят, поэтому дорогой presign на каждый экран не выполняется.
"""

from __future__ import annotations

from uuid import UUID

from features.landlords.domain.exceptions import LandlordNotFoundError
from features.landlords.domain.repositories import LandlordRepository
from features.screens.application.dto import LandlordScreenBrief
from features.screens.domain.entities import Screen
from features.screens.domain.repositories import ScreenRepository


class ListScreensByLandlordUseCase:
    """Отдаёт список облегчённых экранов конкретного арендодателя (FR-8.5)."""

    def __init__(
        self, screen_repo: ScreenRepository, landlord_repo: LandlordRepository
    ) -> None:
        """Внедряем оба репозитория через конструктор (DIP)."""
        self._screen_repo = screen_repo
        self._landlord_repo = landlord_repo

    def execute(self, landlord_id: UUID) -> list[LandlordScreenBrief]:
        """Проверяет существование арендодателя и собирает брифы его экранов.

        Несуществующий арендодатель → LandlordNotFoundError (представление вернёт
        404 с машиночитаемым телом). Существующий без экранов → пустой список.
        """
        if not self._landlord_repo.exists(landlord_id):
            raise LandlordNotFoundError(landlord_id)
        screens = self._screen_repo.list_by_landlord(landlord_id)
        return [self._to_brief(screen) for screen in screens]

    @staticmethod
    def _to_brief(screen: Screen) -> LandlordScreenBrief:
        """Собирает облегчённый DTO из доменного экрана (без attachments/presign).

        city/screen_type загружены вместе с экраном (lazy="joined") и проставлены
        инфраструктурным маппером, поэтому здесь они не None.

        monthly_price (FR-8.4) берём из текущего договора аренды: если он есть —
        его цену (Money), иначе None. Домен-свойство Screen.monthly_price отдаёт
        для неарендованного экрана ноль, но по контракту брифа «нет цены» = null
        (а не 0), поэтому источник — сам current_rental.
        """
        rental = screen.current_rental
        return LandlordScreenBrief(
            id=screen.id,
            name=screen.name,
            status=screen.status,
            size=screen.size,
            city_id=screen.city_id,
            city=screen.city,
            screen_type_id=screen.screen_type_id,
            screen_type=screen.screen_type,
            lng=screen.location.longitude,
            lat=screen.location.latitude,
            monthly_price=rental.rent_price if rental is not None else None,
        )
