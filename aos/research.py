"""Governed research artifacts with provenance, confidence, and contradictions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ClaimStatus(str, Enum):
    VERIFIED = "verified"
    INCOMPLETE = "strong_but_incomplete"
    CONFLICTED = "conflicted"
    UNVERIFIED = "unverified"
    INFERENCE = "inference"


@dataclass(frozen=True)
class ResearchSource:
    source_id: str
    title: str
    uri: str
    publisher: str = ""
    published_at: str | None = None
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence_quality: float = 0.5

    def __post_init__(self) -> None:
        if not 0 <= self.evidence_quality <= 1:
            raise ValueError("evidence_quality must be between 0 and 1")


@dataclass
class ResearchClaim:
    claim_id: str
    text: str
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    confidence: float = 0.0
    source_ids: list[str] = field(default_factory=list)
    reasoning: str = ""
    last_checked_at: str = ""


@dataclass
class ResearchArtifact:
    topic: str
    sources: dict[str, ResearchSource] = field(default_factory=dict)
    claims: dict[str, ResearchClaim] = field(default_factory=dict)
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_source(self, source: ResearchSource) -> None:
        self.sources[source.source_id] = source

    def add_claim(self, claim: ResearchClaim) -> None:
        missing = [sid for sid in claim.source_ids if sid not in self.sources]
        if missing:
            raise ValueError(f"claim references unknown sources: {', '.join(missing)}")
        self.claims[claim.claim_id] = claim

    def verify_claim(self, claim_id: str, *, status: ClaimStatus, confidence: float,
                     reasoning: str, source_ids: list[str] | None = None) -> ResearchClaim:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        claim = self.claims[claim_id]
        ids = source_ids if source_ids is not None else claim.source_ids
        if any(sid not in self.sources for sid in ids):
            raise ValueError("claim references unknown source")
        claim.status = status
        claim.confidence = confidence
        claim.reasoning = reasoning
        claim.source_ids = ids
        claim.last_checked_at = datetime.now(timezone.utc).isoformat()
        return claim

    def add_contradiction(self, claim_ids: list[str], description: str) -> None:
        if len(claim_ids) < 2 or any(cid not in self.claims for cid in claim_ids):
            raise ValueError("contradiction requires at least two known claims")
        for cid in claim_ids:
            self.claims[cid].status = ClaimStatus.CONFLICTED
        self.contradictions.append({"claim_ids": claim_ids, "description": description})

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "created_at": self.created_at,
            "sources": {k: asdict(v) for k, v in self.sources.items()},
            "claims": {k: {**asdict(v), "status": v.status.value} for k, v in self.claims.items()},
            "contradictions": self.contradictions,
            "assumptions": self.assumptions,
        }
