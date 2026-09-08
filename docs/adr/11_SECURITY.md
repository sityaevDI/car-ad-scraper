# Security

## Authentication

- password hashing через современный password hashing algorithm;
- email verification;
- secure session/token handling;
- refresh token rotation при необходимости;
- rate limit login;
- password reset tokens с коротким TTL.

## Authorization

RBAC:
- USER;
- ADMIN.

Каждый resource проверяет ownership.

## Secrets

Never commit:
- DB passwords;
- proxy credentials;
- JWT secret;
- SMTP credentials;
- payment keys.

## API protection

- request size limits;
- pagination limits;
- rate limits;
- validation;
- CORS allowlist;
- CSRF strategy в зависимости от auth architecture.

## Scraping security

Не принимать от пользователя произвольный URL и не отправлять его напрямую scraper'у.

Search должен использовать:
- разрешённые source adapters;
- whitelist domains;
- валидированные query parameters.

Это также предотвращает SSRF.

## Raw data

Не сохранять секреты/cookies в raw payload.
Cookies/session state должны быть отдельно и с ограниченным retention.

## Privacy

Пользовательские данные:
- минимизировать;
- удалить/анонимизировать по необходимости;
- не хранить лишние персональные данные.
