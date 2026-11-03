# ADR-0001 — FastAPI service on platform-backend-core, pinned by Git commit in uv.lock

- Status: accepted (retro-documented)
- Date of evidence: 2026-10-23 (PR #1 merged `f92621d`), core repin 2026-10-29 (`8c3aa04`)

## Context
service ต้องการ auth, DB pool, request boundary และ diagnostics แบบเดียวกับ platform service อื่น แต่ `platform-backend-core` ไม่อยู่บน PyPI

## Decision
ใช้ `platform_backend_core.create_app` (FastAPI) + `require_scope` + `Database` + `MigrationRunner` โดย pin core ที่ commit `21d5f44d26220080cbed43b9807979dc84a8533a` ผ่าน `[tool.uv.sources]` และ `uv.lock`; Dockerfile ติดตั้งด้วย `uv sync --frozen` เท่านั้น

## Evidence
- `pyproject.toml` (`dependencies`, `[tool.uv.sources]` comment "dependency confusion")
- `uv.lock` entry `platform-backend-core` source `?rev=21d5f44…`
- `src/platform_security/app.py` (`base_app('security', …, max_body_bytes=8192)`)
- `tests/test_build_hygiene.py::CorePinTests::test_lock_resolves_the_reviewed_core_commit`

## Consequences
- อัปเกรด core = เปลี่ยน rev แล้ว `uv lock` (docs/runtime.md)
- core's `_Boundary` กลืน exception เป็น 500 ทำให้ต้องเพิ่ม `CaptureErrors` (ADR-0005)
- ops record: core `dc1fa7d` (ServiceTokenSource) มีแล้ว แต่ repo นี้ยัง pin `21d5f44`
