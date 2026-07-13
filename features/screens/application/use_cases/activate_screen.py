"""activate_screen.py — сценарий «Активировать экран» (FR-4).

За что отвечает: переводит экран в статус «активный», добавляя договор аренды
за период. Само правило активации (нужны арендодатель, договор и фото — FR-4.2)
живёт в доменной сущности Screen.activate(); сценарий лишь готовит данные и
сохраняет результат. Если условия не выполнены, домен бросит BusinessRuleViolation
(→ HTTP 409), и экран не активируется.
"""

from __future__ import annotations

from core.application.use_case import UseCase
from core.domain.value_objects import Money
from features.screens.application.dto import ActivateScreenInput
from features.screens.domain.entities import RentalContract, Screen
from features.screens.domain.repositories import ScreenRepository


class ActivateScreenUseCase(UseCase[ActivateScreenInput, Screen]):
    """Активирует экран и фиксирует договор аренды."""

    def __init__(self, repository: ScreenRepository) -> None:
        """Внедряем репозиторий через конструктор (DIP)."""
        self._repository = repository

    def execute(self, data: ActivateScreenInput) -> Screen:
        """Загрузить экран, собрать договор и активировать (с проверкой правила FR-4.2)."""
        screen = self._repository.get_by_id(data.screen_id)

        rental = RentalContract(
            rent_price=Money(data.rent_price, data.currency),
            start_date=data.start_date,
            end_date=data.end_date,
        )
        # Внутри проверяются арендодатель + наличие договора и фото; иначе исключение.
        screen.activate(rental)

        return self._repository.update(screen)
