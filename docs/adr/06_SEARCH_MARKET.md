# Search и Market Analytics

## 1. Search

Search должен возвращать:
- listings;
- total count;
- freshness;
- market summary;
- scrape status при наличии background job.

## 2. Фильтры

MVP:
- source;
- make;
- model;
- generation;
- production year min/max;
- price min/max;
- mileage min/max;
- fuel;
- transmission;
- body;
- engine volume;
- power;
- location.

## 3. Сортировки

- price ascending;
- price descending;
- mileage;
- production year;
- first seen;
- price score;
- freshness.

## 4. Группировка

Основной UI может группировать:
- make;
- model;
- generation;
- production year.

Но listing остаётся базовой единицей данных.

## 5. Market Price

Market Price — не просто среднее всех объявлений.

Базовая MVP-модель:
- median price comparable listings;
- trimmed median/quantiles;
- фильтрация выбросов;
- minimum sample size.

Comparable group определяется по:
- make;
- model;
- generation;
- production year;
- fuel;
- transmission;
- body;
- engine;
- mileage bucket;
- region/source при наличии достаточных данных.

## 6. Price Score

Например:

```text
price_ratio = listing_price / estimated_market_price
deviation_pct = (listing_price - market_price) / market_price * 100
```

UI:
- significantly below market;
- below market;
- market;
- above market;
- significantly above market.

Пороговые значения должны быть конфигурируемыми.

## 7. Confidence

Оценка market price должна иметь confidence, зависящий от:
- sample size;
- age of data;
- similarity;
- dispersion;
- source coverage.

Нельзя показывать точную "рыночную цену", если выборка состоит из 2–3 слабосопоставимых машин.

Пример:

```text
Market price: €15,400
Expected range: €14,600–€16,300
Confidence: Medium
Comparable listings: 47
```

## 8. Outliers

Не удалять исходные объявления.

Для расчёта рынка можно использовать:
- IQR;
- MAD;
- trimmed quantiles.

Порог должен быть конфигурируемым и сохраняться в версии аналитического алгоритма.

## 9. Historical analytics

Графики:
- median price over time;
- active listings over time;
- median mileage;
- price by production year;
- price vs mileage;
- time on market;
- price reduction distribution.

## 10. Time on Market

Если listing:
`first_seen_at = 2026-01-01`
и исчез:
`last_seen_at = 2026-02-15`

можно оценить duration ≈ 45 days.

Но исчезновение не равно продаже.

Поэтому показывать:
`time visible on source`, а не утверждать факт продажи без доказательств.

## 11. Historical sale inference

В будущем можно строить вероятность продажи:
- listing disappeared;
- был активен N дней;
- цена перед исчезновением;
- источник.

Но UI должен явно обозначать, что это inference.

## 12. Market page

Для модели:

```text
Škoda Octavia 2019–2021

Active listings: 124
Median price: €14,900
Median mileage: 168k km
Price trend 30d: -2.1%
Best offers: 8
```

Все метрики должны иметь timestamp.
