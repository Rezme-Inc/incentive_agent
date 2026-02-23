"""
Centralized configuration management using Pydantic Settings
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API Keys
    anthropic_api_key: str = ""
    tavily_api_key: str = ""
    exa_api_key: str = ""

    @field_validator("anthropic_api_key", "tavily_api_key", "exa_api_key", "database_url", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    # Model Configuration
    claude_model: str = "claude-haiku-4-5-20251001"
    thinking_budget_tokens: int = 12000

    # Application Settings
    state: str = "Illinois"  # Default state for fallback
    golden_dataset_path: str = "src/data/golden_dataset.xlsx"

    # Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # Cache TTL (days)
    cache_ttl_federal: int = 30
    cache_ttl_state: int = 30
    cache_ttl_county: int = 14
    cache_ttl_city: int = 7

    # Database
    database_url: str = ""  # Postgres connection string (Supabase). If empty, falls back to SQLite.
    database_path: str = "data/programs.db"  # SQLite path (local dev only)

    # Demo Mode
    demo_mode: bool = False

    # Rate Limits (safety ceilings to prevent runaway costs)
    max_concurrent_sessions: int = 5
    max_sessions_per_day: int = 50
    max_exa_queries_per_session: int = 20
    max_llm_calls_per_session: int = 10

    # ROI Cycle
    max_roi_refinement_rounds: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    settings = Settings()

    # Skip API key validation in demo mode
    if not settings.demo_mode:
        if not settings.anthropic_api_key or not settings.anthropic_api_key.strip():
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Please add it to your .env file:\n"
                "  ANTHROPIC_API_KEY=your_key_here"
            )

        if not settings.tavily_api_key or not settings.tavily_api_key.strip():
            raise ValueError(
                "TAVILY_API_KEY is not set. Please add it to your .env file:\n"
                "  TAVILY_API_KEY=your_key_here"
            )

        if not settings.exa_api_key or not settings.exa_api_key.strip():
            raise ValueError(
                "EXA_API_KEY is not set. Please add it to your .env file:\n"
                "  EXA_API_KEY=your_key_here"
            )
    
    return settings


settings = get_settings()
