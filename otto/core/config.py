"""Configuration module for Otto Agent using python-dotenv for environment variable handling."""

import os
from typing import Optional

try:
    from dotenv import load_dotenv
    # Load environment variables from .env file if it exists
    load_dotenv()
except ImportError:
    # Fallback if dotenv is not available
    pass


def get_openai_api_key() -> Optional[str]:
    """Get OpenAI API key from environment variables."""
    return os.getenv("OPENAI_API_KEY")


def get_openai_base_url() -> Optional[str]:
    """Get OpenAI base URL from environment variables."""
    return os.getenv("OPENAI_BASE_URL")


def get_model_id() -> str:
    """Get model ID from environment variables with fallback."""
    return os.getenv("MODEL") or os.getenv("OTTO_MODEL") or "gpt-5-mini"


def require_env_var(var_name: str) -> str:
    """Get a required environment variable or raise an error."""
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"{var_name} not set. Set it in the environment or create a .env file and reload.")
    return value
