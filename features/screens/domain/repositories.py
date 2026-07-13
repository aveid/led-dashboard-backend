"""repositories.py — порт (интерфейс) репозитория экранов.

Что такое «порт» в Clean Architecture:
    Это абстракция хранилища, объявленная в домене. Домен и use cases зависят
    ОТ ЭТОГО интерфейса, а не от конкретной БД. Реализация (SQLAlchemy) живёт в
    инфраструктуре и «подключается» снаружи. Так соблюдается принцип инверсии
    зависимостей (DIP из SOLID): детали (БД) зависят от абстракции, а не наоборот.

Зачем это нужно:
    • Домен остаётся чистым и не знает про SQLAlchemy/FastAPI;
    • use cases легко тестировать, подставив фейковый репозиторий в памяти;
    • хранилище можно заменить (другая БД, кэш), не трогая бизнес-логику.

Методы возвращают доменные сущности (Screen), а НЕ ORM-объекты — граница слоёв.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from .entities import Screen
from .enums import AttachmentType, ScreenStatus


@dataclass(frozen=True)
class ScreenFilters:
    """Набор фильтров для выборки экранов (соответствует FR-5).

    Все поля необязательны: заданные — применяются, None — игнорируются.
    Комбинируются логическим И (FR-5.6).
    """

    landlord_id: UUID | None = None          # фильтр по арендодателю (FR-5.1)
    status: ScreenStatus | None = None       # фильтр по статусу (FR-5.2)
    city_id: int | None = None               # фильтр по городу (FR-5.3), ссылка на cities.id
    campaign_id: UUID | None = None          # фильтр по кампании (FR-5.4)
    contract_end_before: date | None = None  # договор заканчивается до даты (FR-5.5)
    screen_type_id: int | None = None        # фильтр по типу экрана (§4.3), ссылка на screen_types.id


class ScreenRepository(ABC):
    """Интерфейс хранилища экранов. Реализуется в инфраструктуре (SQLAlchemy).

    Слой представления и use cases работают только с этим интерфейсом.
    """

    @abstractmethod
    def get_by_id(self, screen_id: UUID) -> Screen:
        """Возвращает экран по id.

        Если экран не найден — выбрасывает NotFoundError (домен), которую
        представление превратит в HTTP 404.
        """
        raise NotImplementedError

    @abstractmethod
    def list(self, filters: ScreenFilters | None = None) -> list[Screen]:
        """Возвращает список экранов, опционально сузив его фильтрами (FR-5)."""
        raise NotImplementedError

    @abstractmethod
    def list_by_ids(self, screen_ids: list[UUID]) -> list[Screen]:
        """Возвращает экраны по списку id.

        Нужен для расчёта стоимости выделенных на карте экранов (FR-6).
        """
        raise NotImplementedError

    @abstractmethod
    def list_by_landlord(self, landlord_id: UUID) -> list[Screen]:
        """Возвращает экраны, принадлежащие арендодателю (FR-8.5).

        Плоский список экранов одного арендодателя (для раскрытия карточки).
        Возвращает доменные Screen (не ORM). Пустой список — валидный результат
        (у арендодателя нет экранов), не ошибка.
        """
        raise NotImplementedError

    @abstractmethod
    def add(self, screen: Screen) -> Screen:
        """Сохраняет новый экран и возвращает его уже с присвоенным id."""
        raise NotImplementedError

    @abstractmethod
    def update(self, screen: Screen) -> Screen:
        """Сохраняет изменения существующего экрана и возвращает его."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, screen_id: UUID) -> None:
        """Удаляет экран по id."""
        raise NotImplementedError

    @abstractmethod
    def delete_attachment(self, attachment_id: UUID) -> None:
        """Удаляет одно вложение экрана по его id (строку в таблице attachments).

        Идемпотентно: если вложения уже нет — ничего не делает. Проверку
        принадлежности вложения экрану выполняет вызывающий сценарий.
        """
        raise NotImplementedError

    @abstractmethod
    def archive_expired(self, today: date) -> int:
        """Bulk-перевод всех ACTIVE-экранов с истёкшей арендой в EXPIRY_TARGET_STATUS (FR-4.4).

        Одним идемпотентным UPDATE переводит в целевой статус все экраны, у которых
        `status == ACTIVE`, задана `rental_end_date` и `today > rental_end_date`
        (предикат — зеркало доменного Screen.is_rental_expired; `today` — дата в
        Asia/Bishkek). Возвращает число затронутых строк (≥ 0). Повторный вызов без
        новых просрочек затрагивает 0 строк.
        """
        raise NotImplementedError

    @abstractmethod
    def count_attachments_by_type(
        self, screen_id: UUID, attachment_type: AttachmentType
    ) -> int:
        """Считает вложения указанного вида у экрана (для проверки лимита загрузки).

        Возвращает целое ≥ 0. Отдельный COUNT-запрос — авторитетный источник
        правды о числе вложений на момент проверки (сценарий загрузки вызывает его
        ДО обращения к хранилищу, чтобы при отказе не осталось «сироты» в S3).
        """
        raise NotImplementedError
