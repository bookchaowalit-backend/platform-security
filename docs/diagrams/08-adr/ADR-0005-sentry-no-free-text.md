# ADR-0005 — Sentry errors only, no free text leaves the process

- Status: accepted (retro-documented)
- Date of evidence: PR #14 merged 2026-11-03 (`0187719`)

## Context
PRs #4–#13 พยายาม regex-scrub credential ออกจาก message แต่ review รอบถัดไปหา serialisation ที่หลุดได้เสมอ

## Decision
`_scrub_event` ทิ้ง `exception.values[].value`, `message`, `logentry`, `breadcrumbs`, `extra`, `user`, request (เหลือ method), `dynamic_sampling_context`; `traces_sample_rate=None`, `trace_propagation_targets=[]`, `include_local_variables=False`, `send_default_pii=False`, LoggingIntegration ปิด; `CaptureErrors` เป็น innermost middleware เพื่อจับ 500 ที่ core กลืน

## Evidence
- `src/platform_security/_sentry.py`, `src/platform_security/app.py` (`user_middleware.append(Middleware(CaptureErrors))`)
- `runtime_tests/test_sentry.py::test_no_exception_text_leaves_the_process`
- `docs/runtime.md` "No free text to Sentry — 2026-11-03"
- ops record: book-platforms-status (2026-11-03) ("owner can revert if message text is needed")

## Consequences
- debug ต้องอาศัย type + stack + route template เท่านั้น
- ops record: อีก 7 service มี guard "no event without an active client + transport" ที่ security 0187719 ไม่มี
