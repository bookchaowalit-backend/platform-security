# Security runtime pilot

Status: implemented and locally verified; deployment artifacts staged only.
Correlation: `SHARED-INFRA-2026-10-15`. No production activation or provider
acceptance is claimed. The legacy contract's scaffolded migration marker stays
unchanged because its guard requires activation evidence.

## Installation and lifecycle

Python >=3.12, PostgreSQL >=16. Nothing is published to PyPI. Local editing
uses `uv sync --frozen --all-extras`: `uv.lock` pins every dependency, with
`platform-backend-core` taken from its reviewed Git commit (`[tool.uv.sources]`).
`railway.toml` is a reference release asset; no Railway deployment has been
executed here.

### Container image

`docker build .` works from a clean checkout; no pre-staged `wheelhouse/` is
needed. The `Dockerfile` is two stages:

1. `build` (`python:3.12-slim` plus `git` and uv 0.13.1, the CI version, pinned
   by image digest): `uv sync --frozen --no-dev --no-editable` installs this
   service and every runtime dependency from `uv.lock` into `/opt/venv`, so
   `platform-backend-core` comes from the same reviewed commit
   (`21d5f44d26220080cbed43b9807979dc84a8533a`) CI installs, with the lock's hashes.
   No test or dev extras are installed.
2. `runtime` (`python:3.12-slim`, no git, no uv): copies only `/opt/venv`, runs
   as UID/GID `65532`, `PORT=8080`, and keeps
   `CMD ["python", "-m", "platform_security", "serve"]`. Run `migrate` as a
   separate one-off with the DDL-role `DATABASE_URL` (same image, command override).

`.dockerignore` keeps `.git`, `.venv`, tests, build output and `.env*` out of the
build context. CI job `image` in `check.yml` runs `docker build` on every push and
pull request, then checks that the image imports the service and runs as a
non-root user. It never pushes or deploys. `tests/test_build_hygiene.py` (part of
`scripts/check.sh`) fails if the Dockerfile copies a git-ignored path, stops being
multi-stage, resolves anything outside `uv.lock` (`pip install`, a second core
pin), runs the final stage as anything but `65532:65532` or changes the CMD, if
`[tool.uv.sources]` and `uv.lock` disagree on the core commit, if CI stops
building the image, or if any workflow `uses:` is not pinned to a 40-hex commit
SHA (tag in a trailing comment). Upgrading the core means changing the commit in
`[tool.uv.sources]` and re-locking (`uv lock`).

- `python -m platform_security migrate`: explicit migration with DDL-role `DATABASE_URL`.
- `python -m platform_security serve`: separate nonowner, NOSUPERUSER NOBYPASSRLS
  runtime `DATABASE_URL`; `PORT` defaults to 8080. Maximum API concurrency 100,
  pool 8, SQL timeout 10 seconds, HTTP boundary 30 seconds.
- Configure `JWT_ISSUER`, `JWT_AUDIENCE`, and exactly one `JWT_PUBLIC_KEY`
  (public PEM) or `JWT_JWKS_URL` (trusted HTTPS). Credentials never come from
  files or token-supplied URLs. Use the shared-core workspace RS256 profile.
- `GET /healthz`, `/readyz`, `/metrics` use shared redacted diagnostics.
  Readiness checks exact applied migration versions/checksums, table RLS, effective
  schema USAGE/history SELECT and every required table operation individually;
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

## Independent review correction — 2026-10-15

Round 1 reproduced 3 assertion-level failures before fixes in this service.
Readiness now checks effective `public` schema USAGE, history SELECT, and
separate SELECT/INSERT/UPDATE privileges for writable tables, plus DELETE for
feature flags. It does not interpret comma-separated privilege lists as an
all-required check (PostgreSQL treats those as any privilege). Each required
privilege is revoked independently in a disposable runtime role: ready changes
200 to 503, then returns to 200 after restoration. All audit forbidden
UPDATE/DELETE/TRUNCATE checks remain; each is also granted independently in
regression tests and correctly makes security not ready.

Full PostgreSQL-backed suite after correction: `17 passed`, no database
skips, one unchanged upstream Starlette/httpx warning. Original offline check
also passed. Migration 0001 SQL/checksum is unchanged.

## Pooled connection reuse

Store queries that return mappings use cursor-scoped `dict_row`; they do not
change the pooled connection row factory. Single-connection PostgreSQL
regressions cover successful traffic, conflicts, rollback and foreign-workspace
reads followed by repeated service and shared-core readiness checks.

## Build hygiene 2026-10-29 (branch `build-hygiene`)

Ported from `platform-developer` `8047108`, adapted to this repository's `uv.lock`:

1. The `Dockerfile` copied the git-ignored `wheelhouse/`, so `docker build .`
   failed on a fresh clone. It is now the two-stage `uv sync --frozen` build under
   "Container image", with a `.dockerignore`, and CI job `image` builds it
   without pushing.
2. `check.yml` already pinned every `uses:` (all three jobs call the shared
   workflows at `87dc5e1...` = v1.1.1); the new `image` job pins
   `actions/checkout` to `11d5960a...` (v4), and the test now guards all of them.

RED (tests written first, run on the old files, Python 3.12):
`python -m unittest tests.test_build_hygiene` failed 5 of 9 (`wheelhouse` copied;
no `.dockerignore`; no `docker build` in CI; no `uv.lock`/`uv sync --frozen`; one
`FROM`). The checker self-test, the workflow pin check, lock/`[tool.uv.sources]`
agreement and the non-root `USER`/CMD check passed.

GREEN: `bash scripts/check.sh` 57 unit tests OK; `ruff check .` and `mypy` clean;
`python -m pytest -q --cov` with a local PostgreSQL (`pgserver`) 76 passed,
coverage 87% (gate 87). The build stage was rehearsed without Docker
(`uv sync --frozen --no-dev --no-editable` into a fresh venv from a clean copy,
then `import platform_backend_core, platform_security.app`); the image itself is
verified only by the CI `image` job. Nothing was pushed to a registry or deployed.

## 422 only for domain input — 2026-10-29 (branch `invalid-input`)

Ported from `platform-developer` `8047108` and `platform-commerce` `main`. The app
mapped every `ValueError` to 422 `Invalid metadata`, so a server bug surfaced as a
client error. `store.InvalidInput(ValueError)` is now raised for validation
(`identifier`, `reference`, `put_reference` purpose and rotation, both list
limits, the audit `Idempotency-Key`), and only that maps to 422. Request-schema
errors keep the core's 422; any other exception, including an unexpected
`ValueError`, is the shared core's redacted 500.

`append` used one check for the actor and the key. The actor always comes from
the verified token, so a non-UUID actor now raises `TypeError` (a server bug, 500)
and only the key check is `InvalidInput`. `EnvironmentResolver.resolve` (never
behind a route) raises `InvalidInput` for a bad name, still a `ValueError` for
its callers. Readiness and startup are unchanged.

RED (`runtime_tests/test_error_mapping.py` written first): collection error,
`InvalidInput` missing. With a temporary `InvalidInput = ValueError` stand-in:
2 failed (`test_unexpected_value_error_is_redacted_500` `assert 422 == 500`, and the
non-UUID actor case), 10 passed.

GREEN: `PLATFORM_TEST_DSN=... pytest -q` 88 passed, 12 subtests, against
PostgreSQL 16 (`pgserver`); `--cov` total 87% (gate 87); `bash scripts/check.sh`
57 tests OK; `ruff check .` and `mypy` clean (locked `uv sync --frozen
--all-extras`). Nothing deployed.
