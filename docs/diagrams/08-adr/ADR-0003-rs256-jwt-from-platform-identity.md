# ADR-0003 — RS256 workspace JWTs from platform-identity, one scope per route

- Status: accepted (retro-documented)
- Date of evidence: owner decision 2026-10-29 (ops record), identity activated 2026-11-03

## Context
caller มีทั้ง person และ service client; service ต้องไม่ไว้ใจ workspace/actor จาก body หรือ header

## Decision
- `TokenVerifier` ต้องตั้ง `JWT_ISSUER`, `JWT_AUDIENCE` และแหล่ง key อย่างเดียว (`JWT_PUBLIC_KEY` หรือ `JWT_JWKS_URL` HTTPS)
- production: issuer platform-identity, audience `security-api`, JWKS `/.well-known/jwks.json`
- route ละหนึ่ง scope: `references:read`, `references:write`, `audit:read`, `audit:write`
- ไม่รับ claim `del` / `obo` (no delegation), lifetime ≤ 3600 s, ต้องมี `sub, ws, iat, exp, jti, iss, aud`

## Evidence
- `src/platform_security/__main__.py`
- `src/platform_security/app.py` (`REFERENCES_READ` … `AUDIT_WRITE`)
- platform-backend-core@21d5f44 `auth.py`, `http.py`
- `docs/runtime.md` ("JWT issuer is platform-identity, audience `security-api`")
- ops record: book-platforms-status (2026-11-03): identity maps `references:*` and `audit:*` → `security.*`

## Consequences
- scope names ไม่ตรงกับ action ใน `permission-matrix.json` (`secret_reference:*`, `audit:append`) — mapping อยู่ใน contract เท่านั้น (gap G1)
- ไม่มี revocation check (core comment "Shared services cannot enforce delegation status or revocation")
