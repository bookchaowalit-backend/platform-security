"""BOO-163: tenant, permission, secret-reference, audit and privacy contracts."""

from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import security_contracts as sc  # noqa: E402

GATE = json.loads((ROOT / "fixtures/gates/security-policy-contracts.json").read_text(encoding="utf-8"))
FIX = ROOT / "fixtures" / "security"
MATRIX = sc.load_json(sc.CONTRACT_DIR / "permission-matrix.json")
PRIVACY = sc.load_json(sc.CONTRACT_DIR / "privacy-classes.json")


def fixture(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def secret_looking_samples() -> list[str]:
    """Credential-shaped strings assembled at runtime so none is committed verbatim.

    All are synthetic and non-functional."""
    body = "Q7wErT9yUiOp3AsDfGh5JkLz"
    return [
        "sk" + "_live_" + body,
        "gh" + "p_" + body + "1234",
        "AK" + "IA" + "Z7Q2EXAMPLE9W4X1",
        "xo" + "xb-" + "1234-5678-" + body,
        "-----BEGIN " + "PRIVATE KEY-----",
        "ey" + "JhbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiJ4In0" + "." + "c2lnbmF0dXJl",
        "0123456789abcdef" * 3,
        "postgres://app:" + "hunter2pass" + "@db.example.invalid/x",
        "Bearer " + body,
        body + "Zx81",
    ]


def assert_reason(test: unittest.TestCase, errors: list[str], case: dict) -> None:
    """Each invalid fixture must fail for its stated reason, not just fail."""
    test.assertTrue(case.get("expect"), f"invalid fixture without expect: {case['why']}")
    test.assertTrue(any(case["expect"] in e for e in errors), (case["why"], case["expect"], errors))


def valid_ref() -> dict:
    return copy.deepcopy(fixture("secret-references.json")["valid"][1])


def valid_event() -> dict:
    return copy.deepcopy(fixture("audit-events.json")["valid"][0])


class GateDriftTests(unittest.TestCase):
    def test_contract_json_capabilities_are_all_mapped(self):
        contract = json.loads((ROOT / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual(set(contract["capabilities"]), set(GATE["contract_json_capabilities"]))
        for cap, entry in GATE["contract_json_capabilities"].items():
            if entry["status"] == "defined":
                self.assertTrue((ROOT / entry["schema"]).is_file(), cap)
                if "instance" in entry:
                    self.assertTrue((ROOT / entry["instance"]).is_file(), cap)

    def test_every_gate_contract_exists_and_uses_supported_keywords(self):
        self.assertEqual(set(GATE["gate_contracts"]), set(sc.SCHEMAS))
        for name, rel in GATE["gate_contracts"].items():
            self.assertEqual(rel, f"contracts/security/{sc.SCHEMAS[name]}")
            schema = sc.load_schema(name)
            self.assertTrue(schema.get("x-contract", "").startswith("platform-security."), name)
            self.assertEqual(sc.unsupported_keywords(schema), [], name)

    def test_shipped_policies_are_valid(self):
        self.assertEqual(sc.check_all(), [])

    def test_providers_match_schema_enum_and_ref_pattern(self):
        schema = sc.load_schema("secret-reference")
        enum = schema["properties"]["provider"]["enum"]
        scheme = re.match(r"\^\(([^)]*)\)://", schema["properties"]["ref"]["pattern"]).group(1).split("|")
        self.assertEqual(set(GATE["secret_providers"]), set(enum))
        self.assertEqual(set(enum), set(scheme))
        for alias, canonical in GATE["provider_aliases"].items():
            self.assertIn(canonical, enum, alias)

    def test_every_known_scope_maps_to_a_matrix_action(self):
        mapped = {s for a in MATRIX["actions"] for s in a.get("legacy_scopes", [])}
        for scope in GATE["legacy_bearer_scopes"] + GATE["pr1_runtime_scopes"]:
            self.assertIn(scope, mapped, scope)

    def test_every_auth_class_privacy_is_a_declared_class(self):
        ids = {c["id"] for c in PRIVACY["classes"]}
        for row in GATE["authentication_classes"]:
            self.assertIn(row["privacy_class"], ids)
            if row["role"] not in (None, "matrix"):
                self.assertIn(row["role"], MATRIX["matrix"])

    def test_audit_immutable_fields_cover_every_property(self):
        schema = sc.load_schema("audit-event")
        self.assertTrue(schema["x-append-only"])
        self.assertEqual(set(schema["x-immutable-fields"]), set(schema["properties"]))


class OwnerDecisionTests(unittest.TestCase):
    DOC = ROOT / "docs" / "gates" / "BOO-163-security-policy-contracts.md"

    def test_fixture_records_accepted_decision_with_date(self):
        decision = GATE["owner_decision"]
        self.assertIsInstance(decision, dict)
        self.assertEqual(decision.get("status"), "accepted")
        self.assertEqual(decision.get("date"), "2026-10-16")
        self.assertEqual(decision.get("accepted_option"), "BOO-163: accept the security policy contracts.")
        self.assertTrue(decision.get("verbatim_answer"))
        self.assertTrue(decision.get("open_follow_ups"))

    def test_doc_marks_decision_accepted_with_date(self):
        doc = self.DOC.read_text(encoding="utf-8")
        self.assertIn("## Owner decision — ACCEPTED (owner decision 2026-10-16)", doc)
        self.assertIn(GATE["owner_decision"]["verbatim_answer"], doc)
        self.assertIn(GATE["owner_decision"]["accepted_option"], doc)
        self.assertNotIn("PROPOSED, NOT ACCEPTED", doc)
        self.assertIn("### Still open", doc)

    def test_contract_files_carry_accepted_marker_not_proposed(self):
        files = sorted((ROOT / "contracts" / "security").glob("*.json"))
        self.assertTrue(files)
        stale = re.compile(r"\bproposed\b|not\s+accepted", re.I)
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(stale.search(text), f"{path.name} still says PROPOSED / not accepted")
            if path.name.endswith(".schema.json"):
                self.assertIn("Accepted contract for BOO-163 (owner decision 2026-10-16)",
                              json.loads(text)["description"], path.name)

    def test_scaffold_status_unchanged_by_decision(self):
        contract = json.loads((ROOT / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["status"], "scaffolded")


class TenantTests(unittest.TestCase):
    def test_fixtures(self):
        data = fixture("tenants.json")
        for doc in data["valid"]:
            self.assertEqual(sc.tenant_errors(doc), [], doc["slug"])
        for case in data["invalid"]:
            assert_reason(self, sc.tenant_errors(case["doc"]), case)


class PermissionTests(unittest.TestCase):
    def test_deny_by_default(self):
        self.assertFalse(sc.authorize(MATRIX, "viewer", "policy:manage"))
        self.assertFalse(sc.authorize(MATRIX, "unknown-role", "api:read"))
        self.assertFalse(sc.authorize(MATRIX, "owner", "audit:delete"))
        self.assertTrue(sc.authorize(MATRIX, "viewer", "api:read"))

    def test_only_service_resolves_secrets_and_appends_audit(self):
        for role in MATRIX["matrix"]:
            expected = role == "service"
            self.assertEqual(sc.authorize(MATRIX, role, "secret_reference:resolve"), expected, role)
            self.assertEqual(sc.authorize(MATRIX, role, "audit:append"), expected, role)

    def test_auditor_is_read_only(self):
        mutates = {a["id"] for a in MATRIX["actions"] if a["mutates"]}
        self.assertEqual(set(MATRIX["matrix"]["auditor"]) & mutates, set())

    def test_policy_mutations_are_rejected(self):
        bad = copy.deepcopy(MATRIX)
        bad["matrix"]["owner"].append("secret_reference:resolve")
        self.assertTrue(any("service-only" in e for e in sc.permission_policy_errors(bad)))
        bad = copy.deepcopy(MATRIX)
        bad["actions"].append({"id": "audit:delete", "capability": "audit", "mutates": True})
        self.assertTrue(any("append-only" in e for e in sc.permission_policy_errors(bad)))
        bad = copy.deepcopy(MATRIX)
        bad["matrix"]["viewer"].append("tenant:destroy")
        self.assertTrue(any("unknown action" in e for e in sc.permission_policy_errors(bad)))
        bad = copy.deepcopy(MATRIX)
        bad["default"] = "allow"
        self.assertNotEqual(sc.permission_policy_errors(bad), [])
        with self.assertRaises(sc.ContractError):
            sc.authorize(bad, "viewer", "api:read")
        bad = copy.deepcopy(MATRIX)
        del bad["matrix"]["viewer"]
        self.assertTrue(any("matrix roles" in e for e in sc.permission_policy_errors(bad)))


class SecretReferenceTests(unittest.TestCase):
    def test_valid_fixtures(self):
        for doc in fixture("secret-references.json")["valid"]:
            self.assertEqual(sc.secret_reference_errors(doc), [], doc["name"])

    def test_invalid_fixtures(self):
        for case in fixture("secret-references.json")["invalid"]:
            assert_reason(self, sc.secret_reference_errors(case["doc"]), case)

    def test_rejects_literal_secret_as_ref(self):
        for literal in secret_looking_samples():
            doc = valid_ref()
            doc["ref"] = literal
            self.assertNotEqual(sc.secret_reference_errors(doc), [], literal[:6])

    def test_rejects_secret_hidden_inside_a_reference_path(self):
        for literal in secret_looking_samples():
            if "://" in literal:  # URL credentials are covered by test_rejects_literal_secret_as_ref
                continue
            token = re.sub(r"[^A-Za-z0-9_-]", "", literal)
            doc = valid_ref()
            doc["ref"] = f"vault://platform/{token}#v1"
            errors = sc.secret_reference_errors(doc)
            self.assertTrue(any("secret-looking" in e for e in errors), (literal[:6], errors))

    def test_rejects_secret_in_any_field(self):
        doc = valid_ref()
        doc["purpose"] = secret_looking_samples()[0]
        self.assertNotEqual(sc.secret_reference_errors(doc), [])

    def test_value_field_is_never_accepted(self):
        for field in ("value", "secret", "plaintext"):
            doc = valid_ref()
            doc[field] = "placeholder"
            self.assertTrue(any("unexpected field" in e for e in sc.secret_reference_errors(doc)), field)

    def test_detector_does_not_flag_references_or_ids(self):
        for text in ("vault://platform/payments/webhook-signing#v3", "GOOGLE_REFRESH_TOKEN",
                     "00000000-0000-4000-8000-000000000a01", "/api/finance/v1/summary",
                     "Webhook signature verification", "[REDACTED]"):
            self.assertFalse(sc.is_secret_like(text), text)


class AuditTests(unittest.TestCase):
    def test_valid_fixtures(self):
        for doc in fixture("audit-events.json")["valid"]:
            self.assertEqual(sc.audit_event_errors(doc, PRIVACY), [], doc["event_id"])

    def test_invalid_fixtures(self):
        for case in fixture("audit-events.json")["invalid"]:
            assert_reason(self, sc.audit_event_errors(case["doc"], PRIVACY), case)

    def test_missing_actor_or_tenant_is_invalid(self):
        for field in ("actor", "tenant_id"):
            doc = valid_event()
            del doc[field]
            errors = sc.audit_event_errors(doc)
            self.assertIn(f"$: missing required field {field!r}", errors)
            with self.assertRaises(sc.ContractError):
                sc.AuditLog(PRIVACY).append(doc)

    def test_missing_or_unknown_privacy_class_raises_contract_error_on_append(self):
        for bad in (None, "top-secret", "secret"):
            doc = valid_event()
            if bad is None:
                del doc["privacy_class"]
            else:
                doc["privacy_class"] = bad
            with self.assertRaises(sc.ContractError, msg=repr(bad)):
                sc.AuditLog(PRIVACY).append(doc)
            if bad != "secret":  # "secret" is a known class; only the audit schema forbids it
                with self.assertRaises(sc.ContractError, msg=repr(bad)):
                    sc.redact_audit_metadata(doc, PRIVACY)

    def test_hex_identifiers_are_not_treated_as_secrets(self):
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"  # W3C trace-context example id
        content_hash = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
        doc = valid_event()
        doc.update(request_id=trace_id, idempotency_key=trace_id)
        doc["target"] = {"type": "audit_log", "id": content_hash}
        self.assertEqual(sc.audit_event_errors(doc, PRIVACY), [])
        self.assertEqual(sc.AuditLog(PRIVACY).append(doc)["request_id"], trace_id)

    def test_hex_heuristic_still_applies_outside_identifier_fields(self):
        doc = valid_event()
        doc["metadata"] = {"blob": "0123456789abcdef" * 2}
        self.assertTrue(any("secret-looking" in e for e in sc.audit_event_errors(doc, PRIVACY)))
        doc = valid_event()
        doc["request_id"] = "gh" + "p_" + "Q7wErT9yUiOp3AsDfGh5JkLz1234"
        self.assertTrue(any("secret-looking" in e for e in sc.audit_event_errors(doc, PRIVACY)))

    def test_secret_in_metadata_is_rejected(self):
        doc = valid_event()
        doc["metadata"] = {"token": secret_looking_samples()[1]}
        self.assertTrue(any("secret-looking" in e for e in sc.audit_event_errors(doc, PRIVACY)))

    def test_log_is_append_only_and_hash_chained(self):
        log = sc.AuditLog(PRIVACY)
        for attr in ("update", "delete", "remove", "clear", "replace", "truncate"):
            self.assertFalse(hasattr(log, attr), attr)
        first = log.append(valid_event())
        second = valid_event()
        second["event_id"] = "00000000-0000-4000-8000-0000000e0002"
        second["idempotency_key"] = "idem-0002"
        stored = log.append(second)
        self.assertEqual(stored["prev_hash"], sc.event_hash(first))
        self.assertTrue(log.verify_chain())
        snapshot = log.events(first["tenant_id"])
        snapshot[0]["outcome"] = "denied"
        first["action"] = "audit:read"
        self.assertEqual(log.events(first["tenant_id"])[0]["outcome"], "allowed")
        self.assertEqual(log.events(first["tenant_id"])[0]["action"], "secret_reference:write")

    def test_duplicate_delivery_is_idempotent_and_ids_unique(self):
        log = sc.AuditLog(PRIVACY)
        event = valid_event()
        self.assertEqual(log.append(event), log.append(copy.deepcopy(event)))
        self.assertEqual(len(log.events(event["tenant_id"])), 1)
        clash = valid_event()
        clash["idempotency_key"] = "idem-other"
        with self.assertRaises(sc.ContractError):
            log.append(clash)

    def test_tenant_isolation(self):
        log = sc.AuditLog(PRIVACY)
        a = log.append(valid_event())
        other = valid_event()
        other.update(event_id="00000000-0000-4000-8000-0000000e0005",
                     tenant_id="00000000-0000-4000-8000-000000000b02", idempotency_key="idem-0001")
        log.append(other)
        self.assertEqual([e["event_id"] for e in log.events(a["tenant_id"])], [a["event_id"]])

    def test_privacy_redaction_is_applied_on_append(self):
        log = sc.AuditLog(PRIVACY)
        conf = valid_event()
        conf.update(privacy_class="confidential", metadata={"account": "synthetic-acct"})
        self.assertEqual(log.append(conf)["metadata"], {"account": sc.REDACTED})
        restricted = valid_event()
        restricted.update(event_id="00000000-0000-4000-8000-0000000e0006", idempotency_key="idem-r",
                          privacy_class="restricted", metadata={"name": "synthetic person"})
        self.assertNotIn("metadata", log.append(restricted))


class PrivacyTests(unittest.TestCase):
    def test_policy_mutations_are_rejected(self):
        bad = copy.deepcopy(PRIVACY)
        bad["classes"][4]["storage"] = "plaintext"
        self.assertNotEqual(sc.privacy_policy_errors(bad), [])
        bad = copy.deepcopy(PRIVACY)
        bad["classes"][3]["log_policy"] = "allow"
        self.assertTrue(any("loosen" in e for e in sc.privacy_policy_errors(bad)))
        bad = copy.deepcopy(PRIVACY)
        bad["classes"].pop(0)
        self.assertNotEqual(sc.privacy_policy_errors(bad), [])

    def test_secret_class_is_reference_only(self):
        secret = next(c for c in PRIVACY["classes"] if c["id"] == "secret")
        self.assertEqual((secret["storage"], secret["log_policy"], secret["audit_metadata"]),
                         ("reference_only", "deny", "deny"))


if __name__ == "__main__":
    unittest.main()
