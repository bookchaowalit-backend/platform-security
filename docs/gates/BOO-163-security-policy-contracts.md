# BOO-163 — Security policy contracts gate evidence

| Item | Value |
|---|---|
| Issue | BOO-163 |
| System | `security-identity` (`repository-catalog/registries/system-repositories.yaml`, solo-empire) |
| Owning repo | `bookchaowalit-backend/platform-security` |
| Base | `origin/main` @ `4d3ee11` |
| Status | Evidence only. Owner decision **PROPOSED, NOT ACCEPTED**. No status change, runtime move or cutover. |

## Next gate (verbatim)

> Define tenant, permission, secret-reference, audit, and privacy policy contracts.

## Contract section answered

`systems/architecture/solo-empire-api-contract-v1.md#authentication-classes`
(private `architecture-docs` repo). That document is marked `status: retired`
(2026-10-11, `infra/api` archived), but the registry still names it as this
system's contract. These are the rules this gate carries forward from it:

- Three authentication classes: public read, Bearer protected, and signed webhook.
- Least-privilege Bearer scopes: `finance:read`, `api:read`, `api:write` and `ai:generate`.
- Provider credentials are resolved inside the server-side integration boundary
  and are never sent by clients or written to API responses, logs, tasks or
  payload metadata.

## Delivered contracts

| Gate noun | Contract (JSON Schema 2020-12 subset) | Policy instance / fixtures | Enforced by |
|---|---|---|---|
| tenant | `contracts/security/tenant.schema.json` | `fixtures/security/tenants.json` | `scripts/security_contracts.py` `tenant_errors` |
| permission | `contracts/security/permission.schema.json` | `contracts/security/permission-matrix.json` (role -> action, deny-by-default) | `permission_policy_errors`, `authorize` |
| secret-reference | `contracts/security/secret-reference.schema.json` (`provider://path#version`, reference-only) | `fixtures/security/secret-references.json` | `secret_reference_errors`, `is_secret_like` |
| audit | `contracts/security/audit-event.schema.json` (`x-append-only`, `x-immutable-fields`) | `fixtures/security/audit-events.json` | `audit_event_errors`, `AuditLog` (append-only, hash-chained, idempotent) |
| privacy | `contracts/security/privacy-class.schema.json` | `contracts/security/privacy-classes.json` | `privacy_policy_errors`, `redact_audit_metadata` |

Gate mapping fixture: `fixtures/gates/security-policy-contracts.json`.
Tests: `tests/test_security_contracts.py` (29 tests). `bash scripts/check.sh` runs
them, and `.github/workflows/check.yml` runs that script in hosted CI on
Python 3.11 and 3.12.

## Inventory and mapping (from source)

| Source (file:line) | Item | Mapped to |
|---|---|---|
| `contract.json:8` (`origin/main`) | capabilities `secret-reference`, `policy`, `audit`, `privacy` | secret-reference, permission, audit-event, privacy-class schemas |
| `contract.json:8` | capability `waf-controls` | **out of scope**: the gate does not name it (gap G5) |
| `contract.json:3` / `scripts/check.py:119` | `status: scaffolded` must stay | unchanged |
| API contract, Authentication classes | Public read / Bearer protected / Signed webhook | `authentication_classes` in the gate fixture, each mapped to a privacy class |
| API contract, Bearer protected | scopes `finance:read`, `api:read`, `api:write`, `ai:generate` | matrix actions with `legacy_scopes` of the same name |
| `solo-empire@99ddc05c:infra/scripts/utils/secret_resolver.py:225` | `EnvProvider` (`env`) | provider `env` |
| `solo-empire@99ddc05c:infra/scripts/utils/secret_resolver.py:235` | `InfisicalProvider` (`infisical`, aliases `infisical-api`/`-cli` at :398-404) | provider `infisical` |
| `solo-empire@99ddc05c:infra/scripts/utils/secret_resolver.py:348` | `VaultProvider` (`vault`, alias `hashicorp-vault`) | provider `vault` |
| `solo-empire@99ddc05c:infra/scripts/utils/secrets_health.py:1-12` | health check that "never prints secret values" | invariant that secret-class data is never written to logs or audit metadata |
| PR #1 `src/platform_security/store.py` `reference()` | providers `env`, `vault` and `aws` | `aws` aliased to `aws-sm` |
| PR #1 `src/platform_security/app.py` scopes | `references:read/write`, `audit:read/write` | `secret_reference:read/write`, `audit:read`, `audit:append` |
| PR #1 `src/platform_security/migrations.py` | `security_audit` with an `immutable_audit` trigger and forced RLS on `workspace_id` | audit-event `x-append-only` and `tenant_id` required |

`solo-empire@99ddc05c` is the parent of `5f034945` ("the hub is only the
registry and the clone folder"), the commit that removed the registry's
`source_paths` (`infra/platform` and `infra/scripts/utils/secrets_health.py`)
from solo-empire. Only code structure and provider class names were read. No
secret, `.env` file or credential store was read.

## Key rules encoded

1. **Secret reference is reference-only.** `ref` must match
   `^(env|infisical|vault|aws-sm)://<path>#(v<N>|latest)$` and its scheme must
   equal `provider`. `privacy_class` is always `secret`, and
   `additionalProperties: false` blocks fields like `value`, `secret` or
   `plaintext`. `..` is rejected. Any field that looks like a credential is
   rejected: known token prefixes, PEM blocks, JWTs, credentials embedded in a
   URL, `Bearer …`, long hex strings, or long high-entropy mixed-case strings.
2. **The permission matrix is deny-by-default.** `secret_reference:resolve` and
   `audit:append` go only to service-only roles. No audit update or delete
   action may exist. The auditor role is read-only.
3. **Audit events are append-only.** `tenant_id` and `actor` (`type` and `id`)
   are required, and so are `action`, `target`, `outcome`, `occurred_at` and
   `privacy_class`. `secret` is not an allowed privacy class for an event. Each
   event links to the previous one through a `prev_hash` chain. A repeated
   idempotency key returns the original event, and an `event_id` cannot be
   appended twice.
4. **Privacy classes are ordered** `public < internal < confidential < restricted < secret`.
   As the rank rises, the log and audit-metadata policy can only get stricter.
   Confidential metadata is redacted, restricted and secret metadata is
   dropped, and secret data is stored `reference_only`.

## Red / green proof

- Red: `/home/bookchaowalit/linear-sprint-2026-10-15/BOO-163-red.log`. Two
  deliberate mutations were made: `actor` and `tenant_id` were removed from the
  audit `required` list, and `operator` was granted `secret_reference:resolve`.
  Four tests failed: `test_missing_actor_or_tenant_is_invalid`,
  `test_invalid_fixtures`, `test_shipped_policies_are_valid` and
  `test_only_service_resolves_secrets_and_appends_audit`.
- Green: `/home/bookchaowalit/linear-sprint-2026-10-15/BOO-163-green.log`.
- Full check: `/home/bookchaowalit/linear-sprint-2026-10-15/BOO-163-check.log`.

## Gaps

| # | Gap |
|---|---|
| G1 | No runtime enforces these contracts yet. PR #1 (`codex/shared-infrastructure-20261015`) adds a FastAPI/PostgreSQL pilot whose provider set (`env`, `vault`, `aws`), scopes and audit fields only partly match this contract: it has no `infisical`, no `#version`, no `outcome`/`privacy_class`/`prev_hash`, and an actor that is a UUID only. Those need aligning after the owner decision. |
| G2 | The registry `source_paths` (`infra/platform`, `infra/scripts/utils/secrets_health.py`) no longer exist in solo-empire HEAD. The registry entry should be updated. |
| G3 | The named contract (`solo-empire-api-contract-v1.md`) is retired. A successor security contract doc in `architecture-docs` is needed. |
| G4 | Signed-webhook verification and the token-hash table (`API_TOKENS_JSON`) are only represented as secret references here. Their verification rules are not re-specified. |
| G5 | `waf-controls` (a `contract.json` capability) has no contract. Rate limiting/WAF is still the API contract's open operational gap. |
| G6 | The schemas use a supported JSON Schema subset validated by a stdlib validator. There is no third-party `jsonschema` cross-check and no pinned canonical copy like the sibling repos have. |
| G7 | Secret-literal detection is heuristic. It is a guardrail, not a substitute for provider-side scanning. |

## Owner decision — PROPOSED, NOT ACCEPTED

The owner is asked to accept or amend the following. None of it is accepted,
and nothing below has been applied to any runtime, registry or production
system.

1. Adopt the five contracts in `contracts/security/` as `platform-security`'s
   v1 tenant, permission, secret-reference, audit-event and privacy-class
   contracts.
2. Adopt `provider://path#version` with providers `env | infisical | vault | aws-sm`
   as the only allowed secret representation, and forbid secret values in any
   platform API, log or audit record.
3. Adopt the deny-by-default role matrix in `contracts/security/permission-matrix.json`,
   including the mapping of the legacy Bearer scopes and PR #1 scopes to matrix
   actions.
4. Require PR #1's runtime (or its successor) to conform to these contracts
   before any consumer is moved (G1).
5. Record a successor contract doc and refresh the registry `source_paths`
   (G2, G3). Handle `waf-controls` as a separate gate (G5).
