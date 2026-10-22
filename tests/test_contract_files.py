"""Shape of the shipped contract files in contracts/security/ and fixtures/security/."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts" / "security"
FIXTURES = ROOT / "fixtures" / "security"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ContractFileTests(unittest.TestCase):
    def test_every_schema_declares_a_draft_unique_id_and_contract_marker(self) -> None:
        ids = []
        for path in sorted(CONTRACTS.glob("*.schema.json")):
            with self.subTest(schema=path.name):
                schema = load(path)
                self.assertTrue(schema["$schema"].startswith("https://json-schema.org/"))
                self.assertTrue(schema.get("$id"))
                self.assertTrue(schema.get("x-contract"))
                self.assertEqual(schema.get("type"), "object")
                ids.append(schema["$id"])
        self.assertGreaterEqual(len(ids), 5)
        self.assertEqual(len(ids), len(set(ids)), "schema $id values must be unique")

    def test_closed_schemas_reject_unknown_properties(self) -> None:
        for name in ("permission", "privacy-class", "secret-reference", "tenant"):
            with self.subTest(schema=name):
                schema = load(CONTRACTS / f"{name}.schema.json")
                self.assertIs(schema.get("additionalProperties"), False)

    def test_secret_reference_schema_is_reference_only(self) -> None:
        schema = load(CONTRACTS / "secret-reference.schema.json")
        self.assertTrue(schema.get("x-reference-only"))
        self.assertNotIn("value", schema.get("properties", {}))

    def test_permission_matrix_denies_by_default(self) -> None:
        self.assertEqual(load(CONTRACTS / "permission-matrix.json").get("default"), "deny")

    def test_every_fixture_has_valid_and_invalid_cases(self) -> None:
        for path in sorted(FIXTURES.glob("*.json")):
            with self.subTest(fixture=path.name):
                data = load(path)
                self.assertTrue(data.get("valid"), "needs at least one valid case")
                self.assertTrue(data.get("invalid"), "needs at least one invalid case")


if __name__ == "__main__":
    unittest.main()
