#!/usr/bin/env python3
"""Offline validators for the BOO-163 security policy contracts.

Standard library only. Implements the JSON Schema subset used by
contracts/security/*.schema.json plus the semantic rules JSON Schema cannot
express: secret references are reference-only (no secret-looking literal),
the permission matrix is deny-by-default and internally consistent, audit is
append-only, and audit metadata follows the privacy-class policy.

This module never resolves, reads or prints a secret value.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "contracts" / "security"
SCHEMAS = {
    "tenant": "tenant.schema.json",
    "permission": "permission.schema.json",
    "secret-reference": "secret-reference.schema.json",
    "audit-event": "audit-event.schema.json",
    "privacy-class": "privacy-class.schema.json",
}
ANNOTATIONS = {"$schema", "$id", "$defs", "$comment", "title", "description", "default", "examples"}
SUPPORTED = {
    "type", "required", "properties", "additionalProperties", "enum", "const", "pattern",
    "minLength", "maxLength", "minimum", "items", "minItems", "uniqueItems", "$ref",
    "format", "minProperties", "maxProperties",
}
REDACTED = "[REDACTED]"


class ContractError(ValueError):
    """Raised when an instance violates a security contract."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


# ---------------------------------------------------------------- schema subset

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(name: str) -> dict[str, Any]:
    return load_json(CONTRACT_DIR / SCHEMAS[name])


def unsupported_keywords(schema: Any, path: str = "#") -> list[str]:
    """Keywords the subset validator would silently ignore (drift guard)."""
    found: list[str] = []
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key.startswith("x-") or key in ANNOTATIONS:
                if key == "$defs":
                    for name, sub in value.items():
                        found += unsupported_keywords(sub, f"{path}/$defs/{name}")
                continue
            if key not in SUPPORTED:
                found.append(f"{path}/{key}")
            elif key == "properties":
                for name, sub in value.items():
                    found += unsupported_keywords(sub, f"{path}/properties/{name}")
            elif key in {"items", "additionalProperties"} and isinstance(value, dict):
                found += unsupported_keywords(value, f"{path}/{key}")
    return found


_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "integer": int, "number": (int, float), "null": type(None),
}


def _type_ok(value: Any, expected: str) -> bool:
    if expected in {"integer", "number"} and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[expected])


def _format_ok(value: str, fmt: str) -> bool:
    if fmt == "uuid":
        try:
            return str(UUID(value)) == value.lower()
        except ValueError:
            return False
    if fmt == "date-time":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})", value):
            return False
        try:
            datetime.fromisoformat(value)
        except ValueError:
            return False
        return True
    raise KeyError(f"unsupported format {fmt}")


def schema_errors(instance: Any, schema: dict[str, Any], root: dict[str, Any] | None = None,
                  path: str = "$") -> list[str]:
    root = root or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            return [f"{path}: unsupported $ref {ref}"]
        return schema_errors(instance, root["$defs"][ref.split("/")[-1]], root, path)
    errors: list[str] = []
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']}")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(instance, t) for t in types):
            return errors + [f"{path}: must be {schema['type']}"]
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: does not match {schema['pattern']}")
        if "format" in schema and not _format_ok(instance, schema["format"]):
            errors.append(f"{path}: not a valid {schema['format']}")
    if (
        isinstance(instance, (int, float))
        and not isinstance(instance, bool)
        and "minimum" in schema
        and instance < schema["minimum"]
    ):
        errors.append(f"{path}: below {schema['minimum']}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if schema.get("uniqueItems"):
            seen = [json.dumps(i, sort_keys=True) for i in instance]
            if len(seen) != len(set(seen)):
                errors.append(f"{path}: items are not unique")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(instance):
                errors += schema_errors(item, schema["items"], root, f"{path}[{index}]")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required field {key!r}")
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            errors.append(f"{path}: fewer than {schema['minProperties']} properties")
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            errors.append(f"{path}: more than {schema['maxProperties']} properties")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in props:
                errors += schema_errors(value, props[key], root, f"{path}.{key}")
            elif extra is False:
                errors.append(f"{path}: unexpected field {key!r}")
            elif isinstance(extra, dict):
                errors += schema_errors(value, extra, root, f"{path}.{key}")
    return errors


# ------------------------------------------------------------ secret detection

_SECRET_PREFIXES = (
    "sk_live_", "sk_test_", "rk_live_", "rk_test_", "whsec_", "sk-ant-", "sk-proj-",
    "ghp_", "gho_", "ghs_", "ghu_", "github_pat_", "glpat-", "xoxb-", "xoxp-", "xoxa-",
    "AKIA", "ASIA", "AIza", "ya29.",
)
_PEM = re.compile(r"-----BEGIN")
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}")
_URL_CREDENTIALS = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE)
_BEARER = re.compile(r"\bbearer\s+\S{8,}", re.IGNORECASE)
_HEX = re.compile(r"[0-9a-fA-F]{32,}")


def _entropy(token: str) -> float:
    counts = {c: token.count(c) for c in set(token)}
    return -sum(n / len(token) * math.log2(n / len(token)) for n in counts.values())


def is_secret_like(value: str, *, allow_hex: bool = False) -> bool:
    """True when a string looks like a literal credential rather than a reference.

    allow_hex skips the long-hex rule for identifier fields whose schema permits
    hex ids (e.g. a 32-hex W3C trace id as request_id); all other rules still apply."""
    if not isinstance(value, str) or not value:
        return False
    if _PEM.search(value) or _JWT.search(value) or _URL_CREDENTIALS.search(value) or _BEARER.search(value):
        return True
    for token in re.split(r"[\s/#:=,;\"']+", value):
        if any(token.startswith(prefix) for prefix in _SECRET_PREFIXES) and len(token) >= 12:
            return True
        if not allow_hex and _HEX.fullmatch(token):
            return True
        if len(token) >= 24:
            classes = sum(bool(re.search(p, token)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]"))
            if classes >= 3 and _entropy(token) >= 3.5:
                return True
    return False


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


# ---------------------------------------------------------------- validators

def secret_reference_errors(ref: Any) -> list[str]:
    errors = schema_errors(ref, load_schema("secret-reference"))
    if not isinstance(ref, dict):
        return errors
    target = ref.get("ref")
    if isinstance(target, str):
        scheme = target.split("://", 1)[0]
        if "provider" in ref and scheme != ref["provider"]:
            errors.append("$.ref: scheme must equal provider")
        if ".." in target:
            errors.append("$.ref: path traversal is not allowed")
        if scheme == "env" and "://" in target:
            name = target.split("://", 1)[1].split("#", 1)[0]
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", name):
                errors.append("$.ref: env reference must name an UPPER_SNAKE variable")
    for text in _strings(ref):
        if is_secret_like(text):
            errors.append("secret reference contains a secret-looking literal; store a provider://path#version reference only")
            break
    return errors


def tenant_errors(tenant: Any) -> list[str]:
    return schema_errors(tenant, load_schema("tenant"))


def privacy_policy_errors(policy: Any) -> list[str]:
    errors = schema_errors(policy, load_schema("privacy-class"))
    if errors:
        return errors
    classes = policy["classes"]
    ids = [c["id"] for c in classes]
    if sorted(ids) != sorted(set(ids)) or set(ids) != {"public", "internal", "confidential", "restricted", "secret"}:
        errors.append("privacy classes must list each class exactly once")
    ranks = [c["rank"] for c in classes]
    if ranks != sorted(set(ranks)):
        errors.append("privacy classes must be listed in strictly increasing rank")
    order = {"allow": 0, "redact": 1, "deny": 2}
    for field in ("log_policy", "audit_metadata"):
        levels = [order[c[field]] for c in classes]
        if levels != sorted(levels):
            errors.append(f"{field} must not loosen as rank increases")
    by_id = {c["id"]: c for c in classes}
    secret = by_id.get("secret", {})
    if secret.get("storage") != "reference_only" or secret.get("log_policy") != "deny" or secret.get("audit_metadata") != "deny":
        errors.append("secret class must be reference_only and denied in logs and audit metadata")
    return errors


def permission_policy_errors(policy: Any) -> list[str]:
    errors = schema_errors(policy, load_schema("permission"))
    if errors:
        return errors
    roles = {r["id"]: r for r in policy["roles"]}
    actions = {a["id"]: a for a in policy["actions"]}
    if len(roles) != len(policy["roles"]):
        errors.append("duplicate role id")
    if len(actions) != len(policy["actions"]):
        errors.append("duplicate action id")
    matrix = policy["matrix"]
    if set(matrix) != set(roles):
        errors.append(f"matrix roles {sorted(matrix)} must equal declared roles {sorted(roles)}")
    for action_id in actions:
        if action_id.startswith("audit:") and action_id not in {"audit:read", "audit:append"}:
            errors.append(f"{action_id}: audit is append-only; only audit:read and audit:append may exist")
    for role_id, granted in matrix.items():
        for action_id in granted:
            if action_id not in actions:
                errors.append(f"matrix.{role_id}: unknown action {action_id}")
        role = roles.get(role_id)
        if role is None:
            continue
        service_only = role["principal_types"] == ["service"]
        for action_id in ("secret_reference:resolve", "audit:append"):
            if action_id in granted and not service_only:
                errors.append(f"matrix.{role_id}: {action_id} is restricted to service-only roles")
    return errors


def authorize(policy: dict[str, Any], role: str, action: str) -> bool:
    """Deny-by-default decision from the role -> action matrix."""
    if policy.get("default") != "deny":
        raise ContractError(["permission policy must be deny-by-default"])
    return action in policy.get("matrix", {}).get(role, [])


def audit_event_errors(event: Any, privacy_policy: dict[str, Any] | None = None) -> list[str]:
    errors = schema_errors(event, load_schema("audit-event"))
    if not isinstance(event, dict):
        return errors
    # prev_hash is a chain hash; request_id, idempotency_key and target.id are
    # schema-valid identifiers that may be hex (trace ids, content hashes).
    id_fields = {"request_id", "idempotency_key"}
    scanned = {k: v for k, v in event.items() if k not in id_fields | {"prev_hash", "target"}}
    ids = [event.get(k) for k in id_fields]
    target = event.get("target")
    if isinstance(target, dict):
        scanned["target"] = {k: v for k, v in target.items() if k != "id"}
        ids.append(target.get("id"))
    if any(is_secret_like(t) for t in _strings(scanned)) or any(
        isinstance(t, str) and is_secret_like(t, allow_hex=True) for t in ids
    ):
        errors.append("audit event contains a secret-looking literal")
    if privacy_policy is not None and event.get("metadata"):
        rules = {c["id"]: c for c in privacy_policy["classes"]}
        rule = rules.get(event.get("privacy_class"), {})
        if rule.get("audit_metadata") == "deny":
            errors.append(f"privacy class {event.get('privacy_class')} forbids audit metadata")
        elif rule.get("audit_metadata") == "redact" and any(v != REDACTED for v in event["metadata"].values()):
            errors.append(f"privacy class {event.get('privacy_class')} requires redacted audit metadata")
    return errors


def redact_audit_metadata(event: dict[str, Any], privacy_policy: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the event whose metadata follows the privacy policy."""
    rules = {c["id"]: c for c in privacy_policy["classes"]}
    if event.get("privacy_class") not in rules:
        raise ContractError([f"$.privacy_class: unknown privacy class {event.get('privacy_class')!r}"])
    mode = rules[event["privacy_class"]]["audit_metadata"]
    copy = json.loads(json.dumps(event))
    if "metadata" in copy:
        if mode == "deny":
            del copy["metadata"]
        elif mode == "redact":
            copy["metadata"] = {k: REDACTED for k in copy["metadata"]}
    return copy


def event_hash(event: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class AuditLog:
    """In-memory append-only audit log with a hash chain. No update or delete exists."""

    def __init__(self, privacy_policy: dict[str, Any]):
        self._privacy = privacy_policy
        self._events: list[dict[str, Any]] = []
        self._keys: dict[tuple[str, str], str] = {}

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        # Validate the event's shape before redaction so a missing or unknown
        # privacy_class (or any schema violation) raises ContractError, never KeyError.
        candidate = {k: v for k, v in event.items() if k != "prev_hash"} if isinstance(event, dict) else event
        shape_errors = schema_errors(candidate, load_schema("audit-event"))
        if shape_errors:
            raise ContractError(shape_errors)
        event = redact_audit_metadata(event, self._privacy)
        event.pop("prev_hash", None)
        if self._events:
            event["prev_hash"] = event_hash(self._events[-1])
        errors = audit_event_errors(event, self._privacy)
        if errors:
            raise ContractError(errors)
        key = event.get("idempotency_key")
        if key is not None:
            seen = self._keys.get((event["tenant_id"], key))
            if seen is not None:  # duplicate delivery returns the original event
                return json.loads(seen)
        if any(e["event_id"] == event["event_id"] for e in self._events):
            raise ContractError(["event_id already appended"])
        frozen = json.dumps(event, sort_keys=True)
        self._events.append(json.loads(frozen))
        if key is not None:
            self._keys[(event["tenant_id"], key)] = frozen
        return json.loads(frozen)

    def events(self, tenant_id: str) -> list[dict[str, Any]]:
        return [json.loads(json.dumps(e)) for e in self._events if e["tenant_id"] == tenant_id]

    def verify_chain(self) -> bool:
        return all(
            self._events[i].get("prev_hash") == event_hash(self._events[i - 1])
            for i in range(1, len(self._events))
        )


def check_all() -> list[str]:
    """Validate every shipped contract document; used by scripts/check.sh via tests."""
    errors: list[str] = []
    for name in SCHEMAS:
        errors += [f"{name}: unsupported keyword {k}" for k in unsupported_keywords(load_schema(name))]
    errors += [f"permission-matrix: {e}" for e in permission_policy_errors(load_json(CONTRACT_DIR / "permission-matrix.json"))]
    errors += [f"privacy-classes: {e}" for e in privacy_policy_errors(load_json(CONTRACT_DIR / "privacy-classes.json"))]
    return errors


if __name__ == "__main__":
    problems = check_all()
    if problems:
        raise SystemExit("FAIL: " + "; ".join(problems))
    print("OK: security policy contracts")
