# Scraping architecture

## 1. Adapter interface

Каждый источник должен реализовать единый интерфейс:

```python
class CarSource(Protocol):
    source_code: str

    async def search(self, query: SearchQuery) -> AsyncIterator[SourceListingRef]:
        ...

    async def fetch_listing(self, ref: SourceListingRef) -> SourceListing:
        ...

    def parse_search_page(self, response: HttpResponse) -> list[SourceListingRef]:
        ...

    def parse_listing(self, response: HttpResponse) -> SourceListing:
        ...

    def build_search_url(self, query: SearchQuery) -> str:
        ...
```

Конкретный source adapter не должен знать о PostgreSQL, пользователях или billing.

## 2. Pipeline

```text
SearchQuery
  ↓
Source adapter
  ↓
HTTP/browser fetch
  ↓
Raw response
  ↓
Parser
  ↓
SourceListing
  ↓
Canonical mapper
  ↓
Listing upsert
  ↓
Snapshot if changed
  ↓
Market recalculation
  ↓
Alerts
```

## 3. Search и listing refresh

Разделить:
- поиск ссылок на объявления;
- получение полной карточки;
- периодическую проверку существующих объявлений.

Search page не должна считаться достаточным источником полной информации.

## 4. Deduplication

Primary dedup:
`source_id + external_id`.

Cross-source deduplication — отдельный будущий механизм.

Не считать два объявления одинаковой машиной только по title/year/price.

## 5. Crawl strategy

Использовать разные стратегии:

### User-requested
Высокий приоритет. Точный query.

### Saved-search
Периодический refresh.

### Background discovery
Низкий приоритет. Используется для расширения исторической базы.

### Listing refresh
Проверяет активные listings.

## 6. Pagination

Source adapter должен уметь:
- определять total pages, если источник это предоставляет;
- ограничивать максимальное количество страниц;
- останавливаться при отсутствии новых listing refs;
- корректно переживать изменение сортировки.

## 7. Rate limiting

Не использовать один глобальный sleep.

Rate limit должен быть per-source и при необходимости per-proxy identity.

Параметры:
- requests/min;
- concurrency;
- minimum delay;
- jitter;
- cooldown;
- retry policy.

## 8. Ошибки

Классифицировать:
- network timeout;
- DNS;
- connection reset;
- 403;
- 429;
- 5xx;
- CAPTCHA;
- Cloudflare challenge;
- parser error;
- unexpected schema;
- source unavailable.

Ошибки должны быть наблюдаемыми и не приводить к бесконечным retry.

## 9. Parser versioning

Каждый source adapter имеет parser version.

При изменении parser:
- raw payload можно переобработать;
- новые версии не должны уничтожать исходные данные.

## 10. Source health

Хранить метрики:
- success rate;
- average latency;
- 403 rate;
- 429 rate;
- challenge rate;
- parser error rate;
- listings/hour.

При ухудшении health автоматически снижать crawl rate.

## 11. Важный принцип

Не проектировать scraper как набор ad-hoc функций вида `scrape_all_pages()`.

Существующий PoC можно использовать как источник:
- CSS/XPath selectors;
- URL patterns;
- parser logic;
- source-specific quirks.

Но production scraper должен быть переработан вокруг adapter interface и job pipeline.
