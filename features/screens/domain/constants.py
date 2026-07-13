"""constants.py — доменные константы фичи «экраны».

За что отвечает модуль:
    Хранит значения, которые задают СЕМАНТИКУ бизнес-правил в одной точке, чтобы
    смена поведения не требовала правок по всему коду.

EXPIRY_TARGET_STATUS — целевой статус для экрана с истёкшей арендой (FR-4.4).
    Единственная точка смены семантики авто-архивации: если бизнес решит, что
    «истёкшая аренда = экран свободен», меняем ТОЛЬКО эту константу
    (ARCHIVED → INACTIVE), а доменное правило (Screen.is_rental_expired /
    archive_on_expiry) и bulk-репозиторий (ScreenRepository.archive_expired)
    продолжат работать без изменений.
"""

from __future__ import annotations

from .enums import ScreenStatus

# Куда переводим экран, у которого истёк срок аренды (по ТЗ FR-4.4 — в архив).
EXPIRY_TARGET_STATUS: ScreenStatus = ScreenStatus.ARCHIVED
