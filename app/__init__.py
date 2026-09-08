"""Postgres-backed modular monolith (see the legacy Mongo PoC at repo root, left untouched).

Dependency direction: API (app/api/) -> Application (per-domain packages: listings, search,
market, ...) -> Domain (app/models/) -> Infrastructure (app/db/, app/infrastructure/, app/sources/).
Higher layers may import lower ones, never the reverse.
"""
