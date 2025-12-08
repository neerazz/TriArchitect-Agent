"""
Base agent class for TriArchitect agents.

Provides common functionality for all agents including logging,
TMG access, and execution metrics collection.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

from src.shared.logger import get_logger
from src.tmg import TypedMigrationGraph

T = TypeVar("T")


@dataclass
class AgentResult(Generic[T]):
    """
    Result container for agent operations.
    
    Provides a standardized way to return results from agent
    processing, including success/failure status and metrics.
    
    Attributes:
        success: Whether the operation succeeded.
        data: The result data (type varies by agent).
        error: Error message if operation failed.
        execution_time_ms: Time taken in milliseconds.
        tokens_used: Number of LLM tokens used (if applicable).
        metadata: Additional operation metadata.
    """
    success: bool
    data: T | None = None
    error: str | None = None
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate result state."""
        if not self.success and not self.error:
            self.error = "Unknown error"


class BaseAgent(ABC):
    """
    Abstract base class for all TriArchitect agents.
    
    Provides common functionality including:
    - TMG access and manipulation
    - Structured logging with agent context
    - Execution metrics collection
    - Error handling and reporting
    
    Subclasses must implement the `process` method to define
    their specific behavior.
    
    Attributes:
        name: Human-readable agent name.
        tmg: Reference to the shared Typed Migration Graph.
        logger: Configured logger with agent context.
    
    Example:
        >>> class MyAgent(BaseAgent):
        ...     def process(self, **kwargs):
        ...         self.logger.info("processing")
        ...         return AgentResult(success=True, data="done")
    """
    
    def __init__(
        self,
        name: str,
        tmg: TypedMigrationGraph | None = None,
    ) -> None:
        """
        Initialize the base agent.
        
        Args:
            name: Human-readable name for this agent.
            tmg: Optional TMG reference (can be set later).
        """
        self.name = name
        self._tmg = tmg
        self.logger = get_logger(__name__, agent=name)
        self._created_at = datetime.now()
        self._total_executions: int = 0
        self._total_time_ms: float = 0.0
        
        self.logger.info("agent_initialized", agent_name=name)
    
    @property
    def tmg(self) -> TypedMigrationGraph:
        """
        Get the TMG instance.
        
        Raises:
            ValueError: If TMG is not set.
        """
        if self._tmg is None:
            raise ValueError(f"TMG not set for agent {self.name}")
        return self._tmg
    
    @tmg.setter
    def tmg(self, value: TypedMigrationGraph) -> None:
        """Set the TMG instance."""
        self._tmg = value
        self.logger.debug("tmg_set", tmg_name=value.name)
    
    @abstractmethod
    def process(self, **kwargs: Any) -> AgentResult[Any]:
        """
        Execute the agent's main processing logic.
        
        This method must be implemented by subclasses to define
        the specific behavior of each agent type.
        
        Args:
            **kwargs: Agent-specific arguments.
            
        Returns:
            AgentResult containing the operation outcome.
        """
        pass
    
    def execute(self, **kwargs: Any) -> AgentResult[Any]:
        """
        Execute the agent with timing and error handling.
        
        Wraps the `process` method with:
        - Execution timing
        - Exception handling
        - Metrics collection
        
        Args:
            **kwargs: Arguments passed to process().
            
        Returns:
            AgentResult from process() or error result on exception.
        """
        start_time = time.perf_counter()
        self._total_executions += 1
        
        self.logger.info(
            "agent_execution_start",
            execution_number=self._total_executions,
        )
        
        try:
            result = self.process(**kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            result.execution_time_ms = elapsed_ms
            self._total_time_ms += elapsed_ms
            
            self.logger.info(
                "agent_execution_complete",
                success=result.success,
                execution_time_ms=round(elapsed_ms, 2),
                tokens_used=result.tokens_used,
            )
            
            return result
            
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._total_time_ms += elapsed_ms
            
            self.logger.exception(
                "agent_execution_error",
                error=str(e),
                execution_time_ms=round(elapsed_ms, 2),
            )
            
            return AgentResult(
                success=False,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )
    
    def get_metrics(self) -> dict[str, Any]:
        """
        Get execution metrics for this agent.
        
        Returns:
            Dictionary with execution statistics.
        """
        return {
            "agent_name": self.name,
            "total_executions": self._total_executions,
            "total_time_ms": round(self._total_time_ms, 2),
            "average_time_ms": round(
                self._total_time_ms / self._total_executions, 2
            ) if self._total_executions > 0 else 0,
            "created_at": self._created_at.isoformat(),
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, executions={self._total_executions})"
