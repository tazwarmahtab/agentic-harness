"""YAML manifest loader with JSON Schema validation.

Loads YAML manifests, validates against aos/platform/*.schema.json,
and returns typed Pydantic objects.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

from aos.hardening import sanitize_path
from aos.schemas.harness import Harness
from aos.schemas.agent import Agent
from aos.schemas.venture import Venture
from aos.schemas.memory import Memory
from aos.schemas.tool import ToolRegistry
from aos.schemas.evaluation import Evaluation
from aos.schemas.sop import SOP
from aos.schemas.policy_collection import PolicyCollection

logger = logging.getLogger(__name__)

PLATFORM_DIR = Path(__file__).parent / "platform"
SCHEMA_CACHE: dict[str, dict] = {}


def _load_schema(name: str) -> dict:
    """Load a JSON schema by name (without .schema.json suffix)."""
    if name not in SCHEMA_CACHE:
        schema_path = PLATFORM_DIR / f"{name}.schema.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")
        with open(schema_path) as f:
            SCHEMA_CACHE[name] = json.load(f)
    return SCHEMA_CACHE[name]


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return as dict."""
    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        raise ValueError(f"Empty YAML file: {path}")
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _validate_with_schema(data: dict, schema_name: str, path: Path) -> list[str]:
    """Validate data against a JSON schema. Returns list of error strings."""
    schema = _load_schema(schema_name)
    validator = Draft7Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        field_path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"{path}:{field_path}: {error.message}")
    return errors


def load_yaml_raw(path: Path) -> dict:
    """Load and validate a YAML manifest, returning raw dict."""
    data = _load_yaml(path)
    # Schema name is derived from the manifest content or filename
    # For now, we skip schema validation on load and do it in validator.py
    return data


def load_harness(path: Path) -> Harness:
    """Load a harness manifest and all its sub-manifests."""
    data = _load_yaml(path)
    harness_dir = path.parent

    # Load components if paths are specified
    components = data.get("components", {})
    if components:
        # Store component paths for the registry to load later
        data["_component_paths"] = {}
        for key, rel_path in components.items():
            sanitized = sanitize_path(str(rel_path))
            if sanitized is None:
                logger.warning("Rejected suspicious component path: %s", rel_path)
                continue
            component_path = harness_dir / sanitized
            if component_path.exists():
                data["_component_paths"][key] = str(component_path)

    return Harness(**data)


def load_agent(path: Path) -> Agent:
    """Load an agent manifest."""
    data = _load_yaml(path)
    return Agent(**data)


def load_venture(path: Path) -> Venture:
    """Load a venture manifest."""
    data = _load_yaml(path)
    return Venture(**data)


def load_memory(path: Path) -> Memory:
    """Load a memory manifest."""
    data = _load_yaml(path)
    return Memory(**data)


def load_tool_registry(path: Path) -> ToolRegistry:
    """Load a tool registry manifest."""
    data = _load_yaml(path)
    return ToolRegistry(**data)


def load_evaluation(path: Path) -> Evaluation:
    """Load an evaluation manifest."""
    data = _load_yaml(path)
    return Evaluation(**data)


def load_sop(path: Path) -> SOP:
    """Load an SOP manifest."""
    data = _load_yaml(path)
    return SOP(**data)


def load_policy_collection(path: Path) -> PolicyCollection:
    """Load a policy collection manifest."""
    data = _load_yaml(path)
    return PolicyCollection(**data)


# Schema name mapping for validation
SCHEMA_MAP: dict[str, str] = {
    "harness": "harness",
    "agent": "agent",
    "venture": "venture",
    "memory": "memory",
    "tool": "tool",
    "evaluation": "evaluation",
    "sop": "sop",
    "policy-collection": "policy-collection",
    "identity": "identity",
    "policy": "policy",
}


def detect_manifest_type(data: dict) -> str | None:
    """Detect manifest type from content."""
    manifest_id = data.get("id", "")
    if manifest_id.startswith("HAR-"):
        return "harness"
    if manifest_id.startswith("AGT-"):
        return "agent"
    if manifest_id.startswith("VEN-"):
        return "venture"
    if manifest_id.startswith("MEM-"):
        return "memory"
    if manifest_id.startswith("TOL-"):
        return "tool"
    if manifest_id.startswith("EVAL-"):
        return "evaluation"
    if manifest_id.startswith("SOP-"):
        return "sop"
    if manifest_id.startswith("POL-"):
        # Could be policy or policy_collection
        if "rules" in data and isinstance(data.get("rules"), list):
            return "policy-collection"
        return "policy"
    return None
