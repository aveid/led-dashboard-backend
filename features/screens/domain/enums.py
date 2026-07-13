"""enums.py — перечисления (фиксированные наборы значений) домена «экраны».

За что отвечает модуль:
    Задаёт закрытые списки допустимых значений, чтобы в системе не появлялись
    произвольные строки-статусы. Это делает код надёжным: неверный статус
    невозможно создать, а IDE/линтер подскажут доступные варианты.
"""

from __future__ import annotations

from enum import Enum


class ScreenStatus(str, Enum):
    """Статус LED-экрана (требование FR-2.1).

    Наследуемся от str, чтобы значение легко сериализовалось в JSON и совпадало
    со строкой в БД ("active", "inactive", ...).

    Значения:
        ACTIVE    — экран сейчас арендуется нами;
        INACTIVE  — есть в базе, но сейчас не арендуется;
        POTENTIAL — рассматривается для аренды;
        ARCHIVED  — раньше использовался, сейчас не актуален.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"
    POTENTIAL = "potential"
    ARCHIVED = "archived"


class AttachmentType(str, Enum):
    """Тип прикреплённого к экрану файла (FR-3.12, FR-3.13).

    PHOTO    — фотография экрана;
    CONTRACT — скан/файл договора аренды;
    OTHER    — прочие документы.
    """

    PHOTO = "photo"
    CONTRACT = "contract"
    OTHER = "other"
