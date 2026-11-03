# 11 — State machines

ตารางใน DB ไม่มี status column lifecycle ที่มีจริงคือพฤติกรรมของ row/request ที่ code บังคับ ส่วน `tenant.status` อยู่ใน contract อย่างเดียว

## Audit append request (per Idempotency-Key)

```mermaid
stateDiagram-v2
  [*] --> Received
  Received --> Rejected401: token invalid
  Received --> Rejected403: missing audit write scope
  Received --> Rejected422: bad key, action or target
  Received --> NewEvent: key unseen in workspace
  Received --> Replay: key seen, same fingerprint
  Received --> Conflict409: key seen, different fingerprint
  NewEvent --> Stored
  Replay --> Stored: returns original row
  Stored --> Stored: UPDATE, DELETE, TRUNCATE rejected by trigger
  Rejected401 --> [*]
  Rejected403 --> [*]
  Rejected422 --> [*]
  Conflict409 --> [*]
```

## Secret reference row

```mermaid
stateDiagram-v2
  [*] --> Absent
  Absent --> Stored: PUT valid metadata
  Stored --> Stored: PUT same name overwrites provider, reference, purpose, rotated_at
  Stored --> Stored: rotated_at set by caller
  note right of Stored
    No DELETE route and no DELETE grant
  end note
```

## Service readiness

```mermaid
stateDiagram-v2
  [*] --> Starting
  Starting --> Exited: missing env or dependency, generic SystemExit
  Starting --> Unavailable: process up, checks fail
  Unavailable --> Ready: migrations, grants, RLS, trigger all valid
  Ready --> Unavailable: grant drift, checksum drift, DB error
  Ready --> Sleeping: Railway sleep on idle
  Sleeping --> Starting: next request
```

## Tenant status (contract only, not enforced)

```mermaid
stateDiagram-v2
  [*] --> active
  active --> suspended
  suspended --> active
  active --> closed
  suspended --> closed
```

contract นิยามแค่ enum `active | suspended | closed` และ action `tenant:manage` ("Suspend, close or rename a tenant") — ทิศทาง transition ข้างบนเป็น **interpretation** ของ enum ไม่ได้กำหนดใน schema

Sources: `src/platform_security/store.py`, `src/platform_security/app.py`, `src/platform_security/migrations.py`, `src/platform_security/__main__.py`, platform-backend-core@21d5f44 `http.py`, `docs/runtime.md` (grants), ops record: book-platforms-status (2026-11-03) (sleep on), `contracts/security/tenant.schema.json`, `contracts/security/permission-matrix.json`

## Open questions

- tenant transitions ที่อนุญาตจริง (เช่น `closed` → อื่นได้หรือไม่) ไม่มีใน contract
- Railway sleep → wake เป็นพฤติกรรม platform (ops record "sleep on") ไม่ได้อยู่ใน repo
