"""Тесты доменных правил и прикладных сценариев фичи «экраны».

Эти тесты НЕ требуют базы данных: используется фейковый репозиторий в памяти.
Так проверяется именно бизнес-логика (изолированно, быстро) — это возможно
благодаря Clean Architecture, где домен и сценарии не зависят от инфраструктуры.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from core.application.storage import FileStorage
from core.domain.exceptions import (
    BusinessRuleViolation,
    NotFoundError,
    UnprocessableEntityError,
)
from core.domain.value_objects import GeoPoint, Money
from features.screens.application.dto import (
    ActivateScreenInput,
    AddAttachmentInput,
    CreateScreenInput,
    UpdateScreenInput,
    UpdateScreenLocationInput,
)
from features.screens.application.use_cases.activate_screen import ActivateScreenUseCase
from features.screens.application.use_cases.add_attachment import AddAttachmentUseCase
from features.screens.application.use_cases.create_screen import CreateScreenUseCase
from features.screens.application.use_cases.list_screens import ListScreensUseCase
from features.screens.application.use_cases.update_screen import UpdateScreenUseCase
from features.screens.presentation.schemas import ScreenCreate
from tests.screen_types.test_screen_types_domain import FakeScreenTypeRepository
from features.screens.application.use_cases.update_screen_location import (
    UpdateScreenLocationUseCase,
)
from features.screens.application.use_cases.cost_summary import CostSummaryUseCase
from features.screens.application.use_cases.dashboard_summary import (
    DashboardSummaryInput,
    DashboardSummaryUseCase,
)
from features.screens.application.use_cases.export_screens import (
    ExportScreensInput,
    ExportScreensUseCase,
)
from features.screens.application.expiry_sweep_guard import (
    ExpirySweepGuard,
    get_expiry_sweep_guard,
)
from features.screens.application.use_cases.expire_due_screens import (
    ExpireDueScreensUseCase,
)
from features.screens.domain.constants import EXPIRY_TARGET_STATUS
from features.screens.domain.entities import Attachment, RentalContract, Screen
from features.screens.domain.enums import AttachmentType, ScreenStatus
from features.screens.domain.repositories import ScreenFilters, ScreenRepository


class FakeScreenRepository(ScreenRepository):
    """Репозиторий в памяти — подмена БД для тестов сценариев."""

    def __init__(self, screens: list[Screen]) -> None:
        self._screens = {s.id: s for s in screens}

    def get_by_id(self, screen_id: UUID) -> Screen:
        screen = self._screens.get(screen_id)
        if screen is None:
            raise NotFoundError(f"Экран с id={screen_id} не найден.")
        return screen

    def list(self, filters: ScreenFilters | None = None) -> list[Screen]:
        """Применяет фильтры (как настоящий репозиторий), чтобы тесты сценариев
        со списком (list_screens, export) проверяли реальную фильтрацию, а не заглушку.
        """
        screens = list(self._screens.values())
        if filters is None:
            return screens
        if filters.landlord_id is not None:
            screens = [s for s in screens if s.landlord_id == filters.landlord_id]
        if filters.status is not None:
            screens = [s for s in screens if s.status == filters.status]
        if filters.city_id is not None:
            screens = [s for s in screens if s.city_id == filters.city_id]
        if filters.screen_type_id is not None:
            screens = [s for s in screens if s.screen_type_id == filters.screen_type_id]
        if filters.campaign_id is not None:
            screens = [s for s in screens if filters.campaign_id in s.campaign_ids]
        if filters.contract_end_before is not None:
            screens = [
                s
                for s in screens
                if any(r.end_date <= filters.contract_end_before for r in s.rentals)
            ]
        return screens

    def list_by_ids(self, screen_ids: list[UUID]) -> list[Screen]:
        return [self._screens[i] for i in screen_ids if i in self._screens]

    def list_by_landlord(self, landlord_id: UUID) -> list[Screen]:
        return [s for s in self._screens.values() if s.landlord_id == landlord_id]

    def archive_expired(self, today: date) -> int:
        """In-memory зеркало bulk-архивации: использует доменный SSOT перехода.

        Идёт через Screen.archive_on_expiry (тот же предикат is_rental_expired,
        что и SQL-WHERE реального репозитория) — так тесты сценария/идемпотентности
        проверяют настоящее правило, а не заглушку. Возвращает число заархивированных.
        """
        return sum(
            1 for s in self._screens.values() if s.archive_on_expiry(today)
        )

    def add(self, screen: Screen) -> Screen:
        self._screens[screen.id] = screen
        return screen

    def update(self, screen: Screen) -> Screen:
        self._screens[screen.id] = screen
        return screen

    def delete(self, screen_id: UUID) -> None:
        self._screens.pop(screen_id, None)

    def delete_attachment(self, attachment_id: UUID) -> None:
        for screen in self._screens.values():
            screen.attachments = [
                a for a in screen.attachments if a.id != attachment_id
            ]

    def count_attachments_by_type(
        self, screen_id: UUID, attachment_type: AttachmentType
    ) -> int:
        screen = self._screens.get(screen_id)
        if screen is None:
            return 0
        return sum(1 for a in screen.attachments if a.type == attachment_type)


class FakeFileStorage(FileStorage):
    """Хранилище в памяти — подмена S3/MinIO для тестов сценариев вложений."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, object_key: str, data: bytes, content_type: str) -> None:
        self.objects[object_key] = data

    def generate_presigned_get_url(self, object_key: str, expires_in: int) -> str:
        return f"https://storage.test/{object_key}?exp={expires_in}"

    def delete(self, object_key: str) -> None:
        self.objects.pop(object_key, None)


def _attachment(att_type: AttachmentType, key: str) -> Attachment:
    """Строит доменное вложение с корректными метаданными (для тестов)."""
    return Attachment(
        type=att_type,
        object_key=key,
        original_filename=key.rsplit("/", 1)[-1],
        content_type="application/octet-stream",
        size_bytes=1,
        uploaded_at=datetime.now(),
    )


def _active_screen(price: int, landlord_id: UUID, screen_id: UUID) -> Screen:
    """Готовит активный экран с одним договором аренды заданной цены."""
    rental = RentalContract(Money(Decimal(price)), date(2025, 1, 1), date(2025, 12, 31))
    return Screen(
        name="S",
        city_id=1,
        location=GeoPoint(42.87, 74.59),
        status=ScreenStatus.ACTIVE,
        landlord_id=landlord_id,
        rentals=[rental],
        id=screen_id,
    )


def test_cost_summary_matches_brief_example() -> None:
    """Расчёт стоимости воспроизводит пример из брифа (FR-6)."""
    landlord1, landlord2 = uuid4(), uuid4()
    ids = [uuid4() for _ in range(8)]
    screens = [_active_screen(28000, landlord1, ids[i]) for i in range(5)]
    screens += [
        _active_screen(price, landlord2, ids[5 + j])
        for j, price in enumerate([30000, 25000, 25000])
    ]
    repo = FakeScreenRepository(screens)

    result = CostSummaryUseCase(repo).execute(ids)

    assert result.selected_count == 8
    assert result.total.amount == Decimal(220000)
    by_landlord = {c.landlord_id: c for c in result.by_landlord}
    assert by_landlord[landlord1].screens_count == 5
    assert by_landlord[landlord1].total.amount == Decimal(140000)
    assert by_landlord[landlord2].screens_count == 3
    assert by_landlord[landlord2].total.amount == Decimal(80000)


def test_activation_still_requires_photo() -> None:
    """Через activate() экран нельзя активировать без фото (инвариант FR-4.2 сохранён).

    Наличие ДОГОВОРА больше не проверяется, поэтому отсутствие фото — единственная
    причина отказа здесь (арендодатель указан).
    """
    screen = Screen(
        name="X",
        city_id=2,
        location=GeoPoint(40.5, 72.8),
        landlord_id=uuid4(),
    )
    rental = RentalContract(Money(Decimal(10000)), date(2025, 1, 1), date(2025, 6, 1))

    with pytest.raises(BusinessRuleViolation):
        screen.activate(rental)


def test_activation_no_longer_requires_contract() -> None:
    """Договор перестал быть предусловием: activate() проходит с фото, но БЕЗ договора."""
    screen = Screen(
        name="X",
        city_id=2,
        location=GeoPoint(40.5, 72.8),
        landlord_id=uuid4(),
    )
    # Только фото — договор (Attachment типа CONTRACT) намеренно НЕ прикрепляем.
    screen.add_attachment(_attachment(AttachmentType.PHOTO, "screens/x/photo/p"))
    rental = RentalContract(Money(Decimal(10000)), date(2025, 1, 1), date(2025, 6, 1))

    screen.activate(rental)

    assert screen.status == ScreenStatus.ACTIVE
    assert screen.current_rental is not None
    assert screen.monthly_price.amount == Decimal(10000)


def _activatable_screen() -> Screen:
    """Экран, удовлетворяющий единому инварианту активации (арендодатель + фото +
    сумма аренды в истории + дата окончания) — для проверки mark_active()."""
    screen = Screen(
        name="X",
        city_id=2,
        location=GeoPoint(40.5, 72.8),
        landlord_id=uuid4(),
        rentals=[RentalContract(Money(Decimal(10000)), date(2025, 1, 1), date(2025, 12, 31))],
        rental_end_date=date(2025, 12, 31),
    )
    screen.add_attachment(_attachment(AttachmentType.PHOTO, "screens/x/photo/p"))
    return screen


def test_mark_active_enforces_activation_invariant() -> None:
    """mark_active() больше НЕ «тихий» переход: без инвариантов активации → 409.

    Закрывает API-дыру (PATCH status=active / create-as-active в обход FR-4.2 + §5):
    у голого экрана нет ни арендодателя, ни фото, ни суммы/даты → BusinessRuleViolation.
    """
    screen = Screen(name="X", city_id=2, location=GeoPoint(40.5, 72.8))

    with pytest.raises(BusinessRuleViolation):
        screen.mark_active()


def test_mark_active_succeeds_when_invariant_met() -> None:
    """mark_active() проходит, когда экран пригоден (арендодатель + фото + сумма + дата)."""
    screen = _activatable_screen()

    screen.mark_active()

    assert screen.status == ScreenStatus.ACTIVE


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda s: setattr(s, "landlord_id", None), id="no_landlord"),
        pytest.param(lambda s: setattr(s, "attachments", []), id="no_photo"),
        pytest.param(lambda s: setattr(s, "rentals", []), id="no_rent_sum"),
        pytest.param(lambda s: setattr(s, "rental_end_date", None), id="no_end_date"),
    ],
)
def test_mark_active_rejects_each_missing_invariant(mutate) -> None:  # type: ignore[no-untyped-def]
    """Каждое из требований гарда (арендодатель, фото, сумма, дата) обязательно."""
    screen = _activatable_screen()
    mutate(screen)

    with pytest.raises(BusinessRuleViolation):
        screen.mark_active()


def test_activate_and_mark_active_share_one_predicate() -> None:
    """Паритет: activate() и mark_active() отклоняют один и тот же непригодный экран (§3).

    У экрана есть договор (сумма + дата окончания) и арендодатель, но НЕТ фото —
    оба пути в active обязаны отклонить его одинаково (единый гард, одно правило).
    """
    landlord = uuid4()
    rental = RentalContract(Money(Decimal(10000)), date(2025, 1, 1), date(2025, 12, 31))

    def _screen_without_photo() -> Screen:
        return Screen(
            name="X",
            city_id=2,
            location=GeoPoint(40.5, 72.8),
            landlord_id=landlord,
            rentals=[rental],
            rental_end_date=date(2025, 12, 31),
        )

    with pytest.raises(BusinessRuleViolation):
        _screen_without_photo().mark_active()
    with pytest.raises(BusinessRuleViolation):
        _screen_without_photo().activate(rental)


def test_activation_succeeds_with_contract_and_photo() -> None:
    """Регрессия: активация С договором и фото по-прежнему проходит; договор в истории."""
    screen = Screen(
        name="X",
        city_id=2,
        location=GeoPoint(40.5, 72.8),
        landlord_id=uuid4(),
    )
    screen.add_attachment(_attachment(AttachmentType.CONTRACT, "screens/x/contract/c"))
    screen.add_attachment(_attachment(AttachmentType.PHOTO, "screens/x/photo/p"))
    rental = RentalContract(Money(Decimal(10000)), date(2025, 1, 1), date(2025, 6, 1))

    screen.activate(rental)

    assert screen.status == ScreenStatus.ACTIVE
    assert screen.current_rental is not None
    assert screen.monthly_price.amount == Decimal(10000)


def test_deactivate_keeps_history_but_clears_current_rental() -> None:
    """После деактивации история договоров сохраняется, но текущего договора нет (Q3)."""
    screen = _active_screen(10000, uuid4(), uuid4())

    screen.deactivate()

    assert screen.status == ScreenStatus.INACTIVE
    assert screen.current_rental is None
    assert len(screen.rentals) == 1  # история на месте
    assert screen.monthly_price.amount == Decimal(0)


def test_activate_use_case_flow_with_attachments() -> None:
    """Полный сценарий: загрузка фото и договора → активация проходит (FR-3.12/3.13 + FR-4)."""
    screen_id = uuid4()
    screen = Screen(
        name="Экран у ЦУМа",
        city_id=1,
        location=GeoPoint(42.87, 74.61),
        status=ScreenStatus.POTENTIAL,
        landlord_id=uuid4(),
        id=screen_id,
    )
    repo = FakeScreenRepository([screen])
    storage = FakeFileStorage()

    # Прикрепляем фото и договор через сценарий добавления вложений (сырые файлы).
    AddAttachmentUseCase(repo, storage).execute(
        AddAttachmentInput(
            screen_id=screen_id,
            attachment_type=AttachmentType.PHOTO,
            filename="p.jpg",
            content_type="image/jpeg",
            data=b"\xff\xd8\xff",
        )
    )
    AddAttachmentUseCase(repo, storage).execute(
        AddAttachmentInput(
            screen_id=screen_id,
            attachment_type=AttachmentType.CONTRACT,
            filename="c.pdf",
            content_type="application/pdf",
            data=b"%PDF-1.4",
        )
    )

    # Активируем с условиями аренды.
    result = ActivateScreenUseCase(repo).execute(
        ActivateScreenInput(
            screen_id=screen_id,
            rent_price=Decimal(45000),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
    )

    assert result.status == ScreenStatus.ACTIVE
    assert result.monthly_price.amount == Decimal(45000)
    assert len(result.attachments) == 2


def test_activate_use_case_blocked_without_photo() -> None:
    """Сценарий активации без фото отклоняется (инвариант FR-4.2; договор уже не нужен)."""
    screen_id = uuid4()
    screen = Screen(
        name="Экран без файлов",
        city_id=1,
        location=GeoPoint(42.87, 74.61),
        landlord_id=uuid4(),
        id=screen_id,
    )
    repo = FakeScreenRepository([screen])

    with pytest.raises(BusinessRuleViolation):
        ActivateScreenUseCase(repo).execute(
            ActivateScreenInput(
                screen_id=screen_id,
                rent_price=Decimal(45000),
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
            )
        )


def test_relocate_moves_only_coordinates() -> None:
    """Screen.relocate меняет только координаты, не трогая остальные поля (FR-3.3)."""
    landlord_id = uuid4()
    screen = _active_screen(30000, landlord_id, uuid4())

    screen.relocate(GeoPoint(latitude=41.0, longitude=75.0))

    assert screen.location.latitude == 41.0
    assert screen.location.longitude == 75.0
    # Остальные поля не изменились.
    assert screen.status == ScreenStatus.ACTIVE
    assert screen.landlord_id == landlord_id
    assert screen.monthly_price.amount == Decimal(30000)


def test_update_location_use_case_persists_new_point() -> None:
    """Сценарий смены локации сохраняет новую точку; повтор с тем же телом идемпотентен."""
    screen_id = uuid4()
    screen = Screen(
        name="Экран для переноса",
        city_id=1,
        location=GeoPoint(42.87, 74.61),
        id=screen_id,
    )
    repo = FakeScreenRepository([screen])

    result = UpdateScreenLocationUseCase(repo).execute(
        UpdateScreenLocationInput(screen_id=screen_id, latitude=42.9, longitude=74.5)
    )
    assert (result.location.latitude, result.location.longitude) == (42.9, 74.5)

    # Идемпотентность: повторный вызов с тем же телом даёт ту же геометрию.
    again = UpdateScreenLocationUseCase(repo).execute(
        UpdateScreenLocationInput(screen_id=screen_id, latitude=42.9, longitude=74.5)
    )
    assert (again.location.latitude, again.location.longitude) == (42.9, 74.5)


def test_update_location_use_case_missing_screen_raises() -> None:
    """Смена локации несуществующего экрана поднимает NotFoundError (→ 404 в API)."""
    repo = FakeScreenRepository([])

    with pytest.raises(NotFoundError):
        UpdateScreenLocationUseCase(repo).execute(
            UpdateScreenLocationInput(screen_id=uuid4(), latitude=42.9, longitude=74.5)
        )


def _screen_with_rental(
    name: str,
    price: int,
    landlord_id: UUID,
    status: ScreenStatus,
    end_date: date,
    screen_id: UUID | None = None,
) -> Screen:
    """Готовит экран с одним договором аренды (для тестов сводки/выгрузки)."""
    rental = RentalContract(Money(Decimal(price)), date(2025, 1, 1), end_date)
    rentals = [rental] if status == ScreenStatus.ACTIVE else []
    return Screen(
        name=name,
        city_id=1,
        location=GeoPoint(42.87, 74.59),
        status=status,
        landlord_id=landlord_id,
        rentals=rentals,
        id=screen_id or uuid4(),
    )


def test_dashboard_summary_counts_and_totals() -> None:
    """Сводка считает счётчики по статусам и сумму аренды активных (FR-9.1–9.3)."""
    landlord = uuid4()
    screens = [
        _screen_with_rental("A", 10000, landlord, ScreenStatus.ACTIVE, date(2026, 8, 1)),
        _screen_with_rental("B", 20000, landlord, ScreenStatus.ACTIVE, date(2026, 8, 1)),
        _screen_with_rental("C", 0, landlord, ScreenStatus.INACTIVE, date(2026, 8, 1)),
        _screen_with_rental("D", 0, landlord, ScreenStatus.POTENTIAL, date(2026, 8, 1)),
        _screen_with_rental("E", 0, landlord, ScreenStatus.ARCHIVED, date(2026, 8, 1)),
    ]
    repo = FakeScreenRepository(screens)

    result = DashboardSummaryUseCase(repo).execute(
        DashboardSummaryInput(threshold_days=30, today=date(2026, 7, 1))
    )

    assert result.total_screens == 5
    assert result.active_count == 2
    assert result.inactive_count == 1
    assert result.potential_count == 1
    assert result.archived_count == 1
    assert result.total_active_rent.amount == Decimal(30000)


def test_dashboard_summary_ending_soon_within_threshold() -> None:
    """В список «скоро заканчиваются» попадают только договоры в пределах порога (FR-9.5)."""
    landlord = uuid4()
    today = date(2026, 7, 1)
    screens = [
        _screen_with_rental("Скоро", 10000, landlord, ScreenStatus.ACTIVE, date(2026, 7, 15)),
        _screen_with_rental("Не скоро", 10000, landlord, ScreenStatus.ACTIVE, date(2027, 1, 1)),
        _screen_with_rental("Просрочен", 10000, landlord, ScreenStatus.ACTIVE, date(2026, 6, 20)),
    ]
    repo = FakeScreenRepository(screens)

    result = DashboardSummaryUseCase(repo).execute(
        DashboardSummaryInput(threshold_days=30, today=today)
    )

    names = {item.screen_name for item in result.ending_soon}
    assert names == {"Скоро", "Просрочен"}
    # Отсортировано по дате окончания — просроченный раньше «скоро».
    assert result.ending_soon[0].screen_name == "Просрочен"


def test_export_screens_use_case_by_ids() -> None:
    """С явным списком id выгружаются только они, фильтры игнорируются (FR-7.4)."""
    landlord = uuid4()
    ids = [uuid4(), uuid4(), uuid4()]
    screens = [
        _screen_with_rental("A", 1000, landlord, ScreenStatus.ACTIVE, date(2026, 8, 1), ids[0]),
        _screen_with_rental("B", 1000, landlord, ScreenStatus.ACTIVE, date(2026, 8, 1), ids[1]),
        _screen_with_rental("C", 1000, landlord, ScreenStatus.ACTIVE, date(2026, 8, 1), ids[2]),
    ]
    repo = FakeScreenRepository(screens)

    result = ExportScreensUseCase(repo).execute(
        ExportScreensInput(screen_ids=(ids[0], ids[2]))
    )

    assert {s.id for s in result} == {ids[0], ids[2]}


def test_export_screens_use_case_by_filters() -> None:
    """Без явных id применяются фильтры (FR-7.1–7.3); пустой вход = все экраны."""
    landlord = uuid4()
    screens = [
        _screen_with_rental("A", 1000, landlord, ScreenStatus.ACTIVE, date(2026, 8, 1)),
        _screen_with_rental("B", 1000, landlord, ScreenStatus.INACTIVE, date(2026, 8, 1)),
    ]
    repo = FakeScreenRepository(screens)

    active_only = ExportScreensUseCase(repo).execute(
        ExportScreensInput(filters=ScreenFilters(status=ScreenStatus.ACTIVE))
    )
    everyone = ExportScreensUseCase(repo).execute(ExportScreensInput())

    assert len(active_only) == 1
    assert active_only[0].name == "A"
    assert len(everyone) == 2


# --- Новые поля экрана: size + screen_type_id (backend-instruction §4–§5) ---


def _screen_type_repo_with_one() -> tuple[FakeScreenTypeRepository, int]:
    """Готовит репозиторий типов с одним существующим типом; возвращает (repo, type_id)."""
    from features.screen_types.application.dto import CreateScreenTypeInput
    from features.screen_types.application.use_cases import CreateScreenTypeUseCase

    st_repo = FakeScreenTypeRepository()
    screen_type = CreateScreenTypeUseCase(st_repo).execute(
        CreateScreenTypeInput(name="Вертикальный", code="vertical")
    )
    return st_repo, screen_type.id


def test_create_screen_use_case_persists_size_and_type() -> None:
    """Создание экрана сохраняет size и screen_type_id при существующем типе."""
    st_repo, type_id = _screen_type_repo_with_one()
    repo = FakeScreenRepository([])

    screen = CreateScreenUseCase(repo, st_repo).execute(
        CreateScreenInput(
            name="Экран",
            city_id=1,
            latitude=42.87,
            longitude=74.59,
            size="1920x1080",
            screen_type_id=type_id,
        )
    )

    assert screen.size == "1920x1080"
    assert screen.screen_type_id == type_id


def test_create_screen_use_case_rejects_unknown_type() -> None:
    """Несуществующий screen_type_id при создании → 422 (UnprocessableEntityError)."""
    st_repo, _ = _screen_type_repo_with_one()
    repo = FakeScreenRepository([])

    with pytest.raises(UnprocessableEntityError):
        CreateScreenUseCase(repo, st_repo).execute(
            CreateScreenInput(
                name="Экран",
                city_id=1,
                latitude=42.87,
                longitude=74.59,
                size="55\"",
                screen_type_id=999,  # такого типа нет
            )
        )


def test_create_screen_use_case_as_active_blocked_without_invariant() -> None:
    """POST со status=active в обход инвариантов активации → 409 (§3, enforce).

    У нового экрана нет фото/договора → create-as-active проходит тот же гард
    (mark_active) и отклоняется BusinessRuleViolation; экран не сохраняется.
    """
    st_repo, type_id = _screen_type_repo_with_one()
    repo = FakeScreenRepository([])

    with pytest.raises(BusinessRuleViolation):
        CreateScreenUseCase(repo, st_repo).execute(
            CreateScreenInput(
                name="Экран",
                city_id=1,
                latitude=42.87,
                longitude=74.59,
                size="1920x1080",
                screen_type_id=type_id,
                status=ScreenStatus.ACTIVE,
                landlord_id=uuid4(),
            )
        )


def test_create_screen_use_case_non_active_status_passes_through() -> None:
    """Создание с не-active статусом (potential/inactive) не трогает гард активации."""
    st_repo, type_id = _screen_type_repo_with_one()
    repo = FakeScreenRepository([])

    screen = CreateScreenUseCase(repo, st_repo).execute(
        CreateScreenInput(
            name="Экран",
            city_id=1,
            latitude=42.87,
            longitude=74.59,
            size="1920x1080",
            screen_type_id=type_id,
            status=ScreenStatus.INACTIVE,
        )
    )

    assert screen.status == ScreenStatus.INACTIVE


def test_update_screen_use_case_rejects_unknown_type() -> None:
    """Несуществующий screen_type_id при обновлении → 422 (UnprocessableEntityError)."""
    st_repo, type_id = _screen_type_repo_with_one()
    screen_id = uuid4()
    screen = Screen(
        name="Экран",
        city_id=1,
        location=GeoPoint(42.87, 74.59),
        size="1920x1080",
        screen_type_id=type_id,
        id=screen_id,
    )
    repo = FakeScreenRepository([screen])

    with pytest.raises(UnprocessableEntityError):
        UpdateScreenUseCase(repo, st_repo).execute(
            UpdateScreenInput(screen_id=screen_id, size="1280x720", screen_type_id=999)
        )


def test_update_screen_activate_blocked_without_invariant() -> None:
    """PATCH status=active в обход инвариантов активации → 409 (§3, закрытая API-дыра).

    Голый inactive-экран без арендодателя/фото/суммы/даты больше НЕ переводится в
    active «тихо» через UpdateScreen: mark_active бросает BusinessRuleViolation.
    """
    st_repo, type_id = _screen_type_repo_with_one()
    screen_id = uuid4()
    screen = Screen(
        name="Экран",
        city_id=1,
        location=GeoPoint(42.87, 74.59),
        status=ScreenStatus.INACTIVE,
        size="1920x1080",
        screen_type_id=type_id,
        id=screen_id,
    )
    repo = FakeScreenRepository([screen])

    with pytest.raises(BusinessRuleViolation):
        UpdateScreenUseCase(repo, st_repo).execute(
            UpdateScreenInput(
                screen_id=screen_id,
                size="1920x1080",
                screen_type_id=type_id,
                status=ScreenStatus.ACTIVE,
            )
        )


def test_update_screen_activates_when_invariant_met() -> None:
    """PATCH status=active проходит для пригодного экрана; НОВЫЙ договор не создаётся (§6.2).

    Экран уже несёт арендодателя, фото, договор (сумма) и rental_end_date —
    перевод в active валиден и не фиксирует дополнительный договор (это делает
    только ActivateScreenUseCase).
    """
    st_repo, type_id = _screen_type_repo_with_one()
    screen_id = uuid4()
    rental = RentalContract(Money(Decimal(10000)), date(2025, 1, 1), date(2025, 12, 31))
    screen = Screen(
        name="Экран",
        city_id=1,
        location=GeoPoint(42.87, 74.59),
        status=ScreenStatus.INACTIVE,
        landlord_id=uuid4(),
        rentals=[rental],
        attachments=[_attachment(AttachmentType.PHOTO, "screens/x/photo/p")],
        rental_end_date=date(2025, 12, 31),
        size="1920x1080",
        screen_type_id=type_id,
        id=screen_id,
    )
    repo = FakeScreenRepository([screen])

    result = UpdateScreenUseCase(repo, st_repo).execute(
        UpdateScreenInput(
            screen_id=screen_id,
            size="1920x1080",
            screen_type_id=type_id,
            status=ScreenStatus.ACTIVE,
        )
    )

    assert result.status == ScreenStatus.ACTIVE
    assert len(result.rentals) == 1  # новый договор не добавлялся


def test_list_screens_filter_by_screen_type_id() -> None:
    """Список фильтруется по screen_type_id; несуществующий тип даёт пустой результат (§4.3)."""
    vertical, horizontal = 1, 2
    screens = [
        Screen(name="V", city_id=1, location=GeoPoint(42.8, 74.5),
               size="a", screen_type_id=vertical, id=uuid4()),
        Screen(name="H", city_id=1, location=GeoPoint(42.8, 74.5),
               size="b", screen_type_id=horizontal, id=uuid4()),
    ]
    repo = FakeScreenRepository(screens)

    only_vertical = ListScreensUseCase(repo).execute(ScreenFilters(screen_type_id=vertical))
    assert [s.name for s in only_vertical] == ["V"]

    # Несуществующий тип → пустой список, а не ошибка.
    none = ListScreensUseCase(repo).execute(ScreenFilters(screen_type_id=999))
    assert none == []


def test_screen_create_schema_requires_non_empty_size_and_type() -> None:
    """Схема создания отклоняет пустой size и отсутствие screen_type_id (→ 422)."""
    # Пустой size недопустим.
    with pytest.raises(PydanticValidationError):
        ScreenCreate(name="Экран", city_id=1, latitude=42.8, longitude=74.5,
                     size="", screen_type_id=1)
    # Отсутствие size / screen_type_id недопустимо.
    with pytest.raises(PydanticValidationError):
        ScreenCreate(name="Экран", city_id=1, latitude=42.8, longitude=74.5)


# --- Авто-архивация по истечению аренды (FR-4.4) ---


class _FixedClock:
    """Часы с фиксированной датой — детерминированный источник «сегодня» для тестов."""

    def __init__(self, today: date) -> None:
        self._today = today

    def today_bishkek(self) -> date:
        return self._today


def _screen(
    status: ScreenStatus,
    rental_end_date: date | None,
    screen_id: UUID | None = None,
) -> Screen:
    """Экран заданного статуса с датой окончания аренды (для тестов истечения)."""
    return Screen(
        name="S",
        city_id=1,
        location=GeoPoint(42.87, 74.59),
        status=status,
        rental_end_date=rental_end_date,
        id=screen_id or uuid4(),
    )


_TODAY = date(2026, 7, 10)


@pytest.mark.parametrize("status", list(ScreenStatus))
@pytest.mark.parametrize(
    "rental_end_date, past",
    [
        (date(2026, 6, 1), True),    # прошлое → истекло (если active)
        (_TODAY, False),             # ГРАНИЦА: сегодня == последний день → ещё НЕ истёк
        (date(2026, 8, 1), False),   # будущее → не истекло
        (None, False),               # бессрочная → никогда не истекает
    ],
)
def test_is_rental_expired_matrix(
    status: ScreenStatus, rental_end_date: date | None, past: bool
) -> None:
    """Матрица is_rental_expired: истекает ТОЛЬКО активный с датой строго в прошлом.

    Граница today == rental_end_date → НЕ истёк (последний день включительно).
    Любой не-ACTIVE статус и NULL-дата → не истекает.
    """
    screen = _screen(status, rental_end_date)
    expected = status is ScreenStatus.ACTIVE and past
    assert screen.is_rental_expired(_TODAY) is expected


def test_archive_on_expiry_idempotent_and_targets_constant() -> None:
    """archive_on_expiry переводит просроченный в EXPIRY_TARGET_STATUS; повтор — no-op."""
    screen = _screen(ScreenStatus.ACTIVE, date(2026, 6, 1))

    assert screen.archive_on_expiry(_TODAY) is True
    assert screen.status is EXPIRY_TARGET_STATUS
    # Повторно уже не активен → изменений нет.
    assert screen.archive_on_expiry(_TODAY) is False


def test_archive_on_expiry_leaves_non_expired_untouched() -> None:
    """Непросроченные (будущая дата, NULL, не-active) archive_on_expiry не трогает."""
    for screen in [
        _screen(ScreenStatus.ACTIVE, date(2026, 8, 1)),   # будущее
        _screen(ScreenStatus.ACTIVE, None),               # бессрочная
        _screen(ScreenStatus.INACTIVE, date(2026, 6, 1)), # не active
    ]:
        before = screen.status
        assert screen.archive_on_expiry(_TODAY) is False
        assert screen.status is before


def test_archive_expired_predicate_parity_with_domain_rule() -> None:
    """Паритет: множество, что меняет archive_expired, совпадает с is_rental_expired.

    Защита от расхождения bulk-предиката репозитория и доменного правила (SSOT).
    """
    screens = [
        _screen(ScreenStatus.ACTIVE, date(2026, 6, 1)),    # истёк
        _screen(ScreenStatus.ACTIVE, _TODAY),              # граница — не истёк
        _screen(ScreenStatus.ACTIVE, date(2026, 8, 1)),    # будущее
        _screen(ScreenStatus.ACTIVE, None),                # бессрочная
        _screen(ScreenStatus.INACTIVE, date(2026, 6, 1)),  # не active
        _screen(ScreenStatus.POTENTIAL, date(2026, 6, 1)),
        _screen(ScreenStatus.ARCHIVED, date(2026, 6, 1)),
    ]
    expected_ids = {s.id for s in screens if s.is_rental_expired(_TODAY)}
    repo = FakeScreenRepository(screens)

    changed = repo.archive_expired(_TODAY)

    archived_ids = {
        s.id for s in repo.list() if s.status is EXPIRY_TARGET_STATUS and s.id in expected_ids
    }
    assert archived_ids == expected_ids
    assert changed == len(expected_ids) == 1


def test_expire_due_screens_use_case_archives_and_is_idempotent() -> None:
    """Сценарий архивирует просроченные и возвращает счётчик; повтор — 0 (идемпотентность)."""
    expired = _screen(ScreenStatus.ACTIVE, date(2026, 6, 1))
    safe = _screen(ScreenStatus.ACTIVE, date(2026, 8, 1))
    repo = FakeScreenRepository([expired, safe])
    use_case = ExpireDueScreensUseCase(repo, _FixedClock(_TODAY))

    assert use_case.execute() == 1
    assert repo.get_by_id(expired.id).status is EXPIRY_TARGET_STATUS
    assert repo.get_by_id(safe.id).status is ScreenStatus.ACTIVE
    # Второй прогон без новых просрочек не меняет ничего.
    assert use_case.execute() == 0


class _CountingUseCase:
    """Заглушка use case: считает вызовы execute() и возвращает фиксированный результат."""

    def __init__(self, result: int = 7) -> None:
        self.calls = 0
        self._result = result

    def execute(self) -> int:
        self.calls += 1
        return self._result


def test_expiry_sweep_guard_runs_once_per_day() -> None:
    """Guard: первый вызов в новый день исполняет use case; повтор с той же датой — 0 без него."""
    guard = ExpirySweepGuard()
    use_case = _CountingUseCase(result=7)
    today = _TODAY

    # Первый вызов дня → реальный прогон, возвращает результат use case.
    assert guard.run_if_new_day(use_case, today) == 7
    assert use_case.calls == 1

    # Повтор в тот же день → 0 и БЕЗ обращения к use case (throttle).
    assert guard.run_if_new_day(use_case, today) == 0
    assert use_case.calls == 1

    # Следующий день → снова триггерит.
    assert guard.run_if_new_day(use_case, date(2026, 7, 11)) == 7
    assert use_case.calls == 2


def test_expiry_sweep_guard_is_process_singleton() -> None:
    """get_expiry_sweep_guard() отдаёт один и тот же объект на процесс (lru_cache)."""
    assert get_expiry_sweep_guard() is get_expiry_sweep_guard()


def test_create_screen_use_case_persists_rental_end_date() -> None:
    """Создание экрана сохраняет rental_end_date (FR-4.4)."""
    st_repo, type_id = _screen_type_repo_with_one()
    repo = FakeScreenRepository([])

    screen = CreateScreenUseCase(repo, st_repo).execute(
        CreateScreenInput(
            name="Экран",
            city_id=1,
            latitude=42.87,
            longitude=74.59,
            size="1920x1080",
            screen_type_id=type_id,
            rental_end_date=date(2026, 12, 31),
        )
    )

    assert screen.rental_end_date == date(2026, 12, 31)


def test_update_screen_use_case_applies_and_clears_rental_end_date() -> None:
    """Update применяет дату только с флагом; явный null (с флагом) очищает её (§6)."""
    st_repo, type_id = _screen_type_repo_with_one()
    screen_id = uuid4()
    screen = Screen(
        name="Экран",
        city_id=1,
        location=GeoPoint(42.87, 74.59),
        size="1920x1080",
        screen_type_id=type_id,
        rental_end_date=date(2026, 12, 31),
        id=screen_id,
    )
    repo = FakeScreenRepository([screen])

    # Без флага дата НЕ трогается (обычный PATCH других полей).
    unchanged = UpdateScreenUseCase(repo, st_repo).execute(
        UpdateScreenInput(screen_id=screen_id, size="1280x720", screen_type_id=type_id, name="N")
    )
    assert unchanged.rental_end_date == date(2026, 12, 31)

    # Явный null с флагом → дата очищена (аренда стала бессрочной).
    cleared = UpdateScreenUseCase(repo, st_repo).execute(
        UpdateScreenInput(
            screen_id=screen_id,
            size="1280x720",
            screen_type_id=type_id,
            rental_end_date=None,
            apply_rental_end_date=True,
        )
    )
    assert cleared.rental_end_date is None
