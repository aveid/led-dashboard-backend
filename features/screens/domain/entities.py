"""entities.py — сущности домена «экраны»: Screen (корень), RentalContract, Attachment.

За что отвечает модуль:
    Определяет главные объекты предметной области и их ПОВЕДЕНИЕ (бизнес-правила).
    Ключевая идея Clean Architecture: правила живут в сущностях, а не во вьюхах
    или сериализаторах.

Модель учитывает решения по открытым вопросам ТЗ:
    • Q3 — история аренды: у экрана хранится СПИСОК договоров (rentals), а «текущий»
      договор вычисляется (current_rental). Прошлые договоры остаются как история.
    • Q2 — один арендодатель на экран: landlord_id — одиночная связь.
    • Q4 — кампании: экран хранит СПИСОК кампаний (campaign_ids) с заделом на несколько;
      сейчас в карточке показывается одна текущая (current_campaign_id).
    • Q1 — аренда помесячная: цена договора трактуется как «сом/мес».

Здесь нет ни Django, ни HTTP, ни SQL — только чистая логика предметной области.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from core.domain.entity import Entity
from core.domain.exceptions import BusinessRuleViolation, ValidationError
from core.domain.value_objects import GeoPoint, Money
from features.cities.domain.entities import City
from features.screen_types.domain.entities import ScreenType

from .constants import EXPIRY_TARGET_STATUS
from .enums import AttachmentType, ScreenStatus


class RentalContract(Entity):
    """Договор аренды экрана за некоторый период (Q3: элемент истории аренды).

    Одна запись = один период аренды с ценой. У экрана таких записей может быть
    несколько (текущая + прошлые). Это отдельная сущность (с id), потому что мы
    храним и, возможно, будем ссылаться на конкретные договоры (история, FR-3.9).

    Файл самого договора хранится отдельно как вложение (Attachment типа CONTRACT);
    здесь — только условия (цена и срок).
    """

    def __init__(
        self,
        rent_price: Money,   # стоимость аренды в месяц (Q1), в сомах
        start_date: date,    # дата начала аренды (FR-3.8)
        end_date: date,      # дата окончания договора (FR-3.9)
        id: UUID | None = None,
    ) -> None:
        """Создаёт договор и проверяет, что дата окончания не раньше начала."""
        super().__init__(id=id)
        if end_date < start_date:
            raise ValidationError(
                "Дата окончания договора не может быть раньше даты начала."
            )
        self.rent_price = rent_price
        self.start_date = start_date
        self.end_date = end_date


class Attachment(Entity):
    """Файл, прикреплённый к экрану: фото, договор или иной документ (FR-3.12/3.13).

    Домен не хранит байты и не знает про S3/URL. Он хранит ВНУТРЕННИЙ ключ объекта
    в хранилище (object_key, наружу не отдаётся) и метаданные файла (имя, MIME,
    размер). Короткоживущую ссылку на скачивание собирает внешний слой из object_key
    через порт FileStorage — так домен остаётся чистым (нет boto3/URL).
    """

    def __init__(
        self,
        type: AttachmentType,
        object_key: str,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        uploaded_at: datetime,
        id: UUID | None = None,
    ) -> None:
        """Создаёт вложение (тип, ключ объекта, метаданные файла, время загрузки, id)."""
        super().__init__(id=id)
        self.type = type
        self.object_key = object_key
        self.original_filename = original_filename
        self.content_type = content_type
        self.size_bytes = size_bytes
        self.uploaded_at = uploaded_at


class Screen(Entity):
    """LED-экран — корневая сущность (aggregate root) фичи.

    Собирает воедино все данные экрана (FR-3): название, город, точку на карте,
    статус, арендодателя, контакт, кампании, историю аренды, комментарий и
    вложения. Через его методы происходят все изменения состояния — это гарантирует,
    что бизнес-правила нельзя обойти.

    Точный адрес (район/улица) в модели больше не хранится (FR-3.3): расположение
    экрана задаётся точкой на карте (location), а не текстом.
    """

    def __init__(
        self,
        name: str,
        city_id: int,
        location: GeoPoint,
        status: ScreenStatus = ScreenStatus.POTENTIAL,
        landlord_id: UUID | None = None,
        contact_id: UUID | None = None,
        campaign_ids: list[UUID] | None = None,
        rentals: list[RentalContract] | None = None,
        comment: str = "",
        attachments: list[Attachment] | None = None,
        size: str = "",
        screen_type_id: int | None = None,
        screen_type: ScreenType | None = None,
        city: City | None = None,
        rental_end_date: date | None = None,
        id: UUID | None = None,
    ) -> None:
        """Создаёт экран. Новый экран по умолчанию имеет статус «потенциальный».

        Город указывается обязательным city_id (ссылка на справочник City) — по
        нему работает фильтр (FR-5.3) и внешний ключ в БД. Необязательный city —
        уже загруженная сущность города для отображения (карточка/список): её
        подставляет инфраструктурный маппер при чтении. При создании/обновлении
        экрана достаточно city_id, а city остаётся None.

        rentals (история договоров) заполняется через activate(); напрямую при
        создании обычно пуст. campaign_ids — размещённые кампании (сейчас 0 или 1).
        Изменяемые списки по умолчанию создаём внутри (не в сигнатуре) — это
        защищает от классической ловушки общего изменяемого значения по умолчанию.

        rental_end_date — последний день действия аренды ВКЛЮЧИТЕЛЬНО (FR-4.4).
        None — бессрочная/rolling аренда: экран не истекает никогда. По истечению
        (когда «сегодня» перевалит за эту дату) авто-архивация переведёт активный
        экран в EXPIRY_TARGET_STATUS — см. is_rental_expired/archive_on_expiry.

        size — свободный текстовый размер экрана (напр. «1920x1080», «55"»). На
        уровне домена пустая строка допустима: это исторические записи (после
        backfill у старых экранов size = ''). Требование «непустой при create/update
        через форму» — правило границы (Pydantic-схема), а не инвариант сущности.
        screen_type_id — ссылка на справочник ScreenType (обязательна в БД, NOT NULL);
        по умолчанию None лишь для удобства сборки в тестах — реальное создание
        всегда проставляет его. screen_type — уже загруженный тип для отображения
        (карточка/список): его подставляет инфраструктурный маппер при чтении.
        """
        super().__init__(id=id)
        self.name = name
        self.city_id = city_id
        self.location = location
        self.status = status
        self.landlord_id = landlord_id
        self.contact_id = contact_id
        self.campaign_ids = campaign_ids if campaign_ids is not None else []
        self.rentals = rentals if rentals is not None else []
        self.comment = comment
        self.attachments = attachments if attachments is not None else []
        self.size = size
        self.screen_type_id = screen_type_id
        self.screen_type = screen_type
        self.city = city
        self.rental_end_date = rental_end_date

    # --- Запросы (не меняют состояние) ---

    def is_rental_expired(self, today: date) -> bool:
        """Истекла ли аренда экрана на дату `today` (SSOT перехода авто-архивации, FR-4.4).

        Экран считается просроченным, только когда ВСЕ условия истинны:
            • он сейчас активен (ACTIVE) — архивируем лишь арендуемые экраны;
            • у него задана дата окончания (rental_end_date is not None);
            • «сегодня» уже ПОЗЖЕ последнего дня действия: today > rental_end_date
              (rental_end_date — последний день включительно, поэтому в сам этот
              день экран ещё НЕ просрочен).

        `today` обязан быть датой в тайзоне Asia/Bishkek (UTC+6) — так граница суток
        совпадает с throttle авто-архивации. Это единственный источник правды о
        переходе: bulk-предикат репозитория (archive_expired) обязан его зеркалить.
        """
        return (
            self.status is ScreenStatus.ACTIVE
            and self.rental_end_date is not None
            and today > self.rental_end_date
        )

    @property
    def current_rental(self) -> RentalContract | None:
        """Текущий договор аренды или None, если экран сейчас не арендуется.

        Текущим считаем самый свежий договор (по дате начала) — но только если
        экран в статусе «активный». В неактивном/архивном состоянии текущего
        договора нет, хотя история (rentals) сохраняется. Логика детерминирована
        (не зависит от «сегодня»), поэтому легко тестируется.
        """
        if self.status != ScreenStatus.ACTIVE or not self.rentals:
            return None
        return max(self.rentals, key=lambda r: r.start_date)

    @property
    def monthly_price(self) -> Money:
        """Стоимость аренды экрана в месяц (по текущему договору), иначе ноль.

        Используется при расчёте стоимости выбранных экранов (FR-6).
        """
        rental = self.current_rental
        return rental.rent_price if rental else Money.zero()

    @property
    def current_campaign_id(self) -> UUID | None:
        """Текущая кампания на экране для карточки (FR-3.10).

        Сейчас на экране одна кампания (Q4), поэтому возвращаем первую из списка.
        Когда бизнес разрешит несколько одновременно — здесь появится выбор
        «текущей» (например, по флагу/периоду), а хранилище уже поддерживает список.
        """
        return self.campaign_ids[0] if self.campaign_ids else None

    def has_attachment_of_type(self, attachment_type: AttachmentType) -> bool:
        """Проверяет, есть ли у экрана прикреплённый файл нужного типа.

        Нужно для правила активации (требуется фото) и для выгрузки в Excel
        (колонка «есть договор?»). Наличие договора для активации больше не требуется.
        """
        return any(a.type == attachment_type for a in self.attachments)

    # --- Команды (меняют состояние, соблюдая бизнес-правила) ---

    def relocate(self, location: GeoPoint) -> None:
        """Переносит экран в новую точку на карте (FR-3.3).

        Точечная операция «перетащить пин и сохранить»: меняет только координаты,
        не трогая остальные поля. Диапазоны широты/долготы уже проверены в GeoPoint
        (иначе объект не создался бы), поэтому здесь достаточно присвоения.
        """
        self.location = location

    def add_attachment(self, attachment: Attachment) -> None:
        """Прикрепляет к экрану файл (фото/договор/документ)."""
        self.attachments.append(attachment)

    def set_campaign(self, campaign_id: UUID | None) -> None:
        """Задаёт текущую кампанию экрана (FR-3.10). None — снять кампанию.

        Сейчас поддерживается одна кампания (Q4): метод заменяет список. Для
        нескольких одновременно позже добавим отдельный метод assign_campaign().
        """
        self.campaign_ids = [campaign_id] if campaign_id is not None else []

    def _latest_rental_price(self) -> Money:
        """Цена самого свежего договора БЕЗ учёта статуса (для гарда до смены статуса).

        Свойство monthly_price/current_rental возвращают ноль, пока экран ещё не
        ACTIVE (они гейтят по статусу). Но единый гард активации проверяет сумму
        аренды ДО фактической смены статуса — на пути mark_active (PATCH/create)
        сумму берём отсюда: из последнего по дате начала договора истории.
        Нет договоров → нулевая сумма, и гард отклонит активацию (§5).
        """
        if not self.rentals:
            return Money.zero()
        return max(self.rentals, key=lambda r: r.start_date).rent_price

    def _ensure_activatable(self, monthly_price: Money) -> None:
        """Единый инвариант «экран пригоден быть ACTIVE» — SSOT всех путей активации.

        Через этот гард проходит ЛЮБОЙ переход в ACTIVE (activate / mark_active /
        create-as-active), поэтому расхождения между путями исключены. Требования:
            • указан арендодатель (FR-4.2);
            • прикреплено фото — Attachment типа PHOTO (FR-4.2);
            • задана сумма аренды: monthly_price > 0 (§5);
            • задана дата окончания аренды: rental_end_date is not None (§5).
        Любое нарушение → BusinessRuleViolation (представление → HTTP 409). Нового
        типа ошибки не заводим — контракт 409 прежний.

        Сумму аренды принимаем ПАРАМЕТРОМ, а не через self.monthly_price: гард
        вызывается ДО смены статуса, а свойство вернуло бы ноль, пока статус не
        ACTIVE (current_rental гейтит по ACTIVE). Наличие фото читаем из
        self.attachments — они уже загружены репозиторием при чтении экрана (тот же
        источник, что использует и activate()).
        """
        if self.landlord_id is None:
            raise BusinessRuleViolation(
                "Нельзя активировать экран: не указан арендодатель."
            )
        if not self.has_attachment_of_type(AttachmentType.PHOTO):
            raise BusinessRuleViolation(
                "Нельзя активировать экран: не прикреплено фото."
            )
        if monthly_price.amount <= 0:
            raise BusinessRuleViolation(
                "Нельзя активировать экран: не указана сумма аренды."
            )
        if self.rental_end_date is None:
            raise BusinessRuleViolation(
                "Нельзя активировать экран: не указана дата окончания аренды."
            )

    def mark_active(self) -> None:
        """Переводит экран в ACTIVE, проверяя единый инвариант активации (FR-4.2 + §5).

        Раньше это был «тихий» переход без предусловий, из-за чего в active можно
        было попасть в обход инвариантов напрямую через API (PATCH status=active,
        create-as-active), минуя UI. Теперь mark_active проходит ТОТ ЖЕ гард, что и
        activate() — арендодатель, фото, сумма аренды и дата окончания — единый
        источник истины, расхождения между путями активации больше нет.

        Договор аренды при этом НЕ фиксируется (это делает activate(rental)); сумму
        берём из уже существующей истории аренды экрана. Нарушение инварианта →
        BusinessRuleViolation (представление → HTTP 409).
        """
        self._ensure_activatable(self._latest_rental_price())
        self.status = ScreenStatus.ACTIVE

    def activate(self, rental: RentalContract) -> None:
        """Активирует экран и фиксирует договор аренды в истории. Правило FR-4.2 + §5.

        Явный сценарий «оформить аренду»: помимо перевода в статус «активный» он
        принимает условия договора (rental) и добавляет их в историю (rentals),
        делая договор текущим.

        Активировать этим путём можно, только если выполнен единый инвариант
        активации (см. _ensure_activatable): указан арендодатель, прикреплено фото
        (Attachment типа PHOTO), задана сумма аренды и дата окончания. Иначе —
        BusinessRuleViolation (представление вернёт HTTP 409).

        NOTE: наличие ДОГОВОРА (Attachment типа CONTRACT) не требуется — договор
        перестал быть предусловием активации (остаётся опциональными данными).
        """
        # Дата окончания договора становится датой окончания аренды экрана: активный
        # экран обязан иметь срок (§5) и авто-архивируется по нему (FR-4.4). Ставим
        # ДО гарда, чтобы инвариант «есть дата окончания» проверялся против срока
        # этого же договора (rental.end_date у RentalContract всегда задан).
        self.rental_end_date = rental.end_date
        # Сумму аренды для гарда берём из этого договора (в self.rentals он ещё не
        # добавлен, а свойство monthly_price до смены статуса вернуло бы ноль).
        self._ensure_activatable(rental.rent_price)
        self.rentals.append(rental)
        self.status = ScreenStatus.ACTIVE

    def deactivate(self) -> None:
        """Снимает экран с аренды: статус «неактивный».

        История договоров (rentals) сохраняется, но текущего договора больше нет
        (current_rental вернёт None)."""
        self.status = ScreenStatus.INACTIVE

    def mark_potential(self) -> None:
        """Переводит экран в статус «потенциальный» (рассматривается для аренды)."""
        self.status = ScreenStatus.POTENTIAL

    def archive(self) -> None:
        """Архивирует экран: статус «архивный» (больше не актуален)."""
        self.status = ScreenStatus.ARCHIVED

    def archive_on_expiry(self, today: date) -> bool:
        """Каноничный переход авто-архивации по истечению аренды (FR-4.4). Идемпотентен.

        Если аренда истекла (is_rental_expired), переводит экран в
        EXPIRY_TARGET_STATUS и возвращает True; иначе не трогает состояние и
        возвращает False. На «горячем» пути чтения НЕ используется (там идёт один
        bulk-UPDATE, см. ScreenRepository.archive_expired) — но служит SSOT для
        теста-паритета и доменно-чистой альтернативы (будущий Celery-beat, FR-9.5).
        """
        if self.is_rental_expired(today):
            self.status = EXPIRY_TARGET_STATUS
            return True
        return False
