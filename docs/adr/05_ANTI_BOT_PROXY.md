# Anti-bot, proxy и Cloudflare resilience

## 1. Цель

Архитектура должна позволять менять способ получения страницы без переписывания source parser.

Получение данных должно быть абстрагировано:

```text
Source Adapter
      |
      v
Fetch Strategy
  ├── direct HTTP
  ├── HTTP residential proxy
  ├── browser session
  └── future provider
```

## 2. Residential proxy

У проекта уже есть residential proxy от `geo.iproyal.com`.

Credentials должны находиться только в secrets/environment.

Например:

```text
PROXY_PROVIDER=iproyal
PROXY_URL=...
PROXY_USERNAME=...
PROXY_PASSWORD=...
```

Не хранить proxy credentials в коде, БД или git.

## 3. Proxy pool abstraction

Нужен интерфейс:

```python
class ProxyProvider(Protocol):
    async def acquire(self, source: str) -> ProxyEndpoint:
        ...

    async def report_success(self, proxy: ProxyEndpoint, metrics: FetchMetrics) -> None:
        ...

    async def report_failure(
        self,
        proxy: ProxyEndpoint,
        error: FetchError,
    ) -> None:
        ...
```

Это позволит заменить IPRoyal без изменения scraper.

## 4. Proxy assignment

Proxy выбирается с учётом:
- source;
- текущей нагрузки;
- failure rate;
- cooldown;
- geo requirement;
- sticky session requirement.

Не вращать proxy на каждый запрос без причины. Для некоторых источников стабильная session identity может быть лучше.

## 5. Anti-bot state machine

Fetch layer должен определять:

```text
SUCCESS
RATE_LIMITED
FORBIDDEN
CHALLENGE
CAPTCHA
TIMEOUT
SERVER_ERROR
PARSER_ERROR
```

После challenge/captcha нельзя бесконечно повторять запрос.

Вместо этого:
1. пометить endpoint/session unhealthy;
2. применить cooldown;
3. при наличии альтернативной стратегии переключиться;
4. если не помогает — завершить job как PARTIAL/FAILED.

## 6. Browser fallback

Архитектура должна позволять подключить Playwright/browser worker как fallback для страниц, которые нельзя получить обычным HTTP client.

Это отдельная fetch strategy, например:

```text
HttpFetcher
PlaywrightFetcher
ProxyHttpFetcher
ProxyBrowserFetcher
```

Не смешивать browser automation с parser.

## 7. Что НЕ делать

Не строить систему вокруг постоянной попытки обходить CAPTCHA/anti-bot.

Не пытаться:
- взламывать CAPTCHA;
- обходить authentication;
- эксплуатировать уязвимости;
- скрывать незаконную автоматизацию.

Система должна использовать обычные HTTP/browser механизмы, residential proxy и controlled retry в рамках допустимого использования источника.

## 8. Adaptive throttling

Для каждого source поддерживать динамический crawl budget.

Например:

```text
normal:
  concurrency = 2
  delay = 2s + jitter

429 rate increases:
  concurrency = 1
  delay = 5s + jitter

challenge detected:
  cooldown = 15m
```

Значения конфигурируемые, а не hardcoded.

## 9. Request fingerprint

Fetch layer должен централизованно управлять:
- User-Agent;
- Accept headers;
- language;
- cookies/session;
- redirects;
- timeout;
- TLS/client implementation, если библиотека позволяет.

Не размазывать это по parser'ам.

## 10. Legal/operational boundary

Перед production запуском для каждого источника отдельно проверить:
- robots.txt;
- Terms of Service;
- ограничения API/автоматизации;
- частоту запросов;
- правила использования контента.

Система должна позволять отключить источник административно.
