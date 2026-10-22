"""scripts/check.py: the scaffold contract and README shape gate."""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check


class CheckScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for name in ("contract.json", "README.md"):
            shutil.copy(ROOT / name, self.tmp / name)
        (self.tmp / "scripts").mkdir()
        shutil.copy(ROOT / "scripts" / "check.sh", self.tmp / "scripts" / "check.sh")
        self.original_root = check.ROOT
        check.ROOT = self.tmp
        self.addCleanup(setattr, check, "ROOT", self.original_root)

    def contract(self) -> dict:
        return json.loads((self.tmp / "contract.json").read_text(encoding="utf-8"))

    def write_contract(self, contract: dict) -> None:
        (self.tmp / "contract.json").write_text(json.dumps(contract), encoding="utf-8")

    def assert_fails(self, reason: str) -> None:
        with self.assertRaises(SystemExit) as raised:
            check.main()
        self.assertIn(reason, str(raised.exception))

    def test_repository_passes(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(check.main(), 0)
        self.assertIn("OK: platform-security (security)", out.getvalue())

    def test_status_must_stay_scaffolded(self) -> None:
        contract = self.contract()
        contract["status"] = "active"
        self.write_contract(contract)
        self.assert_fails("must remain scaffolded")

    def test_missing_required_key_fails(self) -> None:
        contract = self.contract()
        del contract["data_owner"]
        self.write_contract(contract)
        self.assert_fails("missing keys: ['data_owner']")

    def test_current_implementation_must_be_the_control_plane(self) -> None:
        contract = self.contract()
        contract["current_implementation"]["repository"] = "platform-security"
        self.write_contract(contract)
        self.assert_fails("current_implementation.repository must be solo-empire")

    def test_invalid_repository_slug_fails(self) -> None:
        contract = self.contract()
        contract["repository"] = "security"
        self.write_contract(contract)
        self.assert_fails("repository has an invalid slug")

    def test_readme_needs_the_migration_gate(self) -> None:
        readme = self.tmp / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8").replace("## Migration gate", "## Later"),
            encoding="utf-8",
        )
        self.assert_fails("README.md is missing ## Migration gate")

    def test_scaffold_placeholder_fails(self) -> None:
        readme = self.tmp / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\n__TODO__\n", encoding="utf-8")
        self.assert_fails("scaffold placeholder remains")


if __name__ == "__main__":
    unittest.main()
