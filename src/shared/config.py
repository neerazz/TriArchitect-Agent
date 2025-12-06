"""
Configuration management for TriArchitect.

Provides centralized settings management using Pydantic Settings with
environment variable support and .env file loading.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings can be overridden via environment variables or a .env file.
    Environment variables take precedence over .env file values.
    
    Attributes:
        openai_api_key: API key for OpenAI services.
        anthropic_api_key: API key for Anthropic services.
        llm_provider: Which LLM provider to use ('openai' or 'anthropic').
        consensus_threshold: Minimum score for consensus (0.0-1.0).
        consensus_max_iterations: Maximum consensus rounds before fallback.
        log_level: Logging verbosity level.
        log_format: Log output format ('json' or 'console').
        docker_image: Docker image for Java/Maven execution.
        docker_timeout: Timeout in seconds for Docker operations.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # LLM Configuration
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    llm_provider: Literal["openai", "anthropic"] = Field(
        default="openai",
        description="LLM provider to use"
    )
    
    # Consensus Settings
    consensus_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum consensus score required"
    )
    consensus_max_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum consensus iterations"
    )
    
    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level"
    )
    log_format: Literal["json", "console"] = Field(
        default="console",
        description="Log output format"
    )
    
    # Docker
    docker_image: str = Field(
        default="maven:3.9-eclipse-temurin-17",
        description="Docker image for Maven builds"
    )
    docker_timeout: int = Field(
        default=300,
        ge=60,
        description="Docker operation timeout in seconds"
    )
    
    def get_llm_api_key(self) -> str:
        """
        Get the API key for the configured LLM provider.
        
        Returns:
            The API key string for the selected provider.
            
        Raises:
            ValueError: If no API key is configured for the selected provider.
        """
        if self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            return self.openai_api_key
        else:
            if not self.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            return self.anthropic_api_key


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings instance.
    
    Uses LRU cache to ensure only one Settings instance is created,
    which is reused across the application.
    
    Returns:
        Configured Settings instance.
    """
    return Settings()
