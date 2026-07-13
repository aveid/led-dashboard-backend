# CONTEXT: FastAPI Backend
# Rule: domain/ is PURE Python. Imports point inward only — no fastapi/sqlalchemy/pydantic inside domain.

## 1. Tech Stack
- Python 3.12+, FastAPI, Pydantic v2.
- SQLAlchemy 2.0 (sync, connection pool), Alembic for migrations.
- PostgreSQL 16 + PostGIS, GeoAlchemy2 + shapely (`Geometry(POINT, 4326)`).
- Object storage: MinIO (S3-compatible) via `boto3` — `S3FileStorage` implements domain `FileStoragePort`.
- Money: `Decimal` only, everywhere. Geo coordinates are the one exception — `float`, validated
  `-90≤lat≤90`, `-180≤lng≤180` (`Coordinates` VO → `InvalidCoordinatesError`).
- Dep pin: `bcrypt<4.1` (passlib 1.7.4 is incompatible with newer bcrypt).

## 2. Domain Entities & Invariants

### Screen (aggregate root)
Fields: `name`, `city_id` (FK→cities, `RESTRICT`), `screen_type_id` (FK→screen_types, `RESTRICT`),
`size` (str, required), coordinates (`Coordinates` VO, PostGIS point), `status`, `landlord_id`,
rentals (→ `monthly_price`), `rental_end_date: date | None`, `attachments[]`.

- **Activation gate — single source of truth: `Screen._ensure_activatable(monthly_price)`.**
  All three paths into `active` go through it (`POST .../activate`, `PATCH status=active`,
  create-as-active). Requires: `landlord_id` set, at least one `PHOTO` attachment,
  `monthly_price > 0`, `rental_end_date` set. Violation → `BusinessRuleViolation` → 409.
  `activate()` sets `rental_end_date = rental.end_date` as a side effect.
- **Auto-archive on expiry (FR-4.4).** `Screen.is_rental_expired` ⇔ `status == ACTIVE and
  rental_end_date is not None and today(Asia/Bishkek) > rental_end_date` (last day inclusive;
  `NULL` never expires). Target status: `ScreenStatus.ARCHIVED` (constant in
  `features/screens/domain/constants.py`). Bulk sweep `ScreenRepository.archive_expired(today)`
  — one idempotent `UPDATE`, mirrors the domain predicate exactly. Triggered via
  `Depends(expire_due_screens)` on every status-dependent read route (list, detail, dashboard,
  export, landlord-screens) in the same DB session, with an explicit `db.commit()` after a real
  sweep; throttled to once per day per process (`ExpirySweepGuard`, `lru_cache` singleton).
- `ScreenUpdate.rental_end_date` distinguishes "not sent" from explicit `null` via
  `model_fields_set` — `null` clears the date (reactivation path).
- No `district`/`street` columns (dropped). Location changes go through the narrow
  `PATCH /api/screens/{id}/location` (`{lng, lat}` → `ScreenRead`; 404 `SCREEN_NOT_FOUND`).

### City — `features/cities`, DB entity (not an enum)
Table `cities`, CRUD `/api/cities`. `Screen.city_id` FK (`RESTRICT`). `ScreenRead` nests the
full `city` object. Screen list / Excel export filter by `?city_id`.

### ScreenType — `features/screen_types`, DB entity (not an enum)
Table `screen_types`, CRUD `/api/screen-types` (JWT). `name` unique (case-insensitive), `code`
unique-if-set (`^[a-z0-9_-]+$`), seeded (vertical/horizontal/square/stop). `Screen.screen_type_id`
FK (`RESTRICT`, required) + `size` (str, required) — both mandatory on create/update.
- List envelope is `{data, meta:{total,page,per_page}}` with `?search=&page=&per_page=` —
  **the one list that isn't a bare array** (cities/screens/landlords/campaigns/users are bare arrays).
- Duplicate name/code → 422 (`UnprocessableEntityError`, distinct from `ValidationError`→400).
  Unknown `screen_type_id` on screen create/update → 422. Deleting an in-use type → 409
  `{"code":"screen_type_in_use","used_by_count":N}`.

### Attachment — `features/screens`, entity (not a bare file)
Table `attachments`, FK `screen_id` (`CASCADE`). Enum `AttachmentType`: `PHOTO`|`CONTRACT`|`OTHER`.
- Upload `POST /api/screens/{id}/attachments` (multipart: `file`, `kind`); delete
  `DELETE .../attachments/{aid}` → 204, scoped by both `id` and `screen_id` (blocks cross-screen
  delete). DB row is the source of truth — S3 object removal on delete is best-effort.
- `ScreenRead.attachments[]` items carry a short-lived **presigned GET url** (media viewable
  without JWT); the domain entity itself only holds `object_key`.
- **Cap:** max 5 per kind per screen (PHOTO and non-PHOTO counted separately, ≤10 total). SSOT =
  domain constant `MAX_ATTACHMENTS_PER_KIND = 5` (app-level, no migration). Checked before the S3
  `put`. Overflow → 409 `{"code":"ATTACHMENT_LIMIT_EXCEEDED","kind":...,"max":5}`.
- Object key: `media/screens/{screen_id}/{uuid}{ext}`, never leading `/`. Human filename lives in
  `original_filename` (DB) + `Content-Disposition`, never in the key. Presign signs against
  `S3_PUBLIC_ENDPOINT_URL` (separate from the internal put/delete endpoint); MinIO CORS via
  `MINIO_API_CORS_ALLOW_ORIGIN`.

### Users & RBAC — `features/users` (NFR-8)
Three roles: `admin`, `user`, `guest` (string enum). Real DB-backed auth — `POST /api/auth/token`
checks a bcrypt hash in `users`, not env credentials. `GET /api/auth/me` → `UserRead` is the SSOT
for the current role (role is not embedded in the JWT — resolved from DB on every request, so
demotion/deactivation takes effect immediately, no stale-token window).
- Access rule: any `GET` / export — any authenticated role; any `POST/PATCH/DELETE` — `admin`
  only (`Depends(require_admin)`). Non-admin on an admin route → 403 `{"code":"ADMIN_ONLY"}`.
- `guest` = `user` for access, plus response redaction (presentation layer only, domain
  untouched): money fields forced to `null` (never `0`) on screens/cost-summary/dashboard/
  landlord-screens/Excel export; non-`PHOTO` attachments filtered out before presigning (URLs
  for contracts are never generated for guests). Dashboard route is additionally gated
  `Depends(require_non_guest)` → guest gets 403 `{"code":"GUEST_FORBIDDEN"}`.
  Redaction helpers live in `features/screens/presentation/guest_redaction.py`.
- Invariants: last active admin can't be deleted/demoted/deactivated → 409 `LAST_ADMIN`;
  self demote/delete/deactivate → 409 `CANNOT_MODIFY_SELF`. Username uniqueness is
  case-insensitive (422 on duplicate). First admin is bootstrapped by migration from
  `INITIAL_ADMIN_USERNAME`/`INITIAL_ADMIN_PASSWORD` env (idempotent upsert).

### Geo boundary — FR-1.6, spec only, not implemented
Planned: `GET /api/geo/kyrgyzstan` (JWT) → `{name, iso3, bbox, rings:[[lng,lat],...]}` read from a
bundled static asset. Deliberately no domain/application/infrastructure/DB — pure presentation
router + Pydantic schema, `lru_cache`'d, `Cache-Control: max-age=86400`.

## 3. Architecture Layers
- `domain` — pure Python: entities, value objects, enums, repository ports
  (`FileStoragePort`, `AttachmentRepositoryPort`, `LandlordRepositoryPort`, `ScreenRepositoryPort`, ...).
- `application` — use cases + DTOs, depends only on `domain`. Presigned-URL assembly happens here.
- `infrastructure` — SQLAlchemy models, repository implementations, mappers, `S3FileStorage`.
- `presentation` — FastAPI routers, Pydantic request/response schemas, `Depends`.

## 4. Coding Rules
1. Money: `Decimal` only, everywhere (geo coordinates are the sole `float` exception).
2. Sync SQLAlchemy sessions via `Depends(get_db)`; endpoints are sync `def`.
3. Repositories return pure domain entities — never SQLAlchemy ORM models.
4. One object-key builder shared by upload and presign (see Attachment above).
5. Any column add/drop needs an Alembic revision with a safe, tested `downgrade`.
6. **Error body format — always under `detail`:** domain errors → `{"detail": "<message>"}`
   (string); Pydantic validation → `{"detail": [...]}` (list); machine-readable business errors →
   `{"detail": {"code": ..., ...}}` (object — e.g. `screen_type_in_use`, `ATTACHMENT_LIMIT_EXCEEDED`,
   `SCREEN_NOT_FOUND`, `LANDLORD_NOT_FOUND`, `LAST_ADMIN`, `CANNOT_MODIFY_SELF`, `ADMIN_ONLY`,
   `GUEST_FORBIDDEN`). No other error envelope exists in the codebase.

## 5. API Surface — endpoints beyond obvious CRUD
- `PATCH /api/screens/{id}/location` — `{lng, lat}` → `ScreenRead`. 404 if missing.
- `GET /api/landlords/{id}/screens` — bare array of `LandlordScreenBrief`
  (`id,name,status,size,city,screen_type,lng,lat,monthly_price|null`). No attachments, no presign
  (compact by design). 404 `LANDLORD_NOT_FOUND`; existing landlord with none → `200 []`.
- `GET /api/auth/me` — current user, SSOT for role.
- `GET /api/geo/kyrgyzstan` — planned, not built (see Geo boundary above).
- List envelopes: bare array everywhere (`cities`, `screens`, `landlords`, `campaigns`, `users`,
  landlord-screens) except `screen-types`, which uses `{data, meta}`.
