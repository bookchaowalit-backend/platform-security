# ADR-0002 — PostgreSQL with forced RLS, workspace from the token, separate DDL and runtime roles

- Status: accepted (retro-documented)
- Date of evidence: 2026-10-15 (runtime pilot), deployed 2026-11-02

## Context
ข้อมูลทุกแถวเป็นของ workspace หนึ่ง และ service เก็บ metadata ที่เกี่ยวกับ credential ต้องกันการอ่านข้าม workspace แม้ code ผิด

## Decision
- ทุกตารางมี `workspace_id` + `ENABLE` และ `FORCE ROW LEVEL SECURITY` ด้วย policy `workspace_id = current_setting('app.workspace_id')`
- `Database.transaction(workspace)` ตั้ง `app.workspace_id` จาก `Principal.workspace` (claim `ws`) เท่านั้น
- `migrate` ใช้ DDL role; `serve` ใช้ runtime role ที่ต้องเป็น NOSUPERUSER NOBYPASSRLS (core `_configure` ปฏิเสธถ้าไม่ใช่) และได้ grant เฉพาะที่ต้องใช้
- migrations ไม่รันตอน startup

## Evidence
- `src/platform_security/migrations.py`
- platform-backend-core@21d5f44 `db.py` (`_configure`, `transaction`)
- `src/platform_security/__main__.py` (docstring "migrations never run at API startup")
- `docs/runtime.md` (grants SQL; deployed role `security_runtime`)
- `runtime_tests/test_runtime.py::test_reference_and_audit_force_rls_reject_foreign_inserts`

## Consequences
- dedicated Neon project ต่อ service (ops record: Neon free quota per project)
- readiness ต้องตรวจ RLS และ grants ทุกครั้ง (`SecurityStore.ready`)
- owner role ยังแก้ DDL/ปิด trigger ได้ — audit ไม่ tamper-proof ต่อ DBA (docs/runtime.md)
