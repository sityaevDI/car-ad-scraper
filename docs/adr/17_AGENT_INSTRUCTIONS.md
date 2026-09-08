# Instructions for AI coding agent

## Context

Existing repository is a Proof-of-Concept scraper. Do not preserve its architecture merely for compatibility.

Use existing code as reference for:
- source URL formats;
- HTML selectors;
- parsing logic;
- existing Polovni Automobili behaviour;
- known edge cases.

The uploaded HTML fixtures are also reference material. For example, the listing page exposes canonical listing metadata such as external ID, price, make/model, production year, mileage, body, fuel, engine volume, horsepower, gearbox, location and seller information in the page data layer. fileciteturn2file1

The search page demonstrates source-side search/saved-search concepts and existing filtering/sorting behaviour. fileciteturn2file0

## Required implementation philosophy

1. Do not build a big-bang rewrite without tests.
2. First inspect the existing repository.
3. Create an architecture migration plan.
4. Preserve useful parser behaviour by moving it behind adapters.
5. Add fixtures before rewriting parsers.
6. Implement database migrations early.
7. Keep source-specific code isolated.
8. Keep business logic independent of scraping implementation.
9. Do not introduce microservices prematurely.
10. Every new major component needs tests.

## Recommended implementation order

### Step 1
Audit current repository:
- files;
- dependencies;
- API;
- DB models;
- scraper;
- frontend;
- Docker;
- tests.

Produce `docs/POC_AUDIT.md`.

### Step 2
Create target architecture and migration plan.

### Step 3
Introduce PostgreSQL domain models and Alembic.

### Step 4
Introduce source adapter interface.

### Step 5
Move Polovni parser behind adapter.

### Step 6
Implement listing + snapshot persistence.

### Step 7
Implement search API.

### Step 8
Implement async scrape jobs and Redis queue.

### Step 9
Implement proxy/fetch abstraction.

### Step 10
Implement market analytics.

### Step 11
Implement authentication/saved searches/notifications.

### Step 12
Implement frontend.

### Step 13
Add admin and observability.

## Definition of Done

A feature is not done if:
- it only works manually;
- it has no tests;
- it stores critical state only in Redis;
- it couples source parser to API;
- it hardcodes credentials;
- it silently swallows scraper failures.

## Important constraints

### Proxy
There is an existing residential proxy provider: `geo.iproyal.com`.

Treat it as a configurable provider. Do not hardcode credentials.

### Anti-bot
Build resilience, not a CAPTCHA-breaking system.

### Data
Never overwrite historical snapshots when the current listing changes.

### Market price
Never display a market estimate without sample size/confidence metadata.

### Removed listings
Never delete merely because they disappeared from source.

### User jobs
Do not create duplicate equivalent scrape jobs.

### Security
Never expose raw proxy credentials or source session cookies through API/frontend.

## Expected coding style

Python:
- modern typing;
- Pydantic;
- async where I/O-bound;
- SQLAlchemy 2.x;
- Alembic;
- pytest;
- Ruff/formatter/linter;
- structured logging.

Prefer explicit domain services over giant route handlers.

## Before coding

If requirements conflict or a requested feature creates architectural debt, stop and explain the conflict rather than silently implementing a bad design.

If information is missing, mark it as an explicit TODO/decision rather than inventing business rules.
