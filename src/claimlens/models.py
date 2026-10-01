from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class PrivacyMode(str, Enum):
    STRICT = "strict"
    VERIFICATION = "verification"
    CUSTOM = "custom"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    CONFLICT = "CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(frozen=True)
class PIIFinding:
    kind: str
    value: str
    start: int
    end: int
    risk: str = "high"


@dataclass
class Claim:
    candidate_id: str
    claim_id: str
    claim_type: str
    claim_text: str
    title: str = ""
    year: str = ""
    organization: str = ""
    journal: str = ""
    doi: str = ""
    patent_number: str = ""
    award_name: str = ""
    authors: str = ""
    verification_query: str = ""
    privacy_risk: str = "low"
    source_file: str = ""

    def row(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class Evidence:
    claim_id: str
    status: VerificationStatus = VerificationStatus.NEEDS_REVIEW
    source: str = ""
    evidence_url: str = ""
    checked_at: str = ""
    matching_fields: list[str] = field(default_factory=list)
    conflicting_fields: list[str] = field(default_factory=list)
    evidence_strength: str = ""
    notes: str = ""
