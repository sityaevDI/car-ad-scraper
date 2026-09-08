# API specification

Base:
`/api/v1`

## Auth

```text
POST /auth/register
POST /auth/login
POST /auth/logout
POST /auth/verify-email
POST /auth/refresh
POST /auth/forgot-password
POST /auth/reset-password
GET  /me
```

## Search

```text
POST /search
GET  /search/{search_id}
```

Search response:

```json
{
  "listings": [],
  "total": 123,
  "freshness": {
    "captured_at": "...",
    "age_seconds": 120
  },
  "market": {
    "estimated_price": 15400,
    "currency": "EUR",
    "sample_size": 47,
    "confidence": "medium"
  },
  "refresh": {
    "recommended": true,
    "active_job_id": null
  }
}
```

## Listings

```text
GET /listings
GET /listings/{id}
GET /listings/{id}/history
GET /listings/{id}/market-comparison
POST /listings/{id}/follow
DELETE /listings/{id}/follow
```

## Saved searches

```text
GET    /saved-searches
POST   /saved-searches
GET    /saved-searches/{id}
PATCH  /saved-searches/{id}
DELETE /saved-searches/{id}
POST   /saved-searches/{id}/run
```

## Scraping

```text
POST /scrape/jobs
GET  /scrape/jobs
GET  /scrape/jobs/{id}
POST /scrape/jobs/{id}/cancel
```

## Market

```text
GET /market/models
GET /market/models/{id}
GET /market/models/{id}/history
GET /market/models/{id}/distribution
```

## User

```text
GET /me
GET /me/subscription
GET /me/notifications
POST /me/notifications/{id}/read
```

## Admin

```text
GET /admin/sources
PATCH /admin/sources/{id}
GET /admin/jobs
GET /admin/source-health
GET /admin/parser-errors
POST /admin/jobs/{id}/retry
```

API должен:
- валидировать query;
- ограничивать page size;
- иметь consistent error format;
- использовать idempotency где необходимо;
- не раскрывать internal errors пользователю.
