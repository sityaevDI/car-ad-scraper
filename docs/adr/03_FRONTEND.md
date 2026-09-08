# Frontend

Заполняет пропуск в нумерации между `02_DOMAIN_MODEL.md` и `04_SCRAPING.md` — этот файл был
открытым вопросом (см. `18_DECISIONS_AND_OPEN_QUESTIONS.md` → "Open questions → Frontend").

## 1. Статус

`01_ARCHITECTURE.md` §8 и `17_AGENT_INSTRUCTIONS.md` (Step 12) ставят frontend последним шагом —
после auth/saved searches/notifications. Но backend уже реализовал Phase 1 core (`app/search`,
`app/listings`, `app/api/v1/vehicles.py`) — grouped/flat search по одному источнику, детали
объявления, история снапшотов. Auth, saved searches, follows, notifications, market page и admin
ещё не реализованы (нет роутов/моделей CRUD).

Поэтому этот документ описывает **frontend MVP, обрезанный по факту существующего API**, а не
весь Phase 1–2 из `07_USER_FLOWS.md`. Это осознанно меньший scope, чем "готовый продукт" —
покрывает только сценарий §1 "Anonymous browse" из `07_USER_FLOWS.md`.

## 2. Стек — решение открытого вопроса

`18_DECISIONS_AND_OPEN_QUESTIONS.md` оставлял выбор между Next.js и React+Vite, рекомендуя решать
по SEO-требованиям.

Решение: **React + TypeScript + Vite**, без SSR.

- SEO пока не требование — market-страниц с контентом для индексации ещё нет (Phase 3), сейчас это
  search-behind-interaction UI.
- Vite даёт быстрый старт и простой прод-билд (статика в Docker-образ, как сейчас `frontend/Dockerfile`).
- Next.js можно ввести позже, если появятся SEO-требования (публичные market-страницы, лендинги) —
  переписывать имеющиеся экраны на Next не критично, они простые.

Для "минимально симпатично" без дизайнера: **Tailwind CSS** + компонентная библиотека без своей
дизайн-системы (например shadcn/ui или headless примитивы + Tailwind). Не собирать кастомный UI-кит
для MVP.

## 3. Экраны MVP

### 3.1 Search & Results (главная и единственная обязательная страница)

Источник данных: `POST /api/v1/search` (`app/api/v1/search.py`, схемы в `app/search/query.py` и
`app/search/schemas.py`).

Фильтры формы — 1:1 с `SearchQuery`:
- make (один, select) + models (multi-select, зависит от make) — заполняются из
  `GET /api/v1/vehicles/makes`;
- year_min/year_max, price_min/price_max, mileage_min/max, engine_volume_min/max, power_min/max;
- fuel_types, transmissions, body_types (multi-select);
- location (текстовое поле).

Group by — чекбоксы, дефолт как в `SearchRequest.group_by`:
`make, model, engine_volume_cc, fuel_type, transmission` (можно убрать любой, добавить
`production_year`, `body_type`).

Сортировка (`sort`) — из `_FLAT_SORTS` (`app/search/service.py`): `price_asc`, `price_desc`,
`mileage_asc`, `mileage_desc`, `year_desc`, `first_seen_desc`, плюс `count_desc` для groups.

Результат — `SearchResponse`: либо `groups` (когда `group_by` задан), либо `listings` (когда
`group_by: []`/`null`). UI:
- **Group card**: `label`, `count`, price/year/mileage range (`price_min–price_max`,
  `year_min–year_max`, `mileage_min–mileage_max`), currency. При разворачивании — см. §4.3.
- **Flat listing row/card**: `title`, `make/model/production_year`, `price`, `mileage_km`,
  `fuel_type`/`transmission`/`body_type` как теги, ссылка `canonical_url` (target=_blank).
- Пагинация — `page`/`page_size`, `total_listings`/`total_groups` уже есть в ответе; **старый
  фронт пагинации не имел вообще**, это обязательно для MVP.

### 3.2 Listing Detail

Источник: `GET /api/v1/listings/{id}` + `GET /api/v1/listings/{id}/history`.

Показывать: все поля `ListingOut` (make/model/year/mileage/price/fuel/transmission/body/engine/
power/location/status/first_seen_at/last_seen_at/last_checked_at) + таблицу/график снапшотов
(`ListingSnapshotOut`: captured_at, price, mileage_km, title) — минимум таблица "дата — цена",
график можно отложить.

`status: removed` — явно показать бейджем ("снято с публикации"), не прятать.

Фото: `ListingOut.image_url` (добавлено, см. §5.4) — показывать на flat-карточках и на detail.
На group-карточках фото не будет в MVP — групповой запрос агрегатный, без ссылки ни на одно
конкретное объявление (см. §5.3).

## 4. Что переносим из PoC-фронта (`frontend/index.html`, `script.js`)

Идеи, которые стоит сохранить как UX-паттерны:
- переключаемые group-by чекбоксы;
- порог `min-count` для групп — теперь есть на backend как `SearchRequest.min_group_count`
  (см. §5.5), отсекает неликвидные малочисленные группы прямо в SQL (`HAVING count(*) >= N`);
- разворачиваемые карточки групп (`Show/Hide`) с сортировкой внутри группы;
- каскадный select make → model через `/vehicles/makes` (эндпоинт сохранился, форма и логика те же);
- прямая ссылка на исходное объявление в новой вкладке.

Что явно не переносим как есть — старый UI: без пагинации, без loading/error-состояний, без
мобильной адаптации, вёрстка на голом CSS + jQuery + Select2. Ни разу не тестировался на экране
уже даже планшета. Для MVP это неприемлемо — состояния и адаптивность нужны с первой итерации
(см. §6).

## 5. Пробелы API относительно PoC — статус решений (2026-09-08)

1. **"Search by URL"** — не входит в MVP frontend, как и было решено. Блокер тот же: нет
   `POST /scrape/jobs`, и `11_SECURITY.md` запрещает принимать сырой URL от пользователя (SSRF).
   Кнопку "Update market" добавить после Phase 2, через allowlisted source adapters.
2. **Множественные include/exclude фильтры по make/model** — решено оставить как отдельную
   фичу вне MVP, а не блокировать им текущую работу. `SearchQuery` пока поддерживает один `make`
   + список `models`. MVP frontend ограничивается одной маркой за раз (текущий контракт API).
   Мультибрендовый include/exclude — задача на будущее (расширение `SearchQuery.make` до списка
   с include/exclude семантикой, как в старом `api.py`/`_uri_params_to_specs`) — завести отдельным
   issue, не блокирует текущую фронтенд-работу.
3. **Список объявлений внутри группы** — решено: (a), второй запрос с фронта. При разворачивании
   группы frontend делает `POST /search` с `group_by: null` и фильтрами, реконструированными из
   ключа группы (`make`, `models: [group.model]`, `fuel_types: [group.fuel_type]`,
   `transmissions: [group.transmission]`, `body_types: [group.body_type]`,
   `year_min=year_max=group.production_year` при наличии, и
   `engine_volume_min/max = bucket-50/bucket+49` для `engine_volume_cc`, воспроизводя округление
   из `_ENGINE_VOLUME_BUCKET` в `app/search/service.py`). Backend не менялся — все нужные фильтры
   уже есть в `SearchQuery`.

   **Кэширование drill-down запросов** — рассматривали (много юзеров разворачивают одну и ту же
   популярную группу → повторяющиеся одинаковые flat-запросы), но решено НЕ добавлять сейчас:
   `16_MVP_ROADMAP.md` Phase 6 ("Scaling") уже относит "more aggressive caching" на потом, "только
   после реальной нагрузки". Redis-слой кэша под конкретные группы — это инвалидация при каждом
   апдейте листинга/снапшота, TTL-политика, доп. сложность — не оправдано при текущем объёме данных
   (один источник, Phase 1). Если это станет узким местом, дешевле начать с индекса на
   group-by-колонках (`fuel_type`, `transmission`, `body_type`, `production_year`,
   `engine_volume_cc` — сейчас индексированы только `make`/`model`), а не с кэша. Решение
   зафиксировано здесь, отдельного issue не заводим — пересмотреть в Phase 6.
4. **Фото объявления** — решено: добавлено. `Listing.image_url` (nullable, миграция
   `a1b2c3d4e5f6_add_listing_image_url`), `ListingOut.image_url`, заполняется в
   `app/sources/polovniautomobili/mapper.py` (`imageMain` на search-странице источника,
   первое по `ordering` изображение из `productData.images` на странице объявления). Group-карточки
   по-прежнему без фото — см. §3.2.
5. **`min-count`** — решено: добавлено. `SearchRequest.min_group_count: int | None`, применяется
   как `HAVING count(*) >= N` в `app/search/service.py._search_grouped` — фильтрация групп на
   уровне SQL, а не на фронте после получения полного списка.

## 6. Обязательные UI-состояния (отсутствовали в PoC)

- Loading (skeleton или спиннер на search/detail);
- Empty results (ничего не найдено — с подсказкой ослабить фильтры);
- Error (сеть/5xx — сообщение, retry, без raw error пользователю — см. `11_SECURITY.md`);
- Responsive: минимум 3 брейкпоинта (mobile/tablet/desktop), карточки групп должны схлопываться
  в одну колонку на мобильном — PoC был fixed 300px inline-block, на мобильном не работает.

## 7. Explicitly не в MVP frontend

Всё, для чего ещё нет backend-реализации (роутов/моделей нет в `app/`):
- login/register/auth (нет `app/auth` роутов, только `app/models/user.py` — schema-only);
- saved searches, follow listing, notifications (`app/models/saved_search.py`,
  `notification.py` — schema-only, без CRUD);
- market/analytics page с ценовым score и confidence (`06_SEARCH_MARKET.md` §5-7 —
  `app/search/service.py` намеренно не считает market price в MVP, см. докстринг там же);
- admin dashboard (`13_ADMIN.md`) — нет `app/admin` роутов;
- billing/subscription UI (`app/models/subscription.py` — schema-only).

Эти экраны — предмет отдельных документов по мере того, как их backend появится (roadmap Phase 2+,
`16_MVP_ROADMAP.md`).

## 8. Открытые вопросы

Все backend-пробелы из §5, блокировавшие MVP frontend (image_url, group drill-down, min-count),
решены — см. §5. Остаётся:

- Аутентификация фронта (cookie vs JWT) — всё ещё открытый вопрос в
  `18_DECISIONS_AND_OPEN_QUESTIONS.md`, но не блокирует MVP frontend (Anonymous browse не требует
  auth).
- Мультибрендовый include/exclude (§5 п.2) — сознательно отложен как отдельная фича, не блокер.
