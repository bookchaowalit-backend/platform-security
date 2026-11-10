# 10 — Sequence diagrams

## S1 — Append audit event (posture-monitor → security-api)

```mermaid
sequenceDiagram
  autonumber
  participant PM as posture-monitor
  participant ID as platform-identity
  participant B as Core _Boundary
  participant R as Route POST /v1/audit
  participant V as TokenVerifier
  participant S as SecurityStore
  participant DB as Neon PostgreSQL
  PM->>ID: client_credentials, audience security-api
  ID-->>PM: RS256 JWT (sub, ws, scope audit:write)
  PM->>B: POST /v1/audit, Idempotency-Key, action, target
  B->>B: body <= 8192 bytes, timeout 30 s, x-request-id
  B->>R: forward
  R->>V: verify Authorization header
  V->>ID: GET JWKS (cached, refresh at most every 60 s)
  V-->>R: Principal(actor, workspace, scopes)
  alt scope missing
    R-->>PM: 403 forbidden
  end
  R->>S: append(workspace, actor, key, action, target)
  S->>DB: BEGIN, set_config app.workspace_id
  S->>DB: INSERT ... ON CONFLICT (workspace_id, event_key) DO NOTHING
  S->>DB: SELECT row WHERE event_key = key
  alt fingerprint differs
    S-->>R: Conflict
    R-->>PM: 409 Idempotency conflict
  else same or new
    S-->>R: id, actor, action, target, created_at
    R-->>PM: 200 JSON
  end
```

## S2 — Upsert secret reference

```mermaid
sequenceDiagram
  autonumber
  participant C as Caller with references:write
  participant R as Route PUT /v1/secret-references/name
  participant S as SecurityStore
  participant DB as Neon PostgreSQL
  C->>R: PUT provider, reference, purpose, rotated_at
  R->>R: Pydantic Reference extra=forbid, max lengths
  alt unknown field such as value
    R-->>C: 422 invalid request
  end
  R->>S: put_reference(workspace from token, name, ...)
  S->>S: identifier(name), reference(provider, ref), purpose regex, tz check
  alt validation fails
    S-->>R: InvalidInput
    R-->>C: 422 Invalid metadata
  end
  S->>DB: INSERT ... ON CONFLICT (workspace_id, name) DO UPDATE ... RETURNING
  DB-->>S: row (RLS WITH CHECK workspace)
  S-->>C: 200 name, provider, reference, purpose, rotated_at
```

## S3 — Readiness probe

```mermaid
sequenceDiagram
  autonumber
  participant U as Railway healthcheck / uptime worker
  participant A as Core /readyz
  participant D as Database.ready
  participant S as SecurityStore.ready
  participant DB as Neon PostgreSQL
  U->>A: GET /readyz
  A->>D: SELECT 1
  D->>DB: query
  A->>S: security_schema_permissions check
  S->>DB: has_schema_privilege / has_table_privilege per operation
  S->>DB: platform_schema_migrations versions and checksums
  S->>DB: relrowsecurity AND relforcerowsecurity
  S->>DB: trigger immutable_audit enabled
  S->>DB: no UPDATE / DELETE / TRUNCATE on security_audit
  alt all checks true
    A-->>U: 200 ready
  else any false or exception
    A-->>U: 503 unavailable
  end
```

## S4 — Release lifecycle (migrate then serve)

```mermaid
sequenceDiagram
  autonumber
  participant O as Operator
  participant M as python -m platform_security migrate
  participant DB as Neon PostgreSQL
  participant SV as python -m platform_security serve
  O->>M: DATABASE_URL = owner role
  M->>DB: advisory locks, CREATE TABLE IF NOT EXISTS platform_schema_migrations
  M->>DB: apply 0001 if absent, record checksum
  O->>DB: GRANT runtime privileges to security_runtime
  O->>SV: DATABASE_URL = runtime role, JWT_ISSUER, JWT_AUDIENCE, JWT_JWKS_URL
  SV->>DB: pool connect, reject SUPERUSER or BYPASSRLS
  SV->>SV: uvicorn 0.0.0.0:PORT, limit_concurrency 100
  Note over SV: any config error exits with a generic message
```

Sources: `src/platform_security/app.py`, `src/platform_security/store.py`, `src/platform_security/__main__.py`, `src/platform_security/migrations.py`, platform-backend-core@21d5f44 `http.py`, `auth.py`, `db.py`, `migrations.py`, `docs/runtime.md`, `.railway/railway.ts`, ops record: book-platforms-status (2026-11-03)
