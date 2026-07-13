"""dashboard_summary.py — сценарий «Сводка для главного экрана» (FR-9).

За что отвечает: собирает по всем экранам агрегаты для дашборда — счётчики по
статусам (FR-9.1/9.2), суммарную аренду активных (FR-9.3), разбивку по
арендодателям (FR-9.4) и список договоров, заканчивающихся в пределах порога
(FR-9.5, порог по умолчанию 30 дней — настраиваемый параметр, см. Q7 в ТЗ).

Дата «сегодня» передаётся параметром (по умолчанию — реальная сегодняшняя дата),
а не берётся из datetime.now() внутри логики: так сценарий остаётся детерминированным
и легко тестируется с фиксированной датой.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from core.application.use_case import UseCase
from core.domain.value_objects import Money
from features.screens.application.dto import (
    DashboardSummaryResult,
    EndingContract,
    LandlordCost,
)
from features.screens.domain.entities import Screen
from features.screens.domain.enums import ScreenStatus
from features.screens.domain.repositories import ScreenRepository


@dataclass(frozen=True)
class DashboardSummaryInput:
    """Параметры сводки: порог «скоро заканчивается» и опорная дата «сегодня»."""

    threshold_days: int = 30
    today: date | None = None  # None → использовать реальную сегодняшнюю дату


class DashboardSummaryUseCase(UseCase[DashboardSummaryInput, DashboardSummaryResult]):
    """Считает сводную статистику по всем экранам в базе."""

    def __init__(self, repository: ScreenRepository) -> None:
        """Внедряем репозиторий через конструктор (DIP)."""
        self._repository = repository

    def execute(self, data: DashboardSummaryInput) -> DashboardSummaryResult:
        """Загружает все экраны и считает по ним агрегаты."""
        screens = self._repository.list()
        today = data.today if data.today is not None else date.today()

        counts = self._count_by_status(screens)
        total_active_rent = self._total_active_rent(screens)
        by_landlord = self._breakdown_by_landlord(screens)
        ending_soon = self._ending_soon(screens, today, data.threshold_days)

        return DashboardSummaryResult(
            total_screens=len(screens),
            active_count=counts[ScreenStatus.ACTIVE],
            inactive_count=counts[ScreenStatus.INACTIVE],
            potential_count=counts[ScreenStatus.POTENTIAL],
            archived_count=counts[ScreenStatus.ARCHIVED],
            total_active_rent=total_active_rent,
            by_landlord=by_landlord,
            ending_soon=ending_soon,
        )

    def _count_by_status(self, screens: list[Screen]) -> dict[ScreenStatus, int]:
        """Считает количество экранов по каждому статусу (FR-9.1, FR-9.2)."""
        counts: dict[ScreenStatus, int] = dict.fromkeys(ScreenStatus, 0)
        for screen in screens:
            counts[screen.status] += 1
        return counts

    def _total_active_rent(self, screens: list[Screen]) -> Money:
        """Суммирует аренду только активных экранов (FR-9.3)."""
        total = Money.zero()
        for screen in screens:
            if screen.status == ScreenStatus.ACTIVE:
                total = total + screen.monthly_price
        return total

    def _breakdown_by_landlord(self, screens: list[Screen]) -> list[LandlordCost]:
        """Считает количество экранов и сумму аренды по каждому арендодателю (FR-9.4).

        Учитываются все экраны (не только активные) — это картина распределения
        экранов по арендодателям; в сумму идёт стоимость аренды по каждому экрану
        (0, если экран сейчас не активен и договора нет).
        """
        counts: dict[UUID | None, int] = defaultdict(int)
        totals: dict[UUID | None, Money] = defaultdict(Money.zero)
        for screen in screens:
            counts[screen.landlord_id] += 1
            totals[screen.landlord_id] = totals[screen.landlord_id] + screen.monthly_price
        return [
            LandlordCost(landlord_id=landlord_id, screens_count=counts[landlord_id], total=totals[landlord_id])
            for landlord_id in counts
        ]

    def _ending_soon(
        self, screens: list[Screen], today: date, threshold_days: int
    ) -> list[EndingContract]:
        """Собирает договоры активных экранов, заканчивающиеся в пределах порога (FR-9.5).

        Порог считается от today. Уже просроченные (end_date < today) договоры тоже
        включаются — на них тем более стоит обратить внимание.
        """
        deadline = today + timedelta(days=threshold_days)
        result = []
        for screen in screens:
            rental = screen.current_rental
            if rental is not None and rental.end_date <= deadline:
                result.append(
                    EndingContract(
                        screen_id=screen.id,
                        screen_name=screen.name,
                        landlord_id=screen.landlord_id,
                        end_date=rental.end_date,
                    )
                )
        result.sort(key=lambda item: item.end_date)  # ближайшие по сроку — первыми
        return result
