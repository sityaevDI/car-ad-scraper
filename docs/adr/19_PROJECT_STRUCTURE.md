# Recommended repository structure

```text
/
├── app/
│   ├── api/
│   ├── auth/
│   ├── users/
│   ├── vehicles/
│   ├── listings/
│   ├── search/
│   ├── market/
│   ├── saved_searches/
│   ├── notifications/
│   ├── scraping/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── sources/
│   │       ├── base/
│   │       ├── polovniautomobili/
│   │       ├── mojauto/
│   │       ├── autoscout24/
│   │       ├── autoplius/
│   │       └── otomoto/
│   ├── billing/
│   ├── admin/
│   └── infrastructure/
│       ├── db/
│       ├── redis/
│       ├── http/
│       ├── proxy/
│       └── storage/
│
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│       └── sources/
│
├── frontend/
├── docs/
├── docker/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Dependency direction

```text
API
 ↓
Application services
 ↓
Domain
 ↓
Infrastructure adapters
```

Source adapters may depend on:
- source domain models;
- fetch abstractions;
- parser utilities.

They must not depend on:
- FastAPI routes;
- User models;
- billing;
- frontend.

## Domain boundaries

### Listings
Owns listing lifecycle.

### Scraping
Owns acquisition.

### Market
Owns statistical calculations.

### Users
Owns identity and preferences.

### Saved searches
Owns matching and scheduling rules.

### Billing
Owns entitlements and credits.

This separation is more important than physically separating them into services.
