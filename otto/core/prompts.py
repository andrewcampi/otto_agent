from pathlib import Path


def load_strongest_system_prompt() -> str:
    # Prefer packaged prompts in otto/prompts
    roots = [
        Path(__file__).resolve().parents[1] / "prompts",
        Path.cwd() / "otto" / "prompts",
    ]
    preferred = [
        "Agent Prompt 2025-09-03.txt",
        "Agent Prompt v1.2.txt",
        "Agent CLI Prompt 2025-08-07.txt",
    ]
    for root in roots:
        for name in preferred:
            p = root / name
            if p.exists():
                return p.read_text(encoding="utf-8")
    # Minimal fallback
    return (
        "You are an AI coding assistant, powered by GPT-5. You operate in a CLI. "
        "You have tools and must autonomously use them to complete tasks."
    )


