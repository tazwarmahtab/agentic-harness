"""Typed intake and evidence contracts. Document content is untrusted data."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Scope = str


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Upload(Contract):
    filename: str = Field(min_length=1, max_length=160)
    content_b64: str = Field(min_length=1, max_length=7_000_000)


class Intake(Contract):
    venture: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    project: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    prospect: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=2000)
    documents: list[Upload] = Field(min_length=1, max_length=12)


class Passage(Contract):
    source_id: str
    page: int = Field(ge=1)
    text: str


class Fact(Contract):
    source_id: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=3, max_length=6000)
    topic: Literal["buyer", "bill", "roof", "commercial", "other"] = "other"


class Analysis(Contract):
    facts: list[Fact] = Field(min_length=1, max_length=80)


class Review(Contract):
    output_hash: str = Field(min_length=1, max_length=64)
    decision: Literal["approve", "reject", "defer"]


class DraftEdit(Contract):
    output_hash: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=10000)
