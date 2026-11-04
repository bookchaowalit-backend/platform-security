# Core 22 SDLC diagram pack — platform-security

ชุด diagram 22 รายการตาม SDLC Diagram Catalog v2 (knowledge-base `knowledge/tech/core-cs/sdlc-diagram-catalog.md`) วาดจาก code / config ของ repo นี้ที่ `main` 0187719 (2026-11-03) ทุก diagram มี `Sources:` และ "Open questions" แยกไว้ hosting facts ที่ไม่อยู่ใน repo อ้าง `ops record: book-platforms-status (2026-11-03)`

สรุปสถาปัตยกรรมระดับระบบ (style, quality attributes, integrations, fitness functions): [`DOCPACK/02-architecture.md`](../../DOCPACK/02-architecture.md)

| # | Item | Status | File | Sources read |
|---|---|---|---|---|
| 01 | Business process (As-Is / To-Be) | done | [01-business-process.md](01-business-process.md) | contract.json, PRODUCT.md, README.md, app.py, store.py, BOO-163 gate doc |
| 02 | Use cases | done | [02-use-cases.md](02-use-cases.md) | app.py, core http.py / auth.py, ops record, uptime targets.ts |
| 03 | User flows (API call flows) | done | [03-user-flows.md](03-user-flows.md) | app.py, store.py, __main__.py, core, test_http.py |
| 04 | Traceability (RTM) | done | [04-traceability.md](04-traceability.md) | PRODUCT.md, runtime.md, BOO-163, tests/, runtime_tests/, check.yml |
| 05 | C4 Context | done | [05-c4-context.md](05-c4-context.md) | __main__.py, _sentry.py, railway.toml, runtime.md, ops record |
| 06 | C4 Container | done | [06-c4-container.md](06-c4-container.md) | Dockerfile, railway.toml, migrations.py, core db.py / auth.py |
| 07 | C4 Component | done | [07-c4-component.md](07-c4-component.md) | src/platform_security/*.py, core http.py / auth.py / db.py |
| 08 | ADRs (6) | done | [08-adr/](08-adr/) | pyproject.toml, uv.lock, migrations.py, app.py, _sentry.py, railway.toml, runtime.md |
| 09 | ERD | done | [09-erd.md](09-erd.md) | migrations.py, store.py, core migrations.py / db.py, runtime.md |
| 10 | Sequences | done | [10-sequences.md](10-sequences.md) | app.py, store.py, __main__.py, core |
| 11 | State machines | done | [11-state-machines.md](11-state-machines.md) | store.py, migrations.py, tenant.schema.json |
| 12 | API and integrations | done (extends [runtime.md](../runtime.md)) | [12-api-integration.md](12-api-integration.md) | app.py, store.py, core http.py, runtime.md |
| 13 | Threat model (DFD + STRIDE) | done | [13-threat-model.md](13-threat-model.md) | src, core, check.yml, ci-workflows security.yml, BOO-163 |
| 14 | Backup / DR | done | [14-backup-dr.md](14-backup-dr.md) | migrations.py, runtime.md, central ADR-0002, ops record |
| 15 | CI/CD pipeline | done | [15-cicd-pipeline.md](15-cicd-pipeline.md) | check.yml, ci-workflows@87dc5e1 ci-python.yml / security.yml, check.sh |
| 16 | Deployment | done | [16-deployment.md](16-deployment.md) | railway.toml, Dockerfile, __main__.py, _sentry.py, runtime.md, ops record |
| 17 | Test coverage matrix | done | [17-test-coverage-matrix.md](17-test-coverage-matrix.md) | tests/*.py, runtime_tests/*.py, pyproject.toml, check.yml |
| 18 | Git / release workflow | done | [18-git-release-workflow.md](18-git-release-workflow.md) | git log, gh pr list, gh run list, check.yml, runtime.md |
| 19 | Service dependency map | done | [19-service-dependency-map.md](19-service-dependency-map.md) | contract.json, pyproject.toml, uv.lock, Dockerfile, core |
| 20 | Observability | done | [20-observability.md](20-observability.md) | _sentry.py, core http.py, railway.toml, uptime targets.ts |
| 21 | Incident response | done | [21-incident-response.md](21-incident-response.md) | uptime targets.ts, ADR-0002, store.py ready(), runtime.md |
| 22 | DORA | done (proxies; deploys not in git) | [22-dora.md](22-dora.md) | git log, gh pr list, gh run list, runtime.md |

## ADRs

- [ADR-0001 FastAPI on shared backend core](08-adr/ADR-0001-fastapi-on-shared-backend-core.md)
- [ADR-0002 PostgreSQL forced RLS, separate roles](08-adr/ADR-0002-postgres-forced-rls-separate-roles.md)
- [ADR-0003 RS256 JWT from platform-identity](08-adr/ADR-0003-rs256-jwt-from-platform-identity.md)
- [ADR-0004 Append-only idempotent audit](08-adr/ADR-0004-append-only-idempotent-audit.md)
- [ADR-0005 Sentry, no free text](08-adr/ADR-0005-sentry-no-free-text.md)
- [ADR-0006 Railway serverless + dedicated Neon](08-adr/ADR-0006-railway-serverless-neon-dedicated.md)

## Reused docs

- [`docs/runtime.md`](../runtime.md) — API, grants, deploy record (ใช้ใน 09, 12, 14, 16)
- [`docs/gates/BOO-163-security-policy-contracts.md`](../gates/BOO-163-security-policy-contracts.md) — contract gate evidence (ใช้ใน 04)

Validate: `node ~/work/core22/tools/validate.mjs docs/diagrams/*.md docs/diagrams/08-adr/*.md`
