"""models.py — ORM-модели SQLAlchemy для фичи «экраны» (таблицы БД).

За что отвечает модуль:
    Описывает, как доменные данные хранятся в PostgreSQL/PostGIS. Это ДЕТАЛЬ
    инфраструктуры: доменные сущности (features/screens/domain/entities.py) и эти
    ORM-модели — разные вещи. Связь между ними делают мапперы (mappers.py).

Учтены решения по открытым вопросам:
    • Q3 (история аренды) — договоры вынесены в отдельную таблицу rental_contracts
      со связью «многие к одному» к экрану (у экрана список договоров);
    • Q4 (кампании) — связь экран↔кампания через таблицу-связку screen_campaigns
      (M2M), что позволяет позже разместить несколько кампаний без смены схемы;
    • Q2 (один арендодатель) — landlord_id одиночная внешняя связь.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Table,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base
from features.campaigns.infrastructure.models import CampaignModel  # владелец таблицы campaigns
from features.cities.infrastructure.models import CityModel  # владелец таблицы cities
from features.landlords.infrastructure.models import LandlordModel  # владелец таблицы landlords  # noqa: F401
from features.screen_types.infrastructure.models import ScreenTypeModel  # владелец таблицы screen_types

# --- Таблица-связка «экран ↔ кампания» (M2M, задел на несколько кампаний, Q4) ---
screen_campaigns = Table(
    "screen_campaigns",
    Base.metadata,
    Column("screen_id", ForeignKey("screens.id", ondelete="CASCADE"), primary_key=True),
    Column("campaign_id", ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True),
)


class ContactModel(Base):
    """Контактное лицо по экрану (FR-3.6). Простая справочная таблица.

    Пока живёт внутри модуля screens (нет отдельных сценариев работы с контактами
    вне карточки экрана). Если появится самостоятельный справочник контактов —
    вынесем по аналогии с landlords/campaigns.
    """

    __tablename__ = "contacts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(255), default="")


class ScreenModel(Base):
    """Таблица LED-экранов — центральная таблица фичи (FR-3)."""

    __tablename__ = "screens"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))

    # Город — ссылка на справочник cities. ON DELETE RESTRICT: город с экранами
    # удалить нельзя (второй барьер после предпроверки в репозитории городов).
    city_id: Mapped[int] = mapped_column(
        ForeignKey("cities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Загружаем город сразу (lazy="joined") — он нужен почти в каждом ответе (карточка/список).
    city: Mapped[CityModel] = relationship(back_populates="screens", lazy="joined")

    # Размер экрана — свободный текст (напр. «1920x1080», «55"»). NOT NULL с DEFAULT ''
    # (историю после backfill храним пустой строкой; форма требует непустое значение).
    size: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")

    # Тип экрана — ссылка на справочник screen_types. ON DELETE RESTRICT: тип с
    # экранами удалить нельзя (второй барьер после предпроверки в репозитории типов).
    screen_type_id: Mapped[int] = mapped_column(
        ForeignKey("screen_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Тип загружаем сразу (lazy="joined") — он нужен в ответе экрана (карточка/список).
    # Связь односторонняя (без back_populates): обратная коллекция типу не нужна.
    screen_type: Mapped[ScreenTypeModel] = relationship(lazy="joined")

    # Гео-точка экрана (PostGIS). SRID 4326 — стандартные широта/долгота (WGS84).
    # Точный адрес (район/улица) в модели не хранится — локация задаётся точкой на
    # карте (FR-3.3), меняется через PATCH /api/screens/{id}/location.
    location = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    # Статус экрана хранится строкой ("active"/"inactive"/...), совпадает со значением enum.
    status: Mapped[str] = mapped_column(String(20), default="potential")

    # Один арендодатель на экран (Q2). SET NULL — при удалении арендодателя экран остаётся.
    landlord_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("landlords.id", ondelete="SET NULL"), nullable=True
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )

    comment: Mapped[str] = mapped_column(Text, default="")

    # Последний день действия аренды ВКЛЮЧИТЕЛЬНО (FR-4.4). NULL — бессрочная/rolling
    # аренда: экран не истекает. По истечению ленивый sweep на чтении переводит
    # активный экран в архив (см. SqlAlchemyScreenRepository.archive_expired).
    rental_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- Связи ---
    # История договоров аренды (Q3): при удалении экрана удаляются и его договоры.
    rentals: Mapped[list["RentalContractModel"]] = relationship(
        back_populates="screen", cascade="all, delete-orphan"
    )
    # Кампании на экране (M2M через таблицу-связку, Q4).
    campaigns: Mapped[list[CampaignModel]] = relationship(secondary=screen_campaigns)
    # Вложения (фото/договоры/документы).
    attachments: Mapped[list["AttachmentModel"]] = relationship(
        back_populates="screen", cascade="all, delete-orphan"
    )


class RentalContractModel(Base):
    """Договор аренды за период — элемент истории аренды экрана (Q3, FR-3.7–3.9)."""

    __tablename__ = "rental_contracts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    screen_id: Mapped[UUID] = mapped_column(ForeignKey("screens.id", ondelete="CASCADE"))
    rent_price: Mapped[float] = mapped_column(Numeric(12, 2))  # хранится как точное число
    currency: Mapped[str] = mapped_column(String(3), default="KGS")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

    screen: Mapped[ScreenModel] = relationship(back_populates="rentals")


class AttachmentModel(Base):
    """Прикреплённый к экрану файл: фото, договор или документ (FR-3.12/3.13).

    Храним ВНУТРЕННИЙ ключ объекта в бакете (object_key) и метаданные файла, а не
    готовую ссылку: короткоживущую presigned-ссылку собирает слой представления из
    object_key при чтении. object_key уникален (сгенерирован от uuid4).
    """

    __tablename__ = "attachments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    screen_id: Mapped[UUID] = mapped_column(ForeignKey("screens.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(20))              # "photo" | "contract" | "other"
    object_key: Mapped[str] = mapped_column(String(512), unique=True)  # ключ объекта в бакете
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))     # MIME
    size_bytes: Mapped[int] = mapped_column(BigInteger)        # размер файла в байтах
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    screen: Mapped[ScreenModel] = relationship(back_populates="attachments")
