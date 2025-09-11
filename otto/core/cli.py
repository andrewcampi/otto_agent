import os
import sys
from typing import Any, Dict, List

from ..core.openai_client import get_openai_client
from ..core.prompts import load_strongest_system_prompt
from ..tools.registry import get_tool_specs, handle_tool_call


MODEL_ID = os.getenv("MODEL") or os.getenv("OTTO_MODEL") or "gpt-5-mini"


def run_cli(verbose: bool = False) -> int:
    client = get_openai_client()
    system_prompt = load_strongest_system_prompt()
    tools = get_tool_specs()

    print("Otto CLI — type your prompt. Ctrl-C to exit.")
    history: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]

    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user:
            continue

        history.append({"role": "user", "content": user})

        # Multi-step tool chain loop
        while True:
            # Stream a step
            stream = client.chat.completions.create(
                model=MODEL_ID,
                messages=history,
                tools=tools,
                tool_choice="auto",
                stream=True,
            )

            assistant_text_chunks: List[str] = []
            acc_tool_calls: Dict[int, Dict[str, Any]] = {}

            for event in stream:
                choice = event.choices[0]
                delta = choice.delta
                if not delta:
                    continue
                content = getattr(delta, "content", None)
                if content:
                    assistant_text_chunks.append(content)
                    sys.stdout.write(content)
                    sys.stdout.flush()
                tcs = getattr(delta, "tool_calls", None)
                if tcs:
                    for tc in tcs:
                        idx = getattr(tc, "index", 0)
                        if idx not in acc_tool_calls:
                            acc_tool_calls[idx] = {
                                "id": None,
                                "type": "function",
                                "function": {"name": None, "arguments": ""},
                            }
                        acc = acc_tool_calls[idx]
                        tc_id = getattr(tc, "id", None)
                        if tc_id:
                            acc["id"] = tc_id
                        tc_type = getattr(tc, "type", None)
                        if tc_type:
                            acc["type"] = tc_type
                        fn = getattr(tc, "function", None)
                        if fn:
                            fn_name = getattr(fn, "name", None)
                            fn_args = getattr(fn, "arguments", None)
                            if fn_name:
                                acc["function"]["name"] = fn_name
                            if fn_args:
                                acc["function"]["arguments"] += fn_args

            print()

            # Finalize tool calls, if any
            finalized_calls: List[Dict[str, Any]] = []
            for idx in sorted(acc_tool_calls.keys()):
                call = acc_tool_calls[idx]
                if not call.get("id"):
                    call["id"] = f"tool_{idx}"
                if not call.get("type"):
                    call["type"] = "function"
                fn = call.get("function") or {}
                if fn.get("name") is None:
                    fn["name"] = ""
                if fn.get("arguments") is None:
                    fn["arguments"] = ""
                call["function"] = fn
                finalized_calls.append(call)

            if finalized_calls:
                # Execute tools and loop again without asking user
                tool_results = []
                for call in finalized_calls:
                    if verbose:
                        print(f"[tool] call -> {call['function']['name']} args={call['function']['arguments']!r}")
                    result = handle_tool_call(call)
                    if verbose:
                        print(f"[tool] result <- {result['content'][:500]}")
                    tool_results.append(result)
                history.append({
                    "role": "assistant",
                    "tool_calls": finalized_calls,
                    "content": None,
                })
                for r in tool_results:
                    history.append(r)
                if verbose:
                    print("[turn] continuing after tool results\n")
                continue
            else:
                # No tool calls – finalize text and end the turn
                text = "".join(assistant_text_chunks)
                history.append({"role": "assistant", "content": text})
                break

    # not reached
    # return 0


