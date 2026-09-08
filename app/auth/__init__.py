"""Session strategy: HttpOnly cookie + server-side session in Redis (not JWT).

Chosen for a browser-first SPA client — see agent_documents/18_DECISIONS_AND_OPEN_QUESTIONS.md
§Authentication. A cookie session avoids storing a bearer token somewhere JS can read it (XSS
exposure), and gives trivial server-side revocation via Redis. The trade-off is CSRF: mutating
cookie-authenticated endpoints require a double-submit `X-CSRF-Token` header (see
app/auth/dependencies.py:require_csrf).
"""
