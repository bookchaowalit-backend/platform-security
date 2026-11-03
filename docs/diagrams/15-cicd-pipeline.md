# 15 — CI/CD pipeline

workflow เดียว: `.github/workflows/check.yml` (`name: Check`) trigger `push` (ทุก branch), `pull_request`, `workflow_dispatch`; `permissions: contents: read`; `concurrency: check-${{ github.ref }}` cancel-in-progress สี่ job ไม่มี `needs` ระหว่างกัน (รันขนาน) และ **ไม่มี deploy job**

```mermaid
flowchart TD
  T1["push any branch"] --> W["workflow Check"]
  T2["pull_request"] --> W
  T3["workflow_dispatch"] --> W
  W --> J1["contract (matrix 3.11, 3.12) - ci-python.yml@87dc5e1 v1.1.1"]
  W --> J2["python - ci-python.yml@87dc5e1, postgres true, coverage 87"]
  W --> J3["security - security.yml@87dc5e1"]
  W --> J4["image - docker build, no push"]
  J1 --> J1a["install-command true, test-command bash scripts/check.sh"]
  J1a --> J1b["check.py, security_contracts.py, unittest discover tests"]
  J2 --> J2a["uv sync --frozen --all-extras"]
  J2a --> J2b["Start PostgreSQL, Ruff lint, mypy"]
  J2b --> J2c["pytest -q --cov with PLATFORM_TEST_DSN"]
  J2c --> J2d["Coverage gate 87 percent"]
  J2d --> J2e["uv build --wheel"]
  J3 --> J3a["gitleaks"]
  J3 --> J3b["semgrep"]
  J3 --> J3c["osv-scanner"]
  J3 --> J3d["trivy-fs"]
  J4 --> J4a["docker build --pull --tag platform-security:ci"]
  J4a --> J4b["import platform_backend_core, platform_security.app"]
  J4b --> J4c["id -u is not 0"]
  J1b --> G{"All green?"}
  J2e --> G
  J3a --> G
  J3b --> G
  J3c --> G
  J3d --> G
  J4c --> G
  G -->|"manual, outside CI"| D["Operator: git archive main + railway up --ci"]
```

`format-check: false` ใน ทั้ง `contract` และ `python` (follow-up: ruff format); `typecheck-command: ""` ใน `contract`

Sources: `.github/workflows/check.yml`, platform-ci-workflows@87dc5e1 `.github/workflows/ci-python.yml` (steps Checkout, Set up uv and Python, Install dependencies, Start PostgreSQL, Lint (Ruff), Typecheck, Test, Coverage gate, Drop CI database), platform-ci-workflows@87dc5e1 `.github/workflows/security.yml` (jobs gitleaks, semgrep, osv-scanner, trivy-fs), `scripts/check.sh`, `docs/runtime.md`, ops record: book-platforms-status (2026-11-03) (deploy recipe)

หมายเหตุ: workflow `Shared runtime` (`shared-runtime.yml`, เห็นใน `gh run list` ถึง 2026-10-23) ถูกลบใน commit `52c1cae` และย้าย PostgreSQL tests เข้า job `python` (comment ใน `check.yml`)

## Open questions

- Railway service ต่อ GitHub (auto deploy on push) หรือ CLI อย่างเดียว
