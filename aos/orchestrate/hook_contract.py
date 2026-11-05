"""Validate and plan hook dispatch; deliberately performs no tool execution.

This boundary does not grant authority or replace the central approval journal.
Registry configuration and required-hook inventory must come from trusted host
policy, never from the hook payload being validated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

POINTS = frozenset(
    {
        "discuss:pre",
        "discuss:post",
        "plan:pre",
        "plan:post",
        "execute:pre",
        "execute:wave:pre",
        "execute:wave:post",
        "execute:post",
        "verify:pre",
        "verify:post",
        "ship:pre",
        "ship:post",
    }
)


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Fragment(BoundaryModel):
    inline: str = Field(min_length=1, max_length=16000)


class Reference(BoundaryModel):
    skill: str | None = Field(default=None, min_length=1, max_length=128)
    agent: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def exactly_one(self) -> Reference:
        if (self.skill is None) == (self.agent is None):
            raise ValueError("exactly one skill or agent reference required")
        return self


class Check(BoundaryModel):
    query: str | None = Field(default=None, min_length=1, max_length=4000)
    predicate: str | None = Field(default=None, min_length=1, max_length=4000)
    agentVerdict: str | None = Field(default=None, min_length=1, max_length=4000)

    @model_validator(mode="after")
    def exactly_one(self) -> Check:
        if (
            sum(
                value is not None
                for value in (self.query, self.predicate, self.agentVerdict)
            )
            != 1
        ):
            raise ValueError("exactly one check type required")
        return self


class Contribution(BoundaryModel):
    id: str = Field(min_length=1, max_length=128)
    kind: Literal["contribution"]
    into: str = Field(min_length=1, max_length=128)
    fragment: Fragment


class Step(BoundaryModel):
    id: str = Field(min_length=1, max_length=128)
    kind: Literal["step"]
    ref: Reference


class GateHook(BoundaryModel):
    id: str = Field(min_length=1, max_length=128)
    kind: Literal["gate"]
    check: Check
    blocking: StrictBool
    onError: Literal["skip", "fail"]


Hook = Annotated[Contribution | Step | GateHook, Field(discriminator="kind")]


class Envelope(BoundaryModel):
    schema_version: Literal["1"]
    registry_revision: str = Field(min_length=1, max_length=128)
    point: str
    activeHooks: tuple[Hook, ...] = Field(default_factory=tuple, max_length=100)

    @field_validator("activeHooks", mode="before")
    @classmethod
    def freeze_wire_hooks(cls, value: Any) -> tuple[Any, ...]:
        """Snapshot a JSON-array hook collection before validating its entries."""
        if not isinstance(value, (list, tuple)):
            raise PydanticCustomError("hook_array_type", "activeHooks must be an array")
        return tuple(value)

    @model_validator(mode="after")
    def validate_identity(self) -> Envelope:
        if self.point not in POINTS:
            raise ValueError("unknown extension point")
        ids = [hook.id for hook in self.activeHooks]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate hook identity")
        return self


class Verdict(BoundaryModel):
    block: StrictBool
    message: str = Field(min_length=1, max_length=4000)


@dataclass(frozen=True)
class PlannedDispatch:
    hook_id: str
    kind: str
    target: str
    target_kind: Literal["role", "skill", "agent", "gate_check"]
    gate: GateHook | None = None
    content: str | None = None
    # Contributions are attributed data, never executable system instructions.
    authority: str = "data_only"


class HookBlocked(ValueError):
    """The host must stop the current step."""


def plan_dispatch(
    payload: Mapping[str, Any],
    *,
    expected_point: str,
    expected_revision: str,
    required_gate_ids: frozenset[str],
    allowed_skills: frozenset[str],
    allowed_agents: frozenset[str],
    allowed_roles: frozenset[str],
    trusted_gates: Mapping[str, GateHook],
) -> tuple[Envelope, tuple[PlannedDispatch, ...]]:
    """Validate a complete envelope before producing any non-executing plan.

    Schema v1 intentionally strengthens the supplied sketch with identity and
    trusted registry binding. Legacy envelopes need an explicit host migration.
    """
    envelope = Envelope.model_validate(dict(payload))
    if (
        envelope.point != expected_point
        or envelope.registry_revision != expected_revision
    ):
        raise HookBlocked("extension point or trusted registry revision mismatch")
    gates = {
        hook.id: hook for hook in envelope.activeHooks if isinstance(hook, GateHook)
    }
    if not required_gate_ids.issubset(gates):
        raise HookBlocked("required gate registration missing")
    for identity, gate in gates.items():
        if identity not in trusted_gates or gate != trusted_gates[identity]:
            raise HookBlocked("gate differs from trusted registry definition")
    for identity in required_gate_ids:
        gate = gates[identity]
        if not gate.blocking or gate.onError != "fail":
            raise HookBlocked("mandatory gates must block and fail closed")
    planned = []
    for hook in envelope.activeHooks:
        if isinstance(hook, Contribution):
            if hook.into not in allowed_roles:
                raise HookBlocked("unregistered contribution role")
            planned.append(
                PlannedDispatch(
                    hook.id, hook.kind, hook.into, "role", content=hook.fragment.inline
                )
            )
        elif isinstance(hook, Step):
            target = hook.ref.skill if hook.ref.skill is not None else hook.ref.agent
            allowed = allowed_skills if hook.ref.skill is not None else allowed_agents
            if target not in allowed:
                raise HookBlocked("unregistered dispatch target")
            assert target is not None
            target_kind: Literal["skill", "agent"] = (
                "skill" if hook.ref.skill is not None else "agent"
            )
            planned.append(PlannedDispatch(hook.id, hook.kind, target, target_kind))
        else:
            planned.append(
                PlannedDispatch(hook.id, hook.kind, hook.id, "gate_check", gate=hook)
            )
    return envelope, tuple(planned)


def evaluate_gate(
    gate: GateHook,
    result: Mapping[str, Any] | None,
    *,
    required: bool,
    check_error: bool = False,
) -> Verdict:
    """Validate one observed verdict; missing/unknown required results block.

    The caller obtains `required` from trusted inventory and must journal the
    verdict against exact run/action/revision before any side effect.
    """
    if required and (not gate.blocking or gate.onError != "fail"):
        raise HookBlocked("invalid mandatory gate policy")
    try:
        if check_error or result is None:
            raise ValueError("gate unavailable")
        verdict = Verdict.model_validate(dict(result))
    except (ValueError, TypeError) as exc:
        if required or gate.onError == "fail":
            raise HookBlocked("gate failed or verdict unavailable") from exc
        return Verdict(
            block=False, message="Advisory check unavailable; explicitly skipped"
        )
    if verdict.block and (required or gate.blocking):
        raise HookBlocked(verdict.message)
    return verdict
