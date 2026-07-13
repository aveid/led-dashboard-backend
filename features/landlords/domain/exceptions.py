"""exceptions.py — доменные исключения модуля арендодателей.

Чистый Python: ни fastapi, ни sqlalchemy, ни pydantic здесь нет и быть не должно.
Слой представления переводит эти ошибки в HTTP-ответы (см. router арендодателей).
"""

from __future__ import annotations

from uuid import UUID

from core.domain.exceptions import DomainError


class LandlordNotFoundError(DomainError):
    """Арендодатель с указанным id не найден.

    Отдельный доменный тип (а не общий NotFoundError), чтобы слой представления
    вернул машиночитаемое тело `{"detail": {"code": "LANDLORD_NOT_FOUND"}}`
    (по образцу `SCREEN_NOT_FOUND`), а не строку сообщения. Несёт id для
    диагностики.
    """

    def __init__(self, landlord_id: UUID) -> None:
        """Фиксирует id ненайденного арендодателя."""
        self.landlord_id = landlord_id
        super().__init__(f"Арендодатель с id={landlord_id} не найден.")
