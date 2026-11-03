# 18 — Git and release workflow

จาก `git log origin/main`: งานทำบน feature branch (เช่น `sentry`, `jwt-tail`, `build-hygiene`, `invalid-input`) → push (CI `Check` รันบน push และ pull_request) → merge เข้า `main` เป็น merge commit `Merge PR #N: …` หรือ `Merge <topic>` (merge ใน local clone แล้ว push) → `Check` รันบน `main` → deploy เป็นขั้นแยกด้วย Railway CLI ไม่มี tag / GitHub release

```mermaid
gitGraph
  commit id: "5c21ff8 scaffold"
  commit id: "BOO-163 PR 2 and 3"
  branch codex-shared-infra
  commit id: "runtime pilot"
  checkout main
  merge codex-shared-infra id: "f92621d PR 1"
  branch build-hygiene
  commit id: "uv two-stage image"
  checkout main
  merge build-hygiene id: "96a7522"
  branch invalid-input
  commit id: "InvalidInput 422"
  checkout main
  merge invalid-input id: "8571414"
  commit id: "core pin 21d5f44"
  branch sentry
  commit id: "Sentry + first deploy notes"
  checkout main
  merge sentry id: "8c4491b PR 4"
  branch type-and-stack-only
  commit id: "no free text"
  checkout main
  merge type-and-stack-only id: "0187719 PR 14"
```

(PR #5–#13 ถูก merge ระหว่าง 8c4491b และ 0187719 ในรูปแบบเดียวกัน ย่อไว้)

```mermaid
flowchart LR
  A["Feature branch"] --> B["push: Check runs"]
  B --> C["PR opened: Check runs on pull_request"]
  C --> D{"Check green + review (Codex rounds noted in PR titles)"}
  D -->|"yes"| E["Local merge commit into main, push"]
  E --> F["Check on main"]
  F --> G["Owner go"]
  G --> H["git archive main + railway up --ci"]
  H --> I["Railway healthcheck /readyz"]
  I --> J["Uptime worker hourly /readyz"]
```

Sources: `git log --merges origin/main`, `gh pr list --state merged`, `gh run list` (branches `sentry`, `jwt-tail`, …), `.github/workflows/check.yml`, `docs/runtime.md` ("Deployed (owner go 2026-11-02)"), `railway.toml`, ops record: book-platforms-status (2026-11-03) (deploy recipe)

## Open questions

- branch protection / required checks บน `main` (ไม่อยู่ใน repo)
- PR #1 ไม่ปรากฏใน `gh pr list --state merged` (merge commit `f92621d` บอก "Merge PR #1") — น่าจะ merge local แล้วปิด PR
