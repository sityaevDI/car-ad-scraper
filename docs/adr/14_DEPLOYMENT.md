# Deployment

## Local development

Docker Compose:

```text
frontend
api
worker
scheduler
postgres
redis
```

Опционально:
- minio/S3-compatible object storage.

## Production

Минимально:

```text
Load Balancer
    |
Frontend / API
    |
PostgreSQL
Redis
Workers
Scheduler
Object Storage
```

## CI/CD

Pipeline:
1. lint;
2. type check;
3. unit tests;
4. integration tests;
5. build Docker images;
6. security scan;
7. deploy;
8. migrations.

## Database migrations

Alembic.

Migrations обязательны.
Не изменять production schema вручную.

## Backups

PostgreSQL:
- automated backups;
- tested restore procedure.

Raw object storage:
- lifecycle policy;
- retention.

## Environments

- local;
- staging;
- production.

Production credentials никогда не используются локально.
