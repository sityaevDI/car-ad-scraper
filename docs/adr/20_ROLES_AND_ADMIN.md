# Roles & Admin (MVP)

## Decision: role is not subscription tier

`users.role` (`app/models/user.py`) is an access-control field — what a user is allowed to *do*
in the system. `subscription_plans` / `user_subscriptions` (`app/models/subscription.py`) is a
billing entitlement — what a user gets for paying. These are two independent axes and must stay
that way:

- An admin does not need a paid plan.
- A paying Pro user does not get admin access.
- `subscription_plans.code` already has an `"ADMIN"` value (a comp/staff billing tier) — this is
  unrelated to `users.role == "admin"`. Don't conflate the two when building billing UI/logic.

`role` is a small enum (`user`, `admin` for now — see `UserRole` in `app/models/user.py`), chosen
over a `is_admin` boolean so a future `moderator`/`support` role doesn't require another schema
change.

## How a user becomes admin

No standing admin password, no seed env var read at startup. Instead:

1. The account registers normally through the existing flow (email + password, argon2 hash, email
   verification) — no new code path, no new place a plaintext password can leak.
2. Someone with access to run commands against the deployment (`docker exec` / `railway run` /
   local dev) runs:

   ```
   python -m app.auth.cli promote --email someone@example.com
   python -m app.auth.cli demote --email someone@example.com
   ```

   This only requires DB access, which is already a higher trust boundary than the app itself —
   there's no bootstrap/chicken-egg problem for the very first admin.

## What's implemented

- `role` column + migration (`migrations/versions/b2c3d4e5f6a7_add_user_role.py`).
- `require_admin` FastAPI dependency (`app/auth/dependencies.py`), on top of `get_current_user`.
- `app/auth/cli.py`: `promote`/`demote` by email.
- Scrape job management is admin-only end to end (`app/api/v1/scrape.py`): list (`GET
  /api/v1/scrape/jobs`, with `status`/`source_id` filters), create, cancel, and the new `retry`
  (re-enqueues a `FAILED`/`CANCELLED` job in place). Matches the "Controls" list in
  [13_ADMIN.md](13_ADMIN.md) as far as jobs go.
- Minimal frontend: `/admin/jobs` (`frontend/src/pages/AdminJobsPage.tsx`), gated by
  `frontend/src/admin/RequireAdmin.tsx` (redirects non-admins to `/`), linked from the header nav
  only when `user.role === 'admin'`.

## Explicitly deferred (backlog)

Scoped out of this pass on purpose — tracked here instead of implemented, so the roles/admin
foundation above isn't blocked on the rest of [13_ADMIN.md](13_ADMIN.md)'s dashboard:

- **Admin dashboard beyond jobs**: source health (enabled/success rate/requests-per-min/challenge
  rate), parser errors + sample raw payload, data stats (active/removed listings, snapshots,
  storage). None of the backing metrics are collected yet either.
- **Audit log**: 13_ADMIN.md says "any manual action is audit-logged" — not built. Every admin
  action (promote/demote, cancel/retry a job) should eventually write to an audit table
  (actor, action, target, timestamp).
- **Source controls**: enable/disable a source, change crawl limits, pause a source — no
  `sources` admin API yet.
- **Billing-plan management CLI**: a `set-plan`-style command to manually assign/comp a
  `subscription_plans` tier to a user, independent of `role`. Useful for support/manual grants
  ahead of real billing integration (still Phase 5 per
  [16_MVP_ROADMAP.md](16_MVP_ROADMAP.md)).
- **Finer-grained roles**: `moderator`/`support` etc., if a need shows up — the enum is already
  shaped to extend without another migration pattern change.
