"""Legal Harness implementation for TAZ OS."""

from .harness import LegalHarness
from .agents import LegalAgent, ContractReviewer, ComplianceOfficer

__all__ = ["LegalHarness", "LegalAgent", "ContractReviewer", "ComplianceOfficer"]
