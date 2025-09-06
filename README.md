# Otto - Python Cursor-like Agent

### Install (from GitHub)

```bash
python3 -m pip install git+https://github.com/andrewcampi/otto_agent.git
```

### Configure

- Create a `.env` with `OPENAI_API_KEY=...` (or pass api_key to the client)

### CLI usage

- python3 -m otto
- python3 -m otto --verbose

### Python client usage

```python
import os
from dotenv import load_dotenv
from otto import OttoAgent

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OttoAgent(api_key=OPENAI_API_KEY)  # optional base_url to use local models
r1 = client.prompt("List the CWD and summarize.")
print(r1["final_text"])  # human text
# Full step logs (assistant text fragments + tool_calls per step)
print(r1["steps"])      
```

### Included tools

- read_file, list_dir, grep_search (rg), file_search, edit_file, delete_file, run_terminal_cmd

### Notes

- Prompts ship with the package (otto/prompts) and are auto-loaded.
- Model defaults to gpt-5-mini; override via OTTO_MODEL env.

###Custom tools (advanced)

You can add extra tools to a specific client instance. Built-in tools are always present; your tools are additional. Provide:
- extra_tools: a list of OpenAI tool specs (function tools JSON).
- extra_tool_handler (optional): a default callable for any unknown tool.
- extra_tool_handlers (optional): a dict mapping tool name → handler callable (overrides the default for that tool).

Example: a simple calculator tool
```python
import os
from dotenv import load_dotenv
from otto import OttoAgent

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

calc_tool = {
    "type": "function",
    "function": {
        "name": "calc",
        "description": "Evaluate a basic arithmetic expression using Python eval in a restricted scope.",
        "parameters": {
            "type": "object",
            "properties": {
                "expr": {"type": "string"}
            },
            "required": ["expr"]
        },
    },
}

def calc_handler(tool_call: dict) -> dict:
    fn = tool_call.get("function", {})
    args_raw = fn.get("arguments", "{}")
    try:
        args = json.loads(args_raw)
    except Exception:
        args = {}
    expr = str(args.get("expr", "")).strip()
    try:
        # Extremely limited eval; only arithmetic
        allowed = {"__builtins__": {}}
        val = eval(expr, allowed, {})
        result = {"ok": True, "value": val}
    except Exception as e:
        result = {"ok": False, "error": str(e)}
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id"),
        "name": "calc",
        "content": json.dumps(result),
    }

client = OttoAgent(
    api_key=OPENAI_API_KEY,
    extra_tools=[calc_tool],
    extra_tool_handlers={"calc": calc_handler},
)
print(client.prompt("Calculate 2 + 3 * 4, then list the CWD.")["final_text"])
```
