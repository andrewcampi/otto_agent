from typing import Optional

from openai import OpenAI

from .config import get_openai_api_key, get_openai_base_url, require_env_var


def get_openai_client() -> OpenAI:
    api_key: Optional[str] = get_openai_api_key()
    base_url: Optional[str] = get_openai_base_url()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Set it in the environment or create a .env and reload.")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)
