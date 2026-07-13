"""expire_due_screens.py — сценарий «Заархивировать экраны с истёкшей арендой» (FR-4.4).

За что отвечает: одним идемпотентным bulk-переводом архивирует все активные
экраны, у которых истёк срок аренды (rental_end_date < сегодня в Asia/Bishkek).
Сам сценарий НИЧЕГО не читает наружу — только пишет счётчик затронутых строк.

Чистый и без throttle by design:
    Дневной throttle («не чаще раза в сутки») — забота отдельного гейта
    ExpirySweepGuard (application/expiry_sweep_guard.py), а не этого сценария.
    Благодаря этому сценарий переиспользуется как есть будущим Celery-beat
    (FR-9.5): там триггером станет расписание, а guard будет не нужен.

Дата «сегодня» приходит из порта Clock (Asia/Bishkek) — не тащим datetime.now()
внутрь логики, чтобы сценарий оставался детерминированным и тестируемым.
"""

from __future__ import annotations

from core.application.clock import Clock
from features.screens.domain.repositories import ScreenRepository


class ExpireDueScreensUseCase:
    """Архивирует все просроченные по аренде экраны одним bulk-переходом. Идемпотентен."""

    def __init__(self, screens: ScreenRepository, clock: Clock) -> None:
        """Внедряем репозиторий экранов и часы через конструктор (DIP)."""
        self._screens = screens
        self._clock = clock

    def execute(self) -> int:
        """Переводит просроченные активные экраны в целевой статус.

        Возвращает число заархивированных экранов (0 — если просрочек нет). Дата
        сравнения — «сегодня» в Asia/Bishkek. Коммит выполняет вызывающий (в проде —
        зависимость-триггер в той же сессии запроса).
        """
        today = self._clock.today_bishkek()
        return self._screens.archive_expired(today)
