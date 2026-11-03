# 21 — Incident response

repo นี้ **ไม่มี** `RUNBOOK.md` หรือ postmortem template flow ด้านล่างประกอบจาก alert channel และ rollback rule ที่มีจริง

```mermaid
flowchart TD
  A1["Uptime worker: /readyz fails twice"] --> T["Telegram alert to owner"]
  A2["Sentry: new unhandled error (type + stack + route)"] --> S["Sentry notification (channel not documented)"]
  A3["Caller error: posture-monitor or mcp-hub sees 401 / 5xx"] --> C["Caller-side failure noticed by owner"]
  T --> TR["Triage"]
  S --> TR
  C --> TR
  TR --> Q1{"/healthz ok?"}
  Q1 -->|"no"| R1["Railway: container crash or sleep wake failure - check logs, restart ON_FAILURE max 3"]
  Q1 -->|"yes, /readyz 503"| Q2{"Which readiness check?"}
  Q2 --> R2["Neon unreachable or suspended"]
  Q2 --> R3["Grant drift on security_runtime"]
  Q2 --> R4["Migration checksum drift"]
  Q2 --> R5["RLS or immutable_audit trigger disabled"]
  Q1 -->|"yes, ready, but 401"| R6["Identity JWKS or issuer / audience mismatch"]
  R1 --> FIX["Fix on branch, Check green, merge, railway up"]
  R2 --> FIX
  R3 --> FIX
  R4 --> FIX
  R5 --> FIX
  R6 --> FIX
  FIX --> RB{"Fix not possible quickly?"}
  RB -->|"yes"| ROLL["Rollback per runtime.md: stop runtime, consumers back to previous adapter, never downgrade SQL"]
  RB -->|"no"| VER["Verify /readyz 200 and one scoped call"]
  ROLL --> VER
  VER --> PMORT["Postmortem: no template in repo"]
```

ตัวอย่างจริงของ "fix-forward" อยู่ใน `docs/runtime.md` (เช่น review rounds PR #4–#14 Sentry, readiness regression 2026-10-15) แต่ไม่ใช่ production incident

Sources: platform-uptime-worker `src/targets.ts`, [ADR-0002](https://github.com/bookchaowalit/architecture-docs/blob/main/docs/architecture/decisions/ADR-0002-production-baseline-monitoring-backups.md), `src/platform_security/_sentry.py`, `src/platform_security/store.py` (`ready`), platform-backend-core@21d5f44 `http.py`, `auth.py`, `railway.toml`, `docs/runtime.md` (rollback paragraph), ops record: book-platforms-status (2026-11-03)

## Open questions

- Sentry notification channel และ severity rules
- on-call / response target (solo owner) และ postmortem location
- runbook สำหรับ rotate `security_runtime` password / Sentry DSN (runtime.md: credential rotation belongs to release gates)
- posture-monitor แจ้งเตือนเมื่อ security-api ตอบผิดพลาดหรือไม่ (ไม่อยู่ใน ops record ของ service นี้)
