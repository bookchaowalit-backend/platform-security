# 03 — User flows (API call flows per caller)

service นี้ไม่มี UI flow คือลำดับ API call ของแต่ละ caller ทุก flow ผ่าน `_Boundary` ของ core (body ≤ 8192 bytes, timeout 30 s) → `require_scope` → handler → `Database.transaction(workspace)` ที่ตั้ง `app.workspace_id`

## Flow A — posture-monitor บันทึก audit event (active)

```mermaid
flowchart TD
  A1["posture-monitor gets client_credentials token from identity, audience security-api"] --> A2["POST /v1/audit with Idempotency-Key, body action + target"]
  A2 --> A3{"Token valid and has audit:write?"}
  A3 -->|"no token or bad signature"| A4["401 unauthorized"]
  A3 -->|"missing scope"| A5["403 forbidden"]
  A3 -->|"yes"| A6{"action / target / key match identifier patterns?"}
  A6 -->|"no"| A7["422 Invalid metadata or invalid request"]
  A6 -->|"yes"| A8{"event_key already stored in workspace?"}
  A8 -->|"no"| A9["INSERT row, return id, actor, action, target, created_at"]
  A8 -->|"yes, same fingerprint"| A10["Return original event (200)"]
  A8 -->|"yes, different fingerprint"| A11["409 Idempotency conflict"]
```

## Flow B — ผู้ถือ references scope บันทึกและอ่าน secret reference

```mermaid
flowchart TD
  B1["PUT /v1/secret-references/{name} with provider, reference, purpose, rotated_at"] --> B2{"references:write?"}
  B2 -->|"no"| B3["401 / 403"]
  B2 -->|"yes"| B4{"Extra fields like value / workspace / actor?"}
  B4 -->|"yes"| B5["422 invalid request (extra=forbid)"]
  B4 -->|"no"| B6{"name, provider env|vault|aws, reference pattern, purpose, tz-aware rotated_at valid?"}
  B6 -->|"no"| B7["422 Invalid metadata"]
  B6 -->|"yes"| B8["UPSERT on (workspace_id, name), return row"]
  B8 --> B9["GET /v1/secret-references?limit&after (references:read)"]
  B9 --> B10["Rows of this workspace only, ordered by name"]
```

## Flow C — mcp-hub อ่าน audit (read-only)

```mermaid
flowchart LR
  C1["mcp-hub call_cell platform-security"] --> C2["GET /v1/audit?limit=1..100&after=uuid"]
  C2 --> C3{"audit:read?"}
  C3 -->|"yes"| C4["Rows ordered by id (UUID), RLS limits to token ws"]
  C3 -->|"no"| C5["403"]
```

## Flow D — operator / uptime probe

```mermaid
flowchart LR
  D1["Operator: migrate with DDL-role DATABASE_URL"] --> D2["MigrationRunner namespace security applies 0001"]
  D2 --> D3["Grant runtime role exact privileges (docs/runtime.md)"]
  D3 --> D4["serve with runtime-role DATABASE_URL"]
  D5["Uptime worker hourly"] --> D6["GET /readyz"]
  D6 --> D7{"DB SELECT 1, grants, migration checksums, forced RLS, trigger enabled, no audit UPDATE/DELETE/TRUNCATE"}
  D7 -->|"all true"| D8["200 ready"]
  D7 -->|"any false or error"| D9["503 unavailable"]
```

Sources: `src/platform_security/app.py`, `src/platform_security/store.py`, `src/platform_security/__main__.py`, platform-backend-core@21d5f44 `http.py`, `auth.py`, `db.py`, `docs/runtime.md`, `runtime_tests/test_http.py`, ops record: book-platforms-status (2026-11-03), platform-uptime-worker `src/targets.ts`

## Open questions

- ยังไม่มี caller ใดใน ops record ที่เรียก `PUT /v1/secret-references` จริง — Flow B เป็นความสามารถที่มี แต่ไม่รู้ว่ามีผู้ใช้
- mcp-hub เรียก route ไหนบ้างใน `call_cell` (ops record บอกแค่ว่า security 200)
