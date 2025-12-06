"""
Structured logging configuration for TriArchitect.

Provides consistent, structured logging with correlation IDs for request
tracing and configurable output formats (JSON or console).
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, List, Optional

import structlog
from rich.console import Console
from rich.logging import RichHandler


# Context variable for correlation ID tracking across async contexts
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """
    Get or generate a correlation ID for the current context.
    
    Returns:
        A string correlation ID. Generates a new UUID if none exists.
    """
    cid = correlation_id_var.get()
    if not cid:
        cid = str(uuid.uuid4())[:8]
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """
    Set the correlation ID for the current context.
    
    Args:
        cid: The correlation ID to set.
    """
    correlation_id_var.set(cid)


def add_correlation_id(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Structlog processor to add correlation ID to all log entries.
    
    Args:
        logger: The wrapped logger instance.
        method_name: The name of the logging method called.
        event_dict: The event dictionary being processed.
        
    Returns:
        The event dictionary with correlation_id added.
    """
    event_dict["correlation_id"] = get_correlation_id()
    return event_dict


def add_agent_context(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Structlog processor to add agent context if available.
    
    Args:
        logger: The wrapped logger instance.
        method_name: The name of the logging method called.
        event_dict: The event dictionary being processed.
        
    Returns:
        The event dictionary, possibly with agent context added.
    """
    # Agent name can be bound to the logger
    return event_dict


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "console",
) -> None:
    """
    Configure structured logging for the application.
    
    Sets up structlog with processors for correlation IDs, timestamps,
    and either JSON or rich console output.
    
    Args:
        log_level: The minimum log level to output (DEBUG, INFO, etc.).
        log_format: Output format - 'json' for structured JSON, 'console' for rich.
    """
    # Clear any existing handlers
    root = logging.getLogger()
    root.handlers.clear()
    
    # Configure standard library logging
    if log_format == "console":
        console = Console(stderr=True)
        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
    
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper()))
    
    # Configure structlog processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        add_correlation_id,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if log_format == "json":
        shared_processors.append(structlog.processors.format_exc_info)
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.rich_traceback,
        )
    
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure formatter for stdlib loggers
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler.setFormatter(formatter)


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name, typically the module __name__.
        **initial_context: Initial context to bind to the logger.
        
    Returns:
        A bound structlog logger with the given context.
        
    Example:
        >>> logger = get_logger(__name__, agent="archeologist")
        >>> logger.info("starting analysis", repo_path="/path/to/repo")
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger
