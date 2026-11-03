# 16 — Deployment

```mermaid
flowchart TB
  subgraph GH["GitHub bookchaowalit-backend/platform-security"]
    MAIN["main"]
  end
  subgraph OP["Owner machine"]
    ARC["git archive main"]
    UPC["railway up --ci"]
  end
  subgraph RW["Railway project platform-security, region asia-southeast1-eqsg3a"]
    SVC["service security-api, Dockerfile build, sleep on"]
    HC["healthcheckPath /readyz, timeout 30 s, restart ON_FAILURE max 3"]
    URL["https://security-api-production-f817.up.railway.app"]
  end
  subgraph NE["Neon project platform-security, aws-ap-southeast-1, PG 16"]
    DB[("DB, owner role + security_runtime")]
  end
  subgraph EXT["Other providers"]
    INF["Infisical /platform-security"]
    ID["platform-identity JWKS, audience security-api"]
    SEN["Sentry project platform-security"]
    UPW["platform-uptime-worker, hourly /readyz"]
  end
  MAIN --> ARC --> UPC --> SVC
  SVC --- HC
  SVC --- URL
  SVC -->|"DATABASE_URL runtime role"| DB
  INF -.->|"secrets copied to Railway vars"| SVC
  SVC -->|"JWKS"| ID
  SVC -->|"errors"| SEN
  UPW -->|"GET /readyz"| URL
```

## Runtime config (env names from code)

| Variable | Use | Source |
|---|---|---|
| `DATABASE_URL` | runtime role for `serve`, DDL role for `migrate` | `__main__.py`, `docs/runtime.md` |
| `JWT_ISSUER`, `JWT_AUDIENCE` | identity issuer, `security-api` | `__main__.py`, `docs/runtime.md` |
| `JWT_JWKS_URL` or `JWT_PUBLIC_KEY` | exactly one | `__main__.py`, core `auth.py` |
| `PORT` | default 8080 | `__main__.py`, `Dockerfile` |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE` | Sentry init | `_sentry.py` |
| `RAILWAY_GIT_COMMIT_SHA`, `RAILWAY_SERVICE_NAME` | release + `service` tag | `_sentry.py` |

Health: `/healthz` = process alive (no DB); `/readyz` = DB + schema/grant/RLS/trigger checks (Railway healthcheck ใช้ตัวนี้) Serverless sleep หมายถึง request แรกหลัง idle ต้องรอ container start + Neon resume (core pool timeout 20 s, connect timeout 15 s)

Sources: `railway.toml`, `Dockerfile`, `src/platform_security/__main__.py`, `src/platform_security/_sentry.py`, platform-backend-core@21d5f44 `db.py`, `http.py`, `docs/runtime.md`, ops record: book-platforms-status (2026-11-03), platform-uptime-worker `src/targets.ts`

## Open questions

- deployed commit ปัจจุบันคืออะไร (first deploy 2026-11-02; 0187719 ไม่มีบันทึก deploy)
- custom domain หรือ gateway route สำหรับ service นี้
- staging environment: ไม่มี (มีแค่ production ใน docs)
