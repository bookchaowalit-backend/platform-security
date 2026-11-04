# 05 — C4 Context

```mermaid
C4Context
  title System Context - platform-security (security-api)
  Person(owner, "Owner", "Person token via identity, pending Google client ID")
  System(sec, "security-api", "Secret reference metadata and append-only audit per workspace")
  System_Ext(identity, "platform-identity", "Issues RS256 tokens, JWKS, audience security-api")
  System_Ext(posture, "platform-posture-monitor", "Service client, appends audit events")
  System_Ext(hub, "Remote MCP hub", "Service client mcp-hub, cell platform-security")
  System_Ext(gw, "Edge API gateway", "gateway.bookchaowalit.com, route platform-security")
  System_Ext(uptime, "platform-uptime-worker", "Hourly /readyz probe, Telegram alerts")
  SystemDb_Ext(neon, "Neon PostgreSQL", "Project platform-security, PG 16")
  System_Ext(sentry, "Sentry", "Project platform-security, errors only")
  System_Ext(railway, "Railway", "Hosts the container, asia-southeast1, sleep on")

  Rel(owner, sec, "HTTPS + Bearer JWT")
  Rel(posture, gw, "POST /v1/platform-security/v1/audit")
  Rel(hub, gw, "Read calls")
  Rel(gw, sec, "HTTPS, token passed through")
  Rel(uptime, sec, "GET /readyz")
  Rel(sec, identity, "Fetch JWKS")
  Rel(sec, neon, "SQL as security_runtime")
  Rel(sec, sentry, "Error events, no free text")
  Rel(railway, sec, "Runs and healthchecks")
```

Sources: `src/platform_security/__main__.py` (JWT_JWKS_URL, DATABASE_URL), `src/platform_security/_sentry.py`, `railway.toml`, `docs/runtime.md` (Sentry and first deployment), ops record: book-platforms-status (2026-11-03), ops record: api-gateway-edge (2026-11-03), platform-api-gateway `routes.json` @ `4a31ff5`, platform-uptime-worker `src/targets.ts`

หมายเหตุ: central [C4-DIAGRAMS.md](https://github.com/bookchaowalit/architecture-docs/blob/main/docs/architecture/C4-DIAGRAMS.md) ยังไม่มี security-api

## Open questions

- ~~security-api อยู่หลัง edge gateway หรือไม่~~ ตอบแล้ว 2026-11-04: มี route `platform-security` → `https://security-api-production-f817.up.railway.app` ใน platform-api-gateway `routes.json` @ `4a31ff5`; posture-monitor เรียกผ่าน gateway (ops record: api-gateway-edge) direct URL ยังเรียกได้
- MCP hub เรียกผ่าน gateway ทุก cell หรือบาง cell ยัง direct: ops record ระบุ 29/29 cells ผ่าน gateway แต่ไม่ได้ยืนยันใน repo นี้
