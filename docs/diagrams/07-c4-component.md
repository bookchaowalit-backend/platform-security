# 07 — C4 Component

```mermaid
C4Component
  title Components inside security-api
  Container_Boundary(api, "security-api process") {
    Component(init, "Package init", "_sentry.init_sentry", "Starts Sentry only when SENTRY_DSN is set")
    Component(main, "CLI entry", "__main__.py", "serve or migrate, fail-closed exit message")
    Component(boundary, "_Boundary middleware", "platform-backend-core http.py", "Body limit 8192, timeout 30 s, x-request-id, metrics, redacted 500")
    Component(capture, "CaptureErrors", "_sentry.py", "Innermost ASGI layer, reports unhandled exceptions")
    Component(scope, "require_scope", "platform-backend-core http.py", "Verify token, check scope, return Principal")
    Component(verifier, "TokenVerifier", "platform-backend-core auth.py", "RS256, iss, aud, sub, ws, jti, lifetime <= 3600")
    Component(routes, "Routes", "app.py", "secret-references and audit handlers, Pydantic models extra=forbid")
    Component(store, "SecurityStore", "store.py", "Validation, SQL, idempotency fingerprint, ready()")
    Component(resolver, "EnvironmentResolver", "store.py", "In-process mapping only, no route")
    Component(dbc, "Database", "platform-backend-core db.py", "Pool, NOSUPERUSER NOBYPASSRLS check, set app.workspace_id")
    Component(health, "Diagnostics", "platform-backend-core http.py", "/healthz /readyz /metrics")
  }
  ContainerDb(pg, "PostgreSQL", "Neon")
  System_Ext(jwks, "Identity JWKS")
  Rel(main, routes, "create_app")
  Rel(boundary, capture, "calls inner app")
  Rel(capture, routes, "calls")
  Rel(routes, scope, "Depends")
  Rel(scope, verifier, "verify")
  Rel(verifier, jwks, "fetch keys")
  Rel(routes, store, "calls")
  Rel(store, dbc, "transaction(workspace)")
  Rel(health, store, "readiness_checks security_schema_permissions")
  Rel(dbc, pg, "SQL")
```

Sources: `src/platform_security/__init__.py`, `src/platform_security/__main__.py`, `src/platform_security/app.py`, `src/platform_security/store.py`, `src/platform_security/_sentry.py`, platform-backend-core@21d5f44 `src/platform_backend_core/http.py`, `auth.py`, `db.py`

Note: `EnvironmentResolver` ไม่ถูกเรียกจาก `app.py` ใด ๆ (ใช้ใน test เท่านั้น)
