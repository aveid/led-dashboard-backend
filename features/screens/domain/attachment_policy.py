"""attachment_policy.py — доменное правило «сколько вложений можно к экрану».

За что отвечает модуль:
    Хранит бизнес-инвариант лимита вложений и доменное исключение его нарушения.
    Это ПРАВИЛО предметной области (а не настройка окружения), поэтому живёт в
    домене, а не в env/settings. Если бизнес позже попросит настраиваемость —
    значение можно вынести в конфиг, не меняя формы исключения.

Чистый Python: ни fastapi, ни sqlalchemy, ни pydantic здесь нет и быть не должно.
"""

from __future__ import annotations

from typing import Final

from core.domain.exceptions import DomainError

from .enums import AttachmentType

# Максимум вложений КАЖДОГО вида на один экран. Виды считаются раздельно
# (5 фото + 5 договоров + 5 прочих — независимые лимиты). Единственный источник
# правды для числа «5»: нигде больше его хардкодить нельзя.
MAX_ATTACHMENTS_PER_KIND: Final[int] = 5


class AttachmentLimitExceededError(DomainError):
    """Достигнут лимит вложений данного вида у экрана (нельзя добавить ещё).

    Несёт вид вложения и предельное значение, чтобы слой представления мог
    вернуть машиночитаемую ошибку (HTTP 409 с кодом ATTACHMENT_LIMIT_EXCEEDED).
    """

    def __init__(self, kind: AttachmentType, max_allowed: int) -> None:
        """Фиксирует вид вложения и лимит, из-за которого отказано в загрузке."""
        self.kind = kind
        self.max_allowed = max_allowed
        super().__init__(
            f"Достигнут лимит вложений вида '{kind.value}' (максимум {max_allowed})."
        )
