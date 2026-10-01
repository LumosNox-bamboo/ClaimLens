from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from claimlens.models import Claim, Evidence


@dataclass(frozen=True)
class OutboundField:
    name: str
    value: str
    reason: str


class VerificationProvider(ABC):
    """Network-capable providers must declare outbound data before execution."""

    name: str

    @abstractmethod
    def outbound_fields(self, claim: Claim) -> list[OutboundField]: ...

    @abstractmethod
    def verify(self, claim: Claim) -> Evidence: ...
