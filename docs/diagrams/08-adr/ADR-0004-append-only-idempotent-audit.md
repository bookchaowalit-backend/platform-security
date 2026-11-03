# ADR-0004 — Append-only audit with a DB trigger and idempotency fingerprint

- Status: accepted (retro-documented)
- Date of evidence: 2026-10-15 (pilot), BOO-163 contracts accepted 2026-10-16

## Decision
- ตาราง `security_audit` มี trigger `immutable_audit` (BEFORE UPDATE OR DELETE OR TRUNCATE → exception) และ `REVOKE ALL … FROM PUBLIC`
- `POST /v1/audit` ต้องมี `Idempotency-Key`; `UNIQUE(workspace_id, event_key)` + `ON CONFLICT DO NOTHING`; fingerprint = sha256 ของ `[actor, action, target]` — ตรง = คืน event เดิม, ต่าง = 409
- readiness fail ถ้า runtime role มี UPDATE/DELETE/TRUNCATE บน audit หรือ trigger ถูกปิด

## Evidence
- `src/platform_security/migrations.py`, `src/platform_security/store.py` (`append`, `ready`)
- `runtime_tests/test_runtime.py::test_audit_append_idempotent_and_immutable`, `::test_audit_concurrent_dedupe_is_atomic`
- `runtime_tests/test_http.py::test_readiness_rejects_each_forbidden_audit_privilege`

## Consequences
- ไม่มี `prev_hash` chain ใน runtime (contract มี) — gap G1
- ไม่มี retention/deletion (docs/runtime.md: "no scheduled deletion")
