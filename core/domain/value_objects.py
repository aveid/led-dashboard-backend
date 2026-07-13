"""value_objects.py — общие value objects (объекты-значения) домена.

Что такое value object:
    Небольшой неизменяемый объект, у которого нет собственного идентификатора —
    он определяется только своими значениями. Две суммы «100 сом» равны, потому
    что равны их поля, а не потому что это «один и тот же объект».

Зачем они нужны здесь:
    • Money  — гарантирует, что деньги всегда считаются в Decimal и не бывают
               отрицательными; арифметика денег живёт в одном месте.
    • GeoPoint — гарантирует, что координаты валидны (широта/долгота в диапазоне).

Все value objects помечены `frozen=True` — их нельзя менять после создания.
Это делает код предсказуемым и безопасным (нельзя случайно «испортить» сумму).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.domain.exceptions import ValidationError

# Валюта проекта — кыргызский сом. Все суммы в системе — в сомах (NFR-5).
DEFAULT_CURRENCY = "KGS"


@dataclass(frozen=True)
class Money:
    """Денежная сумма. Хранится в Decimal (никогда не float!) и не отрицательна.

    Почему Decimal: float даёт ошибки округления (0.1 + 0.2 != 0.3), что для
    денег недопустимо. Decimal считает точно.
    """

    amount: Decimal
    currency: str = DEFAULT_CURRENCY

    def __post_init__(self) -> None:
        """Проверяет инварианты сразу после создания (сумма не отрицательна)."""
        if not isinstance(self.amount, Decimal):
            # Защита от случайной передачи float/int — заставляем использовать Decimal.
            raise ValidationError("Сумма должна быть Decimal, а не float/int.")
        if self.amount < Decimal("0"):
            raise ValidationError("Сумма аренды не может быть отрицательной.")

    @classmethod
    def zero(cls, currency: str = DEFAULT_CURRENCY) -> Money:
        """Возвращает нулевую сумму. Удобно как стартовое значение при суммировании."""
        return cls(Decimal("0"), currency)

    def __add__(self, other: Money) -> Money:
        """Складывает две суммы одной валюты. Разные валюты складывать нельзя."""
        self._ensure_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def _ensure_same_currency(self, other: Money) -> None:
        """Внутренняя проверка: операции возможны только над одной валютой."""
        if self.currency != other.currency:
            raise ValidationError(
                f"Нельзя складывать разные валюты: {self.currency} и {other.currency}."
            )


@dataclass(frozen=True)
class GeoPoint:
    """Гео-точка (координата экрана на карте): широта и долгота.

    Проверяет, что координаты попадают в допустимые диапазоны Земли, чтобы в
    базу не попала «битая» точка, которую карта не сможет отобразить.
    """

    latitude: float   # широта, допустимый диапазон [-90; 90]
    longitude: float  # долгота, допустимый диапазон [-180; 180]

    def __post_init__(self) -> None:
        """Валидирует диапазоны координат при создании точки."""
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValidationError("Широта должна быть в диапазоне [-90; 90].")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValidationError("Долгота должна быть в диапазоне [-180; 180].")
