# Architectural decisions and open questions

## Already decided

- Existing scraper = Proof-of-Concept.
- Production architecture can be substantially rewritten.
- PostgreSQL = primary relational DB.
- Redis = queue/cache/locks/rate limiting.
- Modular monolith initially.
- Source adapters isolated.
- Listing and Snapshot are separate entities.
- Historical data is first-class.
- Market price is a core feature.
- Residential proxy support is required.
- Existing residential proxy provider: IPRoyal / geo.iproyal.com.
- Browser fetch fallback should be architecturally possible.
- Paid priority should be implemented through queue priority/credits.
- First production source should be Polovni Automobili.

## Open questions

### Frontend
Choose:
- Next.js;
- React + Vite;
- another framework.

Recommendation: choose based on SEO requirements and team familiarity.

### Authentication
Choose:
- secure cookie sessions;
- JWT access + refresh.

Recommendation for browser-first product: secure HttpOnly cookie-based auth can be simpler.

### Queue library
Options:
- ARQ;
- Celery;
- RQ;
- custom Redis queue.

Recommendation: use the smallest reliable solution compatible with async FastAPI workers.

### Payments
Provider is not decided.

Design billing behind an interface.

### Email provider
Not decided.

### Object storage
S3-compatible recommended.

### Market algorithm
MVP should use robust statistics, not ML.

### Generation normalization
Initially nullable/manual/semi-automatic.

### Source terms
Before production activation, review each source's ToS/robots/allowed automation.

### Data licensing
Need explicit product/legal decision on how much source data can be republished versus linking to original listing.

## Important product decision still needed

What exactly is the user buying?

Recommended answer:

Not "250 scraped ads".

Instead:

**Priority Refresh Credits** + subscription benefits.

The paid product is faster access to fresh market data and better monitoring, not ownership of scraped data.
