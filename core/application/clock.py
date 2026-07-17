"""clock.py — часы приложения: источник «сегодняшней даты» в тайзоне Бишкека.

За что отвечает модуль:
    Даёт сценариям (use cases) детерминируемый источник даты, не таща
    `datetime.now()` в доменный слой. Абстракция `Clock` позволяет в тестах
    подменить «сегодня» фиксированной датой, а в проде — брать реальную.

Почему фиксированное смещение UTC+6, а не ZoneInfo("Asia/Bishkek"):
    Бишкек живёт по постоянному UTC+6 (перехода на летнее время нет с 2005 г.),
    поэтому фиксированное смещение семантически идентично зоне Asia/Bishkek. При
    этом мы не зависим от системной базы tzdata: базовый образ python:3.12-slim
    её не содержит, а пакет `tzdata` в зависимости не добавлен — ZoneIn­fo мог бы
    упасть с ZoneInfoNotFoundError. Фиксированное смещение надёжнее и без новых
    зависимостей. Если когда-нибудь понадобится настоящая зона (DST и т.п.) —
    достаточно поменять BISHKEK_TZ на ZoneInfo и добавить tzdata.
"""


from __future__ import annotations


from datetime import date, datetime, timedelta, timezone
from typing import Protocol

# Asia/Bishkek — фиксированный UTC+6 (без DST). Граница суток «сегодня» считается
# по этому смещению, чтобы throttle авто-архивации и предикат «истёк» не разъезжались.
BISHKEK_TZ = timezone(timedelta(hours=6))


class Clock(Protocol):
    """Порт часов: отдаёт текущую дату в тайзоне Бишкека.

    Протокол (structural typing): любой объект с методом `today_bishkek() -> date`
    подходит — реальный SystemClock в проде, фиктивный с фиксированной датой в тестах.
    """

    def today_bishkek(self) -> date:  # pragma: no cover - интерфейс
        ...


class SystemClock:
    """Системные часы: «сегодня» по календарю Asia/Bishkek (UTC+6)."""

    def today_bishkek(self) -> date:
        """Возвращает текущую дату в Бишкеке (UTC+6)."""
        return datetime.now(BISHKEK_TZ).date()
