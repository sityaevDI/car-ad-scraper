# Доменная модель

## 1. Listing

`Listing` — конкретное объявление на конкретном источнике.

Обязательные поля:

- id;
- source_id;
- external_id;
- canonical_url;
- title;
- make;
- model;
- generation_id nullable;
- production_year;
- mileage_km;
- price;
- currency;
- fuel_type;
- transmission;
- body_type;
- engine_volume_cc;
- power_hp;
- location;
- seller_type;
- seller_id nullable;
- first_seen_at;
- last_seen_at;
- last_checked_at;
- status;
- raw_data reference;
- created_at;
- updated_at.

Unique:
`(source_id, external_id)`.

## 2. Listing Snapshot

Каждое существенное состояние объявления сохраняется отдельно.

Поля:
- listing_id;
- captured_at;
- price;
- mileage_km;
- title;
- description_hash;
- photos_hash;
- seller information;
- normalized attributes;
- raw payload reference.

Это позволяет строить:
- price history;
- mileage changes;
- time on market;
- listing updates;
- price reductions.

## 3. Canonical Vehicle

Отдельная нормализованная сущность.

Пример:

```text
Škoda
  └── Kodiaq
       └── Generation
            └── 2.0 TDI
                 └── DSG
```

Но MVP не должен пытаться идеально нормализовать все комплектации.

Минимум:
- make;
- model;
- generation nullable;
- engine/fuel/transmission normalized values.

## 4. Source

Источник объявлений.

Поля:
- id;
- name;
- domain;
- country;
- enabled;
- scraper_version;
- health_status;
- rate_limit configuration.

## 5. Search Query

Нормализованный пользовательский запрос.

Пример:

```json
{
  "make": "Skoda",
  "model": "Octavia",
  "year_min": 2018,
  "year_max": 2022,
  "price_max": 15000,
  "mileage_max": 180000,
  "transmission": ["automatic"],
  "sources": ["polovniautomobili"]
}
```

Search Query должна быть сериализуема и иметь стабильный hash.

## 6. Saved Search

Saved Search принадлежит пользователю и содержит Search Query.

Поля:
- user_id;
- name;
- query;
- enabled;
- notification settings;
- last_run_at.

## 7. Scrape Job

Job получения данных.

Типы:
- SEARCH;
- LISTING_REFRESH;
- SAVED_SEARCH_REFRESH;
- FULL_SOURCE_REFRESH;
- MARKET_REFRESH.

Статусы:
- PENDING;
- RUNNING;
- COMPLETED;
- PARTIAL;
- FAILED;
- CANCELLED.

## 8. Notification

Типы:
- NEW_MATCH;
- PRICE_DROP;
- LISTING_REMOVED;
- MARKET_CHANGE.

## 9. User

Минимум:
- id;
- email;
- password_hash;
- email_verified_at;
- status;
- created_at;
- last_login_at.

## 10. Subscription

Планы должны быть отделены от пользователя.

Например:
- FREE;
- SUPPORTER;
- PRO;
- ADMIN.

Подписка должна определять:
- количество saved searches;
- частоту refresh;
- приоритет scraping;
- количество priority credits;
- историю/аналитику;
- notification limits.
