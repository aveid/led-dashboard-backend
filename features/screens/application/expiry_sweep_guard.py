"""expiry_sweep_guard.py — дневной throttle для авто-архивации по истечению (FR-4.4).

Зачем нужен:
    Авто-архивация запускается ЛЕНИВО на статус-зависимых read-запросах (нет
    Celery/cron). Но истечение аренды меняется только на границе суток, поэтому
    подметать чаще раза в день бессмысленно. Guard держит маркер `last_sweep_date`
    НА УРОВНЕ ПРОЦЕССА: если сегодня уже подметали — sweep пропускается целиком
    (ноль обращений к БД). Итог: ~99% чтений не пишут в БД, а запись на GET
    сжимается до одной на весь день (у первого читателя после полуночи).

Почему маркер на уровне процесса, а не на инстансе use case:
    Use case и репозиторий пересоздаются на КАЖДЫЙ запрос (Depends), поэтому
    маркер на них не переживёт запрос. Синглтон через lru_cache даёт ровно один
    guard на процесс (по одному на воркер). Многоворкер/рестарт → максимум пара
    лишних, но полностью идемпотентных sweep'ов — на корректность не влияет.

Потокобезопасность: гонка на границе суток в худшем случае даёт лишний
идемпотентный sweep — блокировки не нужны (низконагруженный внутренний инструмент).
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from features.screens.application.use_cases.expire_due_screens import (
    ExpireDueScreensUseCase,
)


class ExpirySweepGuard:
    """Гейт «не чаще раза в сутки»: маркер последнего sweep живёт на уровне процесса."""

    def __init__(self) -> None:
        """Свежий guard ещё ни разу не подметал (маркер пуст)."""
        self._last: date | None = None

    def run_if_new_day(self, use_case: ExpireDueScreensUseCase, today: date) -> int:
        """Запускает sweep, только если сегодня его ещё не делали.

        `today` передаётся извне (из Clock), чтобы метод оставался тестируемым без
        подмешивания реального времени. Если маркер уже равен `today` — возвращаем 0
        БЕЗ обращения к use case/БД (горячий путь). Иначе выполняем bulk-архивацию,
        запоминаем дату и возвращаем число заархивированных экранов.
        """
        if self._last == today:
            return 0
        n = use_case.execute()
        self._last = today
        return n


@lru_cache(maxsize=1)
def get_expiry_sweep_guard() -> ExpirySweepGuard:
    """Возвращает единственный на процесс экземпляр guard (синглтон через lru_cache)."""
    return ExpirySweepGuard()
