# ADR-0006 — Railway serverless container + dedicated Neon project, CLI deploy

- Status: accepted (retro-documented)
- Date of evidence: deployed 2026-11-02 (owner go)

## Decision
- build จาก `Dockerfile` (two-stage, UID 65532, `CMD python -m platform_security serve`), Railway `healthcheckPath = /readyz`, restart `ON_FAILURE` ≤ 3
- Railway project `platform-security`, service `security-api`, region `asia-southeast1-eqsg3a`, sleep on
- Neon project `platform-security` (aws-ap-southeast-1, PG 16), secrets ใน Infisical `/platform-security`
- deploy ด้วย `railway up --ci` จาก `git archive main` (ops record deploy recipe) — CI ไม่มี deploy job

## Evidence
- `Dockerfile`, `.railway/railway.ts`, `.github/workflows/check.yml` (job `image` "Nothing is pushed or deployed")
- `docs/runtime.md` "Sentry and first deployment — 2026-11-02"
- ops record: book-platforms-status (2026-11-03)

## Consequences
- cold start หลัง sleep + Neon resume (~6–9 s ตาม ops record) → core pool timeout 20 s
- deployment history ไม่อยู่ใน git/gh (ดู 22-dora.md)
