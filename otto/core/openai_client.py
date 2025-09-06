import os
from typing import Optional

from openai import OpenAI


def get_openai_client() -> OpenAI:
    api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Create a .env with OPENAI_API_KEY and reload.")
    return OpenAI(api_key=api_key)


