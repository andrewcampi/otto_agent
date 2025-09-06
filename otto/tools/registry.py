import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]


def get_tool_specs() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file slice or whole file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start": {"type": "integer"},
                        "end": {"type": "integer"},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "List directory entries.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "grep_search",
                "description": "Exact regex search (ripgrep)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "path": {"type": "string"},
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "file_search",
                "description": "Fuzzy file search by substring.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Apply targeted edits using sentinel blocks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_file": {"type": "string"},
                        "instructions": {"type": "string"},
                        "code_edit": {"type": "string"},
                    },
                    "required": ["target_file", "instructions", "code_edit"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_file",
                "description": "Delete a file if it exists.",
                "parameters": {
                    "type": "object",
                    "properties": {"target_file": {"type": "string"}},
                    "required": ["target_file"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_terminal_cmd",
                "description": "Run a command non-interactively.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "is_background": {"type": "boolean"},
                    },
                    "required": ["command", "is_background"],
                },
            },
        },
    ]


def handle_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    fn = tool_call.get("function", {})
    name = fn.get("name")
    args_raw = fn.get("arguments") or "{}"
    try:
        args = json.loads(args_raw)
    except Exception:
        args = {}

    if name == "read_file":
        path = Path(args.get("path", ""))
        start = int(args.get("start") or 1)
        end = int(args.get("end") or 0)
        content = ""
        try:
            text = path.read_text(encoding="utf-8")
            if end and end >= start:
                lines = text.splitlines()
                slice_ = lines[start - 1 : end]
                content = "\n".join(slice_)
            else:
                content = text
            result = {"ok": True, "path": str(path), "content": content}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        return {"role": "tool", "tool_call_id": tool_call.get("id"), "name": name, "content": json.dumps(result)}

    if name == "list_dir":
        path = Path(args.get("path", "."))
        try:
            entries = [
                (p.name + ("/" if p.is_dir() else ""))
                for p in path.iterdir()
            ]
            result = {"ok": True, "path": str(path), "entries": entries}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        return {"role": "tool", "tool_call_id": tool_call.get("id"), "name": name, "content": json.dumps(result)}

    if name == "grep_search":
        pattern = args.get("pattern", "")
        search_path = args.get("path", ".")
        if not pattern:
            result = {"ok": False, "error": "pattern required"}
        else:
            try:
                # simple rg call
                cmd = [
                    "rg",
                    "-n",
                    "--color=never",
                    pattern,
                    search_path,
                ]
                out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                result = {
                    "ok": out.returncode in (0,1),
                    "stdout": out.stdout,
                    "stderr": out.stderr,
                    "exit_code": out.returncode,
                }
            except Exception as e:
                result = {"ok": False, "error": str(e)}
        return {"role": "tool", "tool_call_id": tool_call.get("id"), "name": name, "content": json.dumps(result)}

    if name == "file_search":
        query = args.get("query", "").lower()
        hits: List[str] = []
        for root, dirs, files in os.walk("."):
            for f in files:
                p = os.path.join(root, f)
                rel = os.path.relpath(p, ".")
                if query and query in rel.lower():
                    hits.append(rel)
                    if len(hits) >= 50:
                        break
        result = {"ok": True, "results": hits}
        return {"role": "tool", "tool_call_id": tool_call.get("id"), "name": name, "content": json.dumps(result)}

    if name == "edit_file":
        target = Path(args.get("target_file", ""))
        code_edit = args.get("code_edit", "")
        try:
            # naive apply: replace sentinel sections, keep exactly as provided
            target.parent.mkdir(parents=True, exist_ok=True)
            if "\n" not in code_edit and code_edit.strip() == "":
                raise ValueError("empty code_edit")
            # if the model provides full content, write it; otherwise append
            if code_edit.strip().startswith("// ...") or "// ... existing code ..." in code_edit:
                # for simplicity, write as-is to make the change explicit
                existing = target.read_text(encoding="utf-8") if target.exists() else ""
                merged = f"{existing}\n{code_edit}\n"
                target.write_text(merged, encoding="utf-8")
            else:
                target.write_text(code_edit, encoding="utf-8")
            result = {"ok": True, "path": str(target)}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        return {"role": "tool", "tool_call_id": tool_call.get("id"), "name": name, "content": json.dumps(result)}

    if name == "delete_file":
        target = Path(args.get("target_file", ""))
        try:
            if target.exists():
                target.unlink()
            result = {"ok": True, "path": str(target)}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        return {"role": "tool", "tool_call_id": tool_call.get("id"), "name": name, "content": json.dumps(result)}

    if name == "run_terminal_cmd":
        cmd = args.get("command", "")
        is_bg = bool(args.get("is_background"))
        if not cmd:
            result = {"ok": False, "error": "command required"}
        else:
            try:
                if is_bg:
                    p = subprocess.Popen(cmd, shell=True)
                    result = {"ok": True, "pid": p.pid}
                else:
                    out = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    result = {
                        "ok": out.returncode == 0,
                        "stdout": out.stdout,
                        "stderr": out.stderr,
                        "exit_code": out.returncode,
                    }
            except Exception as e:
                result = {"ok": False, "error": str(e)}
        return {"role": "tool", "tool_call_id": tool_call.get("id"), "name": name, "content": json.dumps(result)}

    # Unknown tool
    result = {"ok": False, "error": f"Unknown tool '{name}'"}
    return {"role": "tool", "tool_call_id": tool_call.get("id"), "name": name, "content": json.dumps(result)}


