# MVP roadmap

## Phase 0 — Foundation

- новая repo structure;
- Docker;
- FastAPI;
- PostgreSQL;
- Redis;
- migrations;
- auth;
- basic CI.

## Phase 1 — One source

Источник: Polovni Automobili.

Сделать:
- search;
- source adapter;
- listings;
- snapshots;
- listing detail;
- status tracking;
- basic market price.

## Phase 2 — Product value

- price score;
- market comparison;
- saved searches;
- follows;
- email notifications;
- scrape jobs;
- queue priority.

## Phase 3 — Analytics

- price history;
- market history;
- distributions;
- time visible;
- source comparison.

## Phase 4 — More sources

Добавлять:
- MojAuto;
- AutoScout24;
- Autoplius;
- Otomoto.

Каждый source после прохождения adapter contract и parser fixture tests.

## Phase 5 — Monetization

- Supporter;
- Pro;
- priority credits;
- payment provider;
- quota enforcement.

## Phase 6 — Scaling

Только после реальной нагрузки:
- отдельные workers per source;
- analytics DB;
- more aggressive caching;
- separate notification service;
- horizontal scaling.

## Критерий MVP

Пользователь должен уметь:

```text
найти автомобиль
→ понять его рыночную цену
→ увидеть историю объявления
→ сохранить поиск
→ получить уведомление о новом/дешевеющем автомобиле
```

И это должно работать хотя бы для одного источника качественно.
