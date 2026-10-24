# platform-security

`Security` platform boundary for the Book Platform portfolio.

## Scope

This repository owns the `security` capability: secret references, policy, audit, WAF controls, privacy.
The current source implementation is recorded as `infra/platform` in the
parent registry. This checkout includes an optional, locally implemented runtime pilot. Its legacy
contract remains scaffolded pending activation evidence; no production activation
is claimed.

## Boundary

- Owner: `bookchaowalit-backend`
- Repository: `platform-security`
- Target remote: `https://github.com/bookchaowalit-backend/platform-security.git` (not created by the bootstrap)
- Contract: `book-platform.contract.v1`
- Status: `scaffolded`
- Data owner: the platform boundary identified in `contract.json`

The platform communicates through versioned API or event contracts. Consumers
must not import another platform's database, migration, or private runtime
module. `solo-empire` remains the control plane and compatibility adapter until
parity and rollback evidence permit a cutover.

## Local verification

Run from this repository:

```bash
bash scripts/check.sh
```

The runtime package (`src/platform_security/`) is developed on the locked
environment: `uv sync --frozen --all-extras`, then `ruff check .`, `mypy` and
`python -m pytest` (set `PLATFORM_TEST_DSN` to a disposable PostgreSQL admin DSN
for the database tests). CI runs the same through the shared `ci-python`
workflow with a coverage gate.

The check validates repository shape and contract metadata only. It does not
claim deployment, provider connectivity, data migration, or production
readiness.

## Migration gate

Before activating a remote or changing a consumer, add sanitized fixtures for
success, duplicate delivery, timeout and provider failure; prove tenant/privacy
isolation; compare the old and new contract; and rehearse rollback on a
disposable state store. Record the evidence in the parent platform registry.

## Runtime pilot — implemented locally, staged only

Correlation: `SHARED-INFRA-2026-10-15`. The new Python 3.12+ / PostgreSQL 16+
runtime owns workspace data through forced RLS and verified UUID workspace JWTs.
See [API and operating guide](docs/runtime.md). Original contracts, schema pins
and offline checks are retained. This code has not been pushed or deployed.
