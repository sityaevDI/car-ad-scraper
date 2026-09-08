# User scenarios

## 1. Anonymous browse

1. Пользователь открывает сайт.
2. Выбирает make/model.
3. Получает существующие listings.
4. Видит freshness.
5. Видит market price.
6. Может открыть listing.
7. Для сохранения поиска предлагает login.

## 2. Search with insufficient data

1. Пользователь задаёт фильтры.
2. Backend ищет существующие данные.
3. Если данных мало/устарели:
   - UI показывает причину;
   - предлагает Update.
4. Создаётся scrape job.
5. Пользователь видит progress.
6. По завершении результаты автоматически доступны.

## 3. Manual refresh

Пользователь нажимает `Update market`.

Backend:
- вычисляет необходимые sources;
- создаёт jobs;
- дедуплицирует уже выполняющиеся jobs;
- показывает ETA только если она вычислима.

## 4. Saved Search

1. Login.
2. Search.
3. Save search.
4. Настроить notifications.
5. Scheduler запускает refresh.
6. New matches → notification.

## 5. Follow listing

Пользователь нажимает Follow.

Система:
- сохраняет relation;
- отслеживает listing;
- при снижении цены создаёт notification.

## 6. Listing detail

Показывать:
- основные характеристики;
- текущую цену;
- market estimate;
- deviation;
- comparable listings;
- price history;
- first seen;
- last seen;
- time visible;
- status;
- source link.

## 7. Market analytics

1. Пользователь выбирает модель.
2. Выбирает период.
3. Получает charts.
4. Может фильтровать по:
   - year;
   - transmission;
   - fuel;
   - source;
   - region.

## 8. Scrape task

Пользователь может увидеть:
- status;
- source;
- query;
- started;
- finished;
- listings discovered;
- listings updated;
- errors.

В UI не нужно раскрывать технические детали proxy/anti-bot обычному пользователю.

## 9. Admin

Admin может:
- включить/отключить source;
- посмотреть source health;
- увидеть jobs;
- retry failed jobs;
- изменить rate limits;
- посмотреть parser errors;
- увидеть queue;
- вручную запустить crawl;
- проверить raw payload.

## 10. Monetization flow

Free:
- search;
- ограниченные saved searches;
- manual refresh;
- низкий priority.

Supporter:
- больше saved searches;
- чаще refresh;
- priority queue;
- notifications;
- priority credits.

Pro:
- максимальные quotas;
- высокий priority;
- расширенная analytics;
- больше history.

Не привязывать UI к конкретному payment provider.
