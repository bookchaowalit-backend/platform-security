# 06 — C4 Container

```mermaid
C4Container
  title Container view - security-api
  System_Ext(identity, "platform-identity", "JWKS /.well-known/jwks.json")
  System_Ext(callers, "Callers", "posture-monitor, mcp-hub, owner")
  System_Ext(sentry, "Sentry", "platform-security project")
  System_Boundary(rw, "Railway project platform-security") {
    Container(api, "security-api", "Python 3.12, FastAPI, uvicorn", "python -m platform_security serve, port 8080, limit_concurrency 100")
    Container(mig, "migrate one-off", "Same image, command override", "python -m platform_security migrate")
  }
  System_Boundary(nb, "Neon project platform-security") {
    ContainerDb(db, "PostgreSQL 16", "secret_references, security_audit, platform_schema_migrations", "Forced RLS on app.workspace_id")
  }
  Rel(callers, api, "HTTPS JSON, Bearer RS256")
  Rel(api, identity, "HTTPS JWKS, refresh at most every 60 s")
  Rel(api, db, "psycopg pool max 8, role security_runtime")
  Rel(mig, db, "DDL as owner role")
  Rel(api, sentry, "HTTPS envelope")
```

Sources: `Dockerfile`, `railway.toml`, `src/platform_security/__main__.py`, `src/platform_security/migrations.py`, platform-backend-core@21d5f44 `db.py` (pool `max_size=8`), `auth.py` (`_JWKS` 60 s), `docs/runtime.md`, ops record: book-platforms-status (2026-11-03)

## Open questions

- `migrate` ถูกรันจากเครื่อง owner หรือเป็น Railway one-off (runtime.md บอกแค่ "ran once with the owner role")
