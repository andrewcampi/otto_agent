import os
from typing import Optional

from openai import OpenAI


def get_openai_client() -> OpenAI:
    api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    base_url: Optional[str] = os.getenv("OPENAI_BASE_URL")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Set it in the environment or create a .env and reload.")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)
