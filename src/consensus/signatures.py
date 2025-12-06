"""
Agent signatures for consensus protocol.

Provides data structures for tracking agent approvals
and signatures during the consensus process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AgentSignature:
    """
    Signature from an agent for a migration proposal.
    
    Represents an agent's vote in the consensus process,
    including approval status, confidence, and feedback.
    
    Attributes:
        agent_id: Unique identifier for the signing agent.
        agent_name: Human-readable agent name.
        approval: Whether the agent approves the proposal.
        confidence: Agent's confidence in their decision (0.0-1.0).
        timestamp: When the signature was created.
        comments: Optional feedback or explanation.
        required_changes: Changes needed before approval (if rejecting).
    """
    agent_id: str
    agent_name: str
    approval: bool
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    comments: str = ""
    required_changes: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "approval": self.approval,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "comments": self.comments,
            "required_changes": self.required_changes,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSignature":
        """Create from dictionary."""
        return cls(
            agent_id=data["agent_id"],
            agent_name=data["agent_name"],
            approval=data["approval"],
            confidence=data.get("confidence", 0.5),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            comments=data.get("comments", ""),
            required_changes=data.get("required_changes", []),
        )


@dataclass 
class SignatureCollection:
    """
    Collection of signatures for a migration proposal.
    
    Tracks all agent signatures and provides utilities
    for checking consensus status.
    
    Attributes:
        proposal_id: ID of the proposal being signed.
        signatures: List of agent signatures.
        created_at: When collection was created.
    """
    proposal_id: str
    signatures: list[AgentSignature] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_signature(self, signature: AgentSignature) -> None:
        """Add a signature, replacing any existing from same agent."""
        # Remove existing signature from this agent
        self.signatures = [
            s for s in self.signatures 
            if s.agent_id != signature.agent_id
        ]
        self.signatures.append(signature)
    
    def get_approval_count(self) -> int:
        """Get number of approving signatures."""
        return sum(1 for s in self.signatures if s.approval)
    
    def get_rejection_count(self) -> int:
        """Get number of rejecting signatures."""
        return sum(1 for s in self.signatures if not s.approval)
    
    def get_average_confidence(self) -> float:
        """Get average confidence across all signatures."""
        if not self.signatures:
            return 0.0
        return sum(s.confidence for s in self.signatures) / len(self.signatures)
    
    def has_unanimous_approval(self) -> bool:
        """Check if all signatures are approvals."""
        return len(self.signatures) > 0 and all(s.approval for s in self.signatures)
    
    def get_required_changes(self) -> list[str]:
        """Get all required changes from rejecting signatures."""
        changes = []
        for sig in self.signatures:
            if not sig.approval:
                changes.extend(sig.required_changes)
        return changes
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "signatures": [s.to_dict() for s in self.signatures],
            "created_at": self.created_at.isoformat(),
            "approval_count": self.get_approval_count(),
            "rejection_count": self.get_rejection_count(),
            "average_confidence": self.get_average_confidence(),
        }
