# Testing strategy

## Unit tests

Обязательно покрыть:
- source parsers;
- canonical mapping;
- query normalization;
- market price calculation;
- outlier filtering;
- price score;
- priority calculation;
- quota calculation.

## Parser fixtures

Для каждого source хранить реальные обезличенные HTML fixtures.

Пример:

```text
tests/
  fixtures/
    polovniautomobili/
      search_page_01.html
      listing_01.html
```

Parser tests не должны ходить в интернет.

## Integration tests

- PostgreSQL;
- Redis;
- API;
- job lifecycle.

## End-to-end

Минимум:
1. register;
2. search;
3. create scrape job;
4. worker processes fixture;
5. listing appears;
6. save search;
7. notification generated.

## Scraper live tests

Отдельно от обычного CI.
Не запускать live scraping на каждый commit.

## Regression

Каждое исправление parser bug должно добавлять fixture/regression test.
