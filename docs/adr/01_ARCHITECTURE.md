# Архитектура

## 1. Архитектурный подход

На старте использовать **modular monolith + background workers**, а не микросервисы.

Компоненты:

- Web frontend;
- FastAPI application;
- PostgreSQL;
- Redis;
- scraping workers;
- scheduler;
- notification worker;
- object storage для raw HTML/JSON при необходимости.

Компоненты должны иметь чёткие границы модулей, чтобы позднее их можно было вынести в отдельные сервисы.

## 2. Логическая схема

```text
Browser
   |
   v
Frontend
   |
   v
FastAPI
   |
   +------------------> PostgreSQL
   |
   +------------------> Redis
   |
   +--> Search Service
   +--> Market Analytics
   +--> User/Subscription
   +--> Saved Searches
   +--> Listings
   |
   v
Job Queue
   |
   +--> Scraper Worker: Polovni
   +--> Scraper Worker: MojAuto
   +--> Scraper Worker: AutoScout24
   +--> Scraper Worker: Autoplius
   +--> Scraper Worker: Otomoto
               |
               v
        HTTP / Browser / Proxy
               |
               v
            Sources
```

## 3. Backend modules

Предлагаемая структура:

```text
app/
  api/
  auth/
  users/
  vehicles/
  listings/
  search/
  market/
  saved_searches/
  notifications/
  scraping/
  sources/
    base/
    polovniautomobili/
    mojauto/
    autoscout24/
    autoplius/
    otomoto/
  billing/
  admin/
  infrastructure/
    db/
    redis/
    storage/
    http/
  common/
```

Модули не должны импортировать внутренности друг друга напрямую без необходимости.

## 4. PostgreSQL

PostgreSQL является основной БД.

Причина:
- пользователи;
- подписки;
- saved searches;
- связи listings ↔ canonical vehicles;
- источники;
- scrape jobs;
- snapshots;
- уведомления;
- платежи;
- квоты;
- аналитические агрегаты.

MongoDB из PoC не использовать как обязательную primary DB. При необходимости её можно оставить для raw source payloads, но это не требование.

## 5. Redis

Использовать Redis для:
- очереди задач;
- locks;
- rate limiting;
- deduplication;
- transient state;
- cache;
- приоритетов задач.

Не хранить в Redis единственную копию бизнес-критичных данных.

## 6. Масштабирование

На старте:
- 1 API container;
- 1–N worker containers;
- 1 scheduler;
- PostgreSQL;
- Redis.

При росте:
- масштабировать workers;
- разделить workers по source;
- вынести тяжёлую аналитику;
- при необходимости добавить отдельное OLAP-хранилище.

## 7. API

REST API через FastAPI.

OpenAPI должен генерироваться автоматически.

Версионирование:
`/api/v1/...`

## 8. Frontend

Предпочтительно React/Next.js либо эквивалентный современный SPA/SSR frontend.

Не переносить старый PoC frontend в production без рефакторинга.

## 9. Конфигурация

Все secrets и environment-specific настройки только через environment/secrets:

- DATABASE_URL
- REDIS_URL
- SECRET_KEY
- SMTP credentials
- proxy credentials
- storage credentials
- payment credentials.

Никаких credentials в git.
