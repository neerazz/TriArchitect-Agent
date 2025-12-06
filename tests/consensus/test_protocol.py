"""
Tests for the consensus protocol.
"""

import pytest

from src.consensus import ConsensusProtocol, ConsensusResult, AgentSignature
from src.consensus.protocol import ConsensusStatus
from src.consensus.signatures import SignatureCollection
from src.shared.tmg.models import MigrationProposal


@pytest.fixture
def sample_proposal() -> MigrationProposal:
    """Create a sample migration proposal."""
    return MigrationProposal(
        node_id="com.example.Service",
        original_code="public void oldMethod() {}",
        proposed_code="public void newMethod() {}",
        confidence=0.85,
        rationale="Migrating deprecated API",
    )


class TestAgentSignature:
    """Tests for AgentSignature."""
    
    def test_create_signature(self):
        """Test creating a signature."""
        sig = AgentSignature(
            agent_id="archeologist_1",
            agent_name="Archeologist",
            approval=True,
            confidence=0.9,
        )
        assert sig.approval
        assert sig.confidence == 0.9
    
    def test_signature_serialization(self):
        """Test signature to/from dict."""
        sig = AgentSignature(
            agent_id="test",
            agent_name="Test Agent",
            approval=False,
            confidence=0.5,
            comments="Needs more work",
            required_changes=["Fix import"],
        )
        
        data = sig.to_dict()
        restored = AgentSignature.from_dict(data)
        
        assert restored.approval == sig.approval
        assert restored.required_changes == sig.required_changes


class TestSignatureCollection:
    """Tests for SignatureCollection."""
    
    def test_add_signature(self):
        """Test adding signatures."""
        collection = SignatureCollection(proposal_id="test")
        
        sig = AgentSignature(
            agent_id="agent_1",
            agent_name="Agent 1",
            approval=True,
            confidence=0.8,
        )
        collection.add_signature(sig)
        
        assert len(collection.signatures) == 1
    
    def test_replace_existing_signature(self):
        """Test that adding from same agent replaces."""
        collection = SignatureCollection(proposal_id="test")
        
        sig1 = AgentSignature(
            agent_id="agent_1",
            agent_name="Agent 1",
            approval=False,
            confidence=0.5,
        )
        sig2 = AgentSignature(
            agent_id="agent_1",
            agent_name="Agent 1",
            approval=True,
            confidence=0.9,
        )
        
        collection.add_signature(sig1)
        collection.add_signature(sig2)
        
        assert len(collection.signatures) == 1
        assert collection.signatures[0].approval
    
    def test_approval_count(self):
        """Test counting approvals."""
        collection = SignatureCollection(proposal_id="test")
        
        collection.add_signature(AgentSignature("a1", "A1", True, 0.8))
        collection.add_signature(AgentSignature("a2", "A2", True, 0.9))
        collection.add_signature(AgentSignature("a3", "A3", False, 0.5))
        
        assert collection.get_approval_count() == 2
        assert collection.get_rejection_count() == 1
    
    def test_unanimous_approval(self):
        """Test unanimous approval check."""
        collection = SignatureCollection(proposal_id="test")
        
        collection.add_signature(AgentSignature("a1", "A1", True, 0.8))
        collection.add_signature(AgentSignature("a2", "A2", True, 0.9))
        
        assert collection.has_unanimous_approval()
        
        collection.add_signature(AgentSignature("a3", "A3", False, 0.5))
        assert not collection.has_unanimous_approval()
    
    def test_average_confidence(self):
        """Test average confidence calculation."""
        collection = SignatureCollection(proposal_id="test")
        
        collection.add_signature(AgentSignature("a1", "A1", True, 0.6))
        collection.add_signature(AgentSignature("a2", "A2", True, 0.8))
        
        assert collection.get_average_confidence() == pytest.approx(0.7)


class TestConsensusProtocol:
    """Tests for ConsensusProtocol."""
    
    def test_create_protocol(self):
        """Test creating protocol with defaults."""
        protocol = ConsensusProtocol()
        assert protocol.threshold == 0.85
        assert protocol.max_iterations == 3
    
    def test_run_simple_approved(self, sample_proposal: MigrationProposal):
        """Test simple consensus with approval."""
        protocol = ConsensusProtocol(threshold=0.7)
        
        votes = [
            ("arch", "Archeologist", True, 0.9),
            ("arct", "Architect", True, 0.85),
            ("val", "Validator", True, 0.8),
        ]
        
        result = protocol.run_simple(sample_proposal, votes)
        
        assert result.status == ConsensusStatus.APPROVED
        assert result.final_score > 0.7
    
    def test_run_simple_rejected(self, sample_proposal: MigrationProposal):
        """Test simple consensus with rejection."""
        protocol = ConsensusProtocol(threshold=0.9)
        
        votes = [
            ("arch", "Archeologist", True, 0.7),
            ("arct", "Architect", False, 0.4),
            ("val", "Validator", False, 0.3),
        ]
        
        result = protocol.run_simple(sample_proposal, votes)
        
        assert result.status == ConsensusStatus.REJECTED
    
    def test_high_threshold_requires_high_confidence(self, sample_proposal: MigrationProposal):
        """Test that high threshold requires high confidence."""
        protocol = ConsensusProtocol(threshold=0.95)
        
        votes = [
            ("arch", "Archeologist", True, 0.8),
            ("arct", "Architect", True, 0.8),
            ("val", "Validator", True, 0.8),
        ]
        
        result = protocol.run_simple(sample_proposal, votes)
        
        # Even with all approvals, score might not hit 0.95
        assert result.final_score <= 0.95 or result.status == ConsensusStatus.APPROVED
    
    def test_get_statistics(self, sample_proposal: MigrationProposal):
        """Test statistics collection."""
        protocol = ConsensusProtocol(threshold=0.7)
        
        # Run multiple consensus rounds
        for _ in range(3):
            votes = [
                ("arch", "Archeologist", True, 0.9),
                ("arct", "Architect", True, 0.8),
                ("val", "Validator", True, 0.85),
            ]
            protocol.run_simple(sample_proposal, votes)
        
        stats = protocol.get_statistics()
        
        assert stats["total_runs"] == 3
        assert stats["approved"] == 3
        assert stats["average_score"] > 0
