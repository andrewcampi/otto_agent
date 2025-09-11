import sys
import json
from typing import Any, Dict, List, Optional, Callable

from openai import OpenAI

from .prompts import load_strongest_system_prompt
from .config import get_openai_api_key, get_openai_base_url, get_model_id
from ..tools.registry import get_tool_specs, handle_tool_call


class OttoAgent:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        extra_tools: Optional[List[Dict[str, Any]]] = None,
        extra_tool_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        extra_tool_handlers: Optional[Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = None,
    ) -> None:
        key = api_key or get_openai_api_key()
        if not key:
            raise RuntimeError("api_key is required (or set OPENAI_API_KEY)")
        resolved_base_url = base_url or get_openai_base_url()
        if resolved_base_url:
            self.client = OpenAI(api_key=key, base_url=resolved_base_url)
        else:
            self.client = OpenAI(api_key=key)
        self.model = get_model_id()
        self.system_prompt = load_strongest_system_prompt()
        # Default tools
        self.tools = get_tool_specs()
        # Optional additional tools (specs follow OpenAI tool JSON)
        if extra_tools:
            self.tools = self.tools + list(extra_tools)
        # Optional handlers for extra tools; called when builtin handler doesn't recognize tool
        self.extra_tool_handler = extra_tool_handler
        self.extra_tool_handlers = extra_tool_handlers or {}
        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

    def prompt(self, text: str, verbose: bool = False) -> Dict[str, Any]:
        self.history.append({"role": "user", "content": text})
        step_logs: List[Dict[str, Any]] = []

        while True:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                tools=self.tools,
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
                    if verbose:
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

            # finalize tool calls
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

            # log this streamed step
            step_logs.append({
                "assistant_text": "".join(assistant_text_chunks),
                "tool_calls": finalized_calls,
            })

            if finalized_calls:
                # execute tools, append, and continue loop
                tool_results = []
                for call in finalized_calls:
                    if verbose:
                        print(f"[tool] call -> {call['function']['name']} args={call['function']['arguments']!r}")
                    result = handle_tool_call(call)
                    # If builtin handler didn't recognize, try user handler
                    try:
                        ok_probe = json.loads(result.get("content", "{}"))
                    except Exception:
                        ok_probe = {}
                    unknown = isinstance(ok_probe, dict) and ok_probe.get("ok") is False and "Unknown tool" in ok_probe.get("error", "")
                    if unknown:
                        # Prefer name-specific handler if provided
                        name = (call.get("function") or {}).get("name") or ""
                        handler = self.extra_tool_handlers.get(name) if name else None
                        if handler:
                            result = handler(call)
                        elif self.extra_tool_handler:
                            result = self.extra_tool_handler(call)
                    if verbose:
                        preview = result.get("content", "")
                        print(f"[tool] result <- {preview[:500]}")
                    tool_results.append(result)
                self.history.append({
                    "role": "assistant",
                    "tool_calls": finalized_calls,
                    "content": None,
                })
                for r in tool_results:
                    self.history.append(r)
                continue
            else:
                # no tool calls; finalize text and return
                final_text = "".join(assistant_text_chunks)
                self.history.append({"role": "assistant", "content": final_text})
                return {
                    "ok": True,
                    "final_text": final_text,
                    "steps": step_logs,
                    "history_count": len(self.history),
                }


