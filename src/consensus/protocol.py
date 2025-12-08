"""
Cyclic Consensus Protocol implementation.

Implements the proposal → verify → sign consensus loop that
ensures all three agents agree on migration proposals before
they are applied.

Mathematical Definition:
    Stopping Condition: Score ≥ θ AND All Signatures Present
    where θ is the configurable consensus threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable

from src.consensus.signatures import AgentSignature, SignatureCollection
from src.shared.config import get_settings
from src.shared.logger import get_logger
from src.tmg.models import MigrationProposal

logger = get_logger(__name__, component="consensus")


class ConsensusStatus(Enum):
    """Status of a consensus round."""
    PENDING = auto()
    IN_PROGRESS = auto()
    APPROVED = auto()
    REJECTED = auto()
    FAILED = auto()
    NEEDS_REVISION = auto()


@dataclass
class ConsensusResult:
    """
    Result of the consensus protocol.
    
    Attributes:
        proposal: The proposal that was evaluated.
        status: Final consensus status.
        iterations: Number of rounds taken.
        final_score: Final consensus score.
        signatures: All collected signatures.
        feedback: Aggregated feedback for revisions.
        applied: Whether the proposal was applied.
    """
    proposal: MigrationProposal
    status: ConsensusStatus = ConsensusStatus.PENDING
    iterations: int = 0
    final_score: float = 0.0
    signatures: SignatureCollection | None = None
    feedback: list[str] = field(default_factory=list)
    applied: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "proposal_id": self.proposal.node_id,
            "status": self.status.name,
            "iterations": self.iterations,
            "final_score": self.final_score,
            "signatures": self.signatures.to_dict() if self.signatures else None,
            "feedback": self.feedback,
            "applied": self.applied,
        }


class ConsensusProtocol:
    """
    Cyclic Consensus Protocol for multi-agent agreement.
    
    Implements the Algorithm 1 from the paper:
    1. Architect proposes a migration
    2. Archeologist verifies semantic preservation
    3. Validator runs tests and confirms
    4. All agents sign or request revisions
    5. Repeat until threshold reached or max iterations
    
    Attributes:
        threshold: Minimum score for consensus (default: 0.85).
        max_iterations: Maximum rounds before fallback (default: 3).
    
    Example:
        >>> protocol = ConsensusProtocol()
        >>> result = protocol.run(proposal, agents)
        >>> if result.status == ConsensusStatus.APPROVED:
        ...     print("Proposal approved!")
    """
    
    def __init__(
        self,
        threshold: float | None = None,
        max_iterations: int | None = None,
    ) -> None:
        """
        Initialize the consensus protocol.
        
        Args:
            threshold: Minimum consensus score (0.0-1.0).
            max_iterations: Maximum consensus rounds.
        """
        settings = get_settings()
        self.threshold = threshold or settings.consensus_threshold
        self.max_iterations = max_iterations or settings.consensus_max_iterations
        self._results: list[ConsensusResult] = []
        
        logger.info(
            "consensus_protocol_initialized",
            threshold=self.threshold,
            max_iterations=self.max_iterations,
        )
    
    def run(
        self,
        proposal: MigrationProposal,
        verify_fn: Callable[[MigrationProposal], AgentSignature] | None = None,
        sign_fns: dict[str, Callable[[MigrationProposal], AgentSignature]] | None = None,
        on_revision: Callable[[MigrationProposal, list[str]], MigrationProposal] | None = None,
    ) -> ConsensusResult:
        """
        Run the consensus protocol for a proposal.
        
        Args:
            proposal: The migration proposal to evaluate.
            verify_fn: Function to verify the proposal (Validator).
            sign_fns: Dict of agent_id -> signing function.
            on_revision: Callback to revise proposal based on feedback.
            
        Returns:
            ConsensusResult with final status and feedback.
        """
        result = ConsensusResult(
            proposal=proposal,
            status=ConsensusStatus.IN_PROGRESS,
            signatures=SignatureCollection(proposal_id=proposal.node_id),
        )
        
        logger.info(
            "consensus_started",
            proposal_id=proposal.node_id,
            initial_confidence=proposal.confidence,
        )
        
        current_proposal = proposal
        
        for iteration in range(1, self.max_iterations + 1):
            result.iterations = iteration
            
            logger.info(
                "consensus_iteration",
                iteration=iteration,
                proposal_id=current_proposal.node_id,
            )
            
            # Phase 1: Verify (typically Validator)
            if verify_fn:
                verification = verify_fn(current_proposal)
                result.signatures.add_signature(verification)
                
                if not verification.approval:
                    result.feedback.extend(verification.required_changes)
            
            # Phase 2: Collect signatures from all agents
            if sign_fns:
                for agent_id, sign_fn in sign_fns.items():
                    signature = sign_fn(current_proposal)
                    result.signatures.add_signature(signature)
                    
                    if not signature.approval:
                        result.feedback.extend(signature.required_changes)
            
            # Calculate consensus score
            result.final_score = self._calculate_score(result.signatures)
            
            logger.info(
                "consensus_score",
                iteration=iteration,
                score=result.final_score,
                approvals=result.signatures.get_approval_count(),
                rejections=result.signatures.get_rejection_count(),
            )
            
            # Check stopping condition
            if self._check_stopping_condition(result):
                result.status = ConsensusStatus.APPROVED
                logger.info(
                    "consensus_reached",
                    iterations=iteration,
                    final_score=result.final_score,
                )
                break
            
            # Check for hard rejection
            if result.signatures.get_rejection_count() > len(sign_fns or {}) // 2:
                result.status = ConsensusStatus.REJECTED
                logger.warning(
                    "consensus_rejected",
                    rejections=result.signatures.get_rejection_count(),
                )
                break
            
            # Attempt revision if not last iteration
            if iteration < self.max_iterations and on_revision and result.feedback:
                logger.info(
                    "attempting_revision",
                    feedback_count=len(result.feedback),
                )
                current_proposal = on_revision(current_proposal, result.feedback)
                result.proposal = current_proposal
                result.feedback.clear()
        
        # Final status if loop exhausted
        if result.status == ConsensusStatus.IN_PROGRESS:
            if result.final_score >= self.threshold * 0.9:  # Close to threshold
                result.status = ConsensusStatus.NEEDS_REVISION
            else:
                result.status = ConsensusStatus.FAILED
        
        self._results.append(result)
        
        logger.info(
            "consensus_complete",
            status=result.status.name,
            iterations=result.iterations,
            final_score=result.final_score,
        )
        
        return result
    
    def run_simple(
        self,
        proposal: MigrationProposal,
        agent_votes: list[tuple[str, str, bool, float]],
    ) -> ConsensusResult:
        """
        Run simplified consensus with pre-computed votes.
        
        For testing and demo purposes when full agents aren't available.
        
        Args:
            proposal: The proposal to evaluate.
            agent_votes: List of (agent_id, agent_name, approval, confidence).
            
        Returns:
            ConsensusResult based on votes.
        """
        result = ConsensusResult(
            proposal=proposal,
            status=ConsensusStatus.IN_PROGRESS,
            iterations=1,
            signatures=SignatureCollection(proposal_id=proposal.node_id),
        )
        
        for agent_id, agent_name, approval, confidence in agent_votes:
            signature = AgentSignature(
                agent_id=agent_id,
                agent_name=agent_name,
                approval=approval,
                confidence=confidence,
            )
            result.signatures.add_signature(signature)
        
        result.final_score = self._calculate_score(result.signatures)
        
        if self._check_stopping_condition(result):
            result.status = ConsensusStatus.APPROVED
        elif result.signatures.get_rejection_count() > len(agent_votes) // 2:
            result.status = ConsensusStatus.REJECTED
        else:
            result.status = ConsensusStatus.NEEDS_REVISION
        
        return result
    
    def _calculate_score(self, signatures: SignatureCollection) -> float:
        """
        Calculate consensus score from signatures.
        
        Score formula:
        - Base: approval_rate * average_confidence
        - Bonus: +0.1 for unanimous approval
        - Penalty: -0.2 per rejection
        
        Args:
            signatures: The signature collection.
            
        Returns:
            Consensus score (0.0-1.0).
        """
        if not signatures.signatures:
            return 0.0
        
        total = len(signatures.signatures)
        approvals = signatures.get_approval_count()
        avg_confidence = signatures.get_average_confidence()
        
        # Base score
        approval_rate = approvals / total
        score = approval_rate * avg_confidence
        
        # Unanimous bonus
        if signatures.has_unanimous_approval():
            score += 0.1
        
        # Rejection penalty
        rejections = signatures.get_rejection_count()
        score -= 0.2 * (rejections / total)
        
        return max(0.0, min(1.0, score))
    
    def _check_stopping_condition(self, result: ConsensusResult) -> bool:
        """
        Check if stopping condition is met.
        
        Condition: Score ≥ θ AND All Signatures Present AND No Hard Rejections
        
        Args:
            result: Current consensus result.
            
        Returns:
            True if consensus is reached.
        """
        if not result.signatures:
            return False
        
        # Score must meet threshold
        if result.final_score < self.threshold:
            return False
        
        # Must have unanimous approval or supermajority
        total = len(result.signatures.signatures)
        approvals = result.signatures.get_approval_count()
        
        # Require at least 2/3 approval
        if approvals < (2 * total / 3):
            return False
        
        return True
    
    def get_statistics(self) -> dict[str, Any]:
        """Get statistics from all consensus runs."""
        if not self._results:
            return {"total_runs": 0}
        
        approved = sum(1 for r in self._results if r.status == ConsensusStatus.APPROVED)
        rejected = sum(1 for r in self._results if r.status == ConsensusStatus.REJECTED)
        failed = sum(1 for r in self._results if r.status == ConsensusStatus.FAILED)
        
        avg_iterations = sum(r.iterations for r in self._results) / len(self._results)
        avg_score = sum(r.final_score for r in self._results) / len(self._results)
        
        return {
            "total_runs": len(self._results),
            "approved": approved,
            "rejected": rejected,
            "failed": failed,
            "average_iterations": round(avg_iterations, 2),
            "average_score": round(avg_score, 3),
            "approval_rate": round(approved / len(self._results), 3),
        }
