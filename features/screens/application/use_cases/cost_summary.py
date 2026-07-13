"""cost_summary.py — сценарий «Расчёт стоимости выбранных экранов» (FR-6).

За что отвечает:
    По списку id выделенных на карте экранов считает:
      • сколько экранов выбрано (FR-6.2);
      • общую стоимость аренды в месяц (FR-6.3);
      • разбивку суммы и количества по арендодателям (FR-6.4).

    Соответствует примеру из брифа:
      «Выбрано 8 · Итого 220 000 сом · Арендодатель 1 — 5 экранов, 140 000 сом ...»

Почему это отдельный use case:
    Это ключевая бизнес-логика продукта (быстрый расчёт бюджета). Она не должна
    жить во вьюхе — здесь её легко покрыть юнит-тестами на разных наборах экранов.
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from features.screens.application.dto import CostSummaryResult, LandlordCost
from features.screens.domain.entities import Screen
from features.screens.domain.repositories import ScreenRepository
from core.application.use_case import UseCase
from core.domain.value_objects import Money


class CostSummaryUseCase(UseCase[list[UUID], CostSummaryResult]):
    """Считает суммарную стоимость аренды выбранных экранов и разбивку по арендодателям."""

    def __init__(self, repository: ScreenRepository) -> None:
        """Внедряем репозиторий через конструктор (DIP)."""
        self._repository = repository

    def execute(self, data: list[UUID]) -> CostSummaryResult:
        """Главный метод: получить экраны по id и посчитать агрегаты.

        Аргумент data — список id выделенных экранов. Пустой список даёт нулевой
        результат (0 экранов, 0 сом) — это корректное поведение, не ошибка.
        """
        screens = self._repository.list_by_ids(data)
        total = self._calculate_total(screens)
        by_landlord = self._breakdown_by_landlord(screens)
        return CostSummaryResult(
            selected_count=len(screens),
            total=total,
            by_landlord=by_landlord,
        )

    def _calculate_total(self, screens: list[Screen]) -> Money:
        """Суммирует месячную стоимость всех переданных экранов.

        Начинаем с нуля и прибавляем цену каждого экрана. Экран без аренды
        добавляет ноль (см. Screen.monthly_price), поэтому список смешанных
        (арендуемых и нет) экранов считается корректно.
        """
        total = Money.zero()
        for screen in screens:
            total = total + screen.monthly_price
        return total

    def _breakdown_by_landlord(self, screens: list[Screen]) -> list[LandlordCost]:
        """Группирует экраны по арендодателю и считает по каждому кол-во и сумму.

        Экраны без арендодателя (landlord_id = None) попадают в отдельную группу
        с ключом None — их тоже видно в разбивке.
        """
        # Накопители: количество и сумма по каждому landlord_id.
        counts: dict[UUID | None, int] = defaultdict(int)
        totals: dict[UUID | None, Money] = defaultdict(Money.zero)

        for screen in screens:
            key = screen.landlord_id
            counts[key] += 1
            totals[key] = totals[key] + screen.monthly_price

        # Превращаем накопленное в список DTO для ответа.
        return [
            LandlordCost(
                landlord_id=landlord_id,
                screens_count=counts[landlord_id],
                total=totals[landlord_id],
            )
            for landlord_id in counts
        ]
