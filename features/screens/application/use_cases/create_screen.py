"""create_screen.py — сценарий «Создать экран» (FR-10.1).

За что отвечает: принимает плоские входные данные (CreateScreenInput), собирает
из них доменную сущность Screen (валидируя адрес и координаты через value
objects) и сохраняет её через репозиторий. Возвращает созданный экран с id.

Почему логика тут, а не во вьюхе: создание — это сценарий приложения. Вьюха
лишь принимает HTTP-запрос и делегирует сюда; так сценарий можно переиспользовать
и тестировать без HTTP.
"""

from __future__ import annotations

from features.screens.application.dto import CreateScreenInput
from features.screens.domain.entities import Screen
from features.screens.domain.enums import ScreenStatus
from features.screens.domain.repositories import ScreenRepository
from features.screen_types.domain.repositories import ScreenTypeRepository
from core.application.use_case import UseCase
from core.domain.exceptions import UnprocessableEntityError
from core.domain.value_objects import GeoPoint


class CreateScreenUseCase(UseCase[CreateScreenInput, Screen]):
    """Создаёт новый экран из входных данных и сохраняет его в хранилище."""

    def __init__(
        self,
        repository: ScreenRepository,
        screen_type_repository: ScreenTypeRepository,
    ) -> None:
        """Получает репозитории через конструктор (внедрение зависимости, DIP).

        Сценарий зависит от интерфейсов (ScreenRepository, ScreenTypeRepository),
        а не от конкретной БД — в тестах сюда можно передать фейки в памяти.
        Репозиторий типов нужен, чтобы проверить существование screen_type_id
        и вернуть понятную 422, а не наткнуться на ошибку внешнего ключа.
        """
        self._repository = repository
        self._screen_types = screen_type_repository

    def execute(self, data: CreateScreenInput) -> Screen:
        """Собирает доменный Screen из DTO и сохраняет его.

        Валидация координат (диапазоны широты/долготы) происходит автоматически
        внутри value object GeoPoint — если данные некорректны, будет выброшена
        доменная ValidationError. Существование типа экрана проверяем явно:
        несуществующий screen_type_id → 422 (UnprocessableEntityError, §5).

        Прямое создание сразу как ACTIVE проходит ТОТ ЖЕ инвариант активации, что и
        остальные пути (§3, enforce): экран собираем в безопасном статусе, а затем
        переводим в active через mark_active() — он бросит BusinessRuleViolation
        (409), если инвариант не выполнен. У нового экрана нет ни фото, ни договора,
        поэтому create-as-active на практике отклоняется — активацию делают
        отдельным шагом (create → активация/загрузка фото).
        """
        if not self._screen_types.exists(data.screen_type_id):
            raise UnprocessableEntityError("Указанный тип экрана не найден")

        # Собираем гео-точку — здесь же сработает её проверка диапазонов.
        location = GeoPoint(latitude=data.latitude, longitude=data.longitude)

        # ACTIVE не проставляем прямо в конструкторе (это обошло бы гард) — экран
        # рождается в POTENTIAL, а переход в active идёт через mark_active() ниже.
        as_active = data.status is ScreenStatus.ACTIVE
        screen = Screen(
            name=data.name,
            city_id=data.city_id,
            location=location,
            status=ScreenStatus.POTENTIAL if as_active else data.status,
            landlord_id=data.landlord_id,
            contact_id=data.contact_id,
            campaign_ids=list(data.campaign_ids),  # DTO хранит кортеж → домену нужен список
            comment=data.comment,
            size=data.size,
            screen_type_id=data.screen_type_id,
            rental_end_date=data.rental_end_date,
        )
        if as_active:
            # Единый гард активации (арендодатель + фото + сумма + дата) → 409, если нет.
            screen.mark_active()

        # Репозиторий сохранит экран и вернёт его с присвоенным id.
        return self._repository.add(screen)
