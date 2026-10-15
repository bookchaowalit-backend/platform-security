# Security runtime pilot

Status: implemented and locally verified; deployment artifacts staged only.
Correlation: `SHARED-INFRA-2026-10-15`. No production activation or provider
acceptance is claimed. The legacy contract's scaffolded migration marker stays
unchanged because its guard requires activation evidence.

## Installation and lifecycle

Python >=3.12, PostgreSQL >=16. Build/review wheels for this repository and
`platform-backend-core==0.1.0`; the parent release bundles all transitive wheels
in `wheelhouse/` for the Dockerfile. Nothing is published to PyPI. Local editing
uses `pip install -e . --no-deps` after installing the reviewed core and runtime
dependencies. `Dockerfile` and `railway.toml` are reference release assets;
no container build or Railway deployment has been executed here.

- `python -m platform_security migrate`: explicit migration with DDL-role `DATABASE_URL`.
- `python -m platform_security serve`: separate nonowner, NOSUPERUSER NOBYPASSRLS
  runtime `DATABASE_URL`; `PORT` defaults to 8080. Maximum API concurrency 100,
  pool 8, SQL timeout 10 seconds, HTTP boundary 30 seconds.
- Configure `JWT_ISSUER`, `JWT_AUDIENCE`, and exactly one `JWT_PUBLIC_KEY`
  (public PEM) or `JWT_JWKS_URL` (trusted HTTPS). Credentials never come from
  files or token-supplied URLs. Use the shared-core workspace RS256 profile.
- `GET /healthz`, `/readyz`, `/metrics` use shared redacted diagnostics.
  Readiness checks exact applied migration versions/checksums and table RLS;
  missing schema returns generic 503. Setup and serving are separate commands.
- Python interface `platform_security.app:create_app(database, verifier)` and
  `platform_security.migrations.MIGRATIONS` support explicit dependency injection.

The DDL role owns the schema. Grant runtime schema USAGE, SELECT on
`platform_schema_migrations`, and only needed table permissions below. Do not
grant ownership, CREATE, TRUNCATE, schema-history writes or migration execution.
Use a dedicated database per service; no other service's tables are imported.
Runtime role and backup/restore provisioning remain operator release work.
All workspace authority comes from JWT `ws`, actor from JWT `sub`; body/header
workspace fields never select tenant context. API validation errors are generic.

## Verification and release gate

Run original `bash scripts/check.sh`, then `PLATFORM_TEST_DSN=<explicit disposable
local admin DSN> python -m pytest -q`. Without that DSN the PostgreSQL cases
visibly skip and provide no durability evidence. Runtime tests use unique
throwaway databases and NOSUPERUSER NOBYPASSRLS roles, real JWT signatures,
concurrent independent connections, and HTTP requests. Tests never call live
providers. Local verification uses Python 3.14/PostgreSQL 18; the 3.12/16 floor
is specified but was not executed. One upstream Starlette/httpx deprecation
warning remains. Production load, backup restore, credential rotation, ingress
policy and full provider acceptance belong to integration/release gates.

Rollback stops this optional runtime and restores consumers to the previous
adapter. Do not downgrade applied SQL or overwrite a live database. Restore
only to a new isolated database and verify synthetic workspace reads before
cutover. Coordinate retention and backup encryption with the owning operator;
no scheduled deletion or backup credential access is implemented here.

## Reference metadata and audit API

Production runtime grants must be explicit:

```sql
GRANT SELECT, INSERT, UPDATE ON secret_references TO runtime_role;
GRANT SELECT, INSERT ON security_audit TO runtime_role;
REVOKE UPDATE, DELETE, TRUNCATE ON security_audit FROM runtime_role;
GRANT SELECT ON platform_schema_migrations TO runtime_role;
```

Substitute the provisioned runtime role using an identifier-safe admin tool.
Readiness rejects a role with audit UPDATE/DELETE/TRUNCATE, missing forced RLS,
missing checksum history or a disabled immutable trigger. A trigger also rejects
UPDATE/DELETE/TRUNCATE if broad test/admin grants accidentally include them.
Runtime cannot alter/disable triggers because it is not an owner. The owner
still controls DDL; this is append-only application audit, not tamperproof
storage against a database administrator.

- `PUT /v1/secret-references/{name}` (`references:write`): `provider`,
  `reference`, `purpose`, optional timezone-aware `rotated_at`.
- `GET /v1/secret-references` (`references:read`), limit 1..100, after name.
- `POST /v1/audit` (`audit:write`), required `Idempotency-Key`, body `action`
  and `target` identifier labels only. Workspace and actor are server-bound.
  Exact retry returns the original event; changed action/target/actor is 409.
- `GET /v1/audit` (`audit:read`), limit 1..100, after UUID, ordered by UUID.
  Pagination is bounded, not a snapshot of concurrently appended rows.

Names/actions/targets match `[a-z][a-z0-9_.-]{0,63}`. Providers are `env`,
`vault`, `aws`; only env uppercase names or bounded provider path identifiers
are accepted, never URLs, file paths, dot traversal, or free-form credentials.
Purpose is a short label; never put credentials in metadata. Unknown fields
including `value`, `actor` and `workspace` are rejected. There is no secret-value
HTTP endpoint or provider/file lookup. `EnvironmentResolver(allowed_mapping)`
is optional application-only resolution from an explicitly injected mapping;
unknown names raise KeyError and nothing is discovered from the host.

## Local verification record — 2026-10-15

- Initial runtime suite was RED during collection because the new service
  package/store did not exist. This is missing-interface evidence, not an
  assertion-level behavioral failure.
- An assertion-level regression test removed applied migration history and
  observed the developer readiness endpoint incorrectly return 200; after
  adding exact checksum/version checks it returns 503. The same history
  checks are present in all three services.
- Final full suite: `7 passed`, no database skips, one upstream warning.
- Original `bash scripts/check.sh`: passed, original minimal security contract guard unchanged.
- Isolated wheel build and import: passed. No wheel publication, container
  build, live provider operation, push or deployment was performed.
