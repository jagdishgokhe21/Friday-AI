"""
FRIDAY hands — Mark LVI's desktop actions, served to Claude Code over MCP.

The bridge (bridge/server.mjs) spawns this file as a stdio MCP server. Every
actions/*.py that declares a TOOL dict is discovered exactly as Mark LVI did it
(core/action_loader.py) and offered to the brain as an MCP tool, alongside the
three things Mark LVI kept in main.py rather than in actions/: memory, recall
and undo.

WHY STDOUT IS MOVED BEFORE ANYTHING ELSE IMPORTS
    MCP over stdio owns stdout: one stray byte there and the client drops the
    connection. The actions print freely, and some shell out to tools that do
    too. So file descriptor 1 is duplicated for the protocol and then pointed at
    stderr — every print, and every child process, lands in the bridge's log
    instead of in the protocol stream.

WHAT IS DIFFERENT FROM MARK LVI
    * No HUD. The handler context gets a headless `player` whose log and speech
      go to stderr; the action's return value is what reaches the brain.
    * No confirmation screen. core/confirm.py refuses irreversible actions when
      nothing is bound to show the prompt, so shutdown, restart and the like
      decline rather than run unasked. The bridge's decideTool() is the other
      gate: effectful tools here need JARVIS_ALLOW_WRITES=1.
    * Gemini is optional. Actions that use it for a smart step (web grounding,
      transcript summaries, finding something on screen) work once a free key
      is in config/api_keys.json as {"gemini_api_key": "..."}, and say so
      plainly when it is not.

Derived from Mark LVI by FatihMakes, CC BY-NC 4.0. See ../LICENSE.
"""
from __future__ import annotations

import os
import sys

_PROTOCOL_OUT = os.fdopen(os.dup(1), "wb", buffering=0)
os.dup2(2, 1)
sys.stdout = sys.stderr

import asyncio
import io
from pathlib import Path

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.chdir(HERE)

from core import undo as undo_stack                          # noqa: E402
from core.action_loader import discover_actions              # noqa: E402
from memory.memory_manager import forget, remember, search_memory  # noqa: E402


def _log(msg: str) -> None:
    print(f"[hands] {msg}", file=sys.stderr, flush=True)


class HeadlessPlayer:
    """What the actions call `player` — the HUD in Mark LVI, a log line here."""

    muted = False

    def write_log(self, text: str) -> None:
        _log(text)

    def request_say(self, instruction: str) -> None:
        _log(f"say: {instruction}")

    def __getattr__(self, name):
        # Any other HUD method an action reaches for is a no-op, not a crash.
        return lambda *a, **k: None


_PLAYER = HeadlessPlayer()
_CTX = {
    "player": _PLAYER,
    "speak": lambda text: _log(f"speak: {text}"),
    "response": None,
    "session_memory": None,
}

registry = discover_actions(HERE / "actions", reserved_names={"memory_save", "memory_recall",
                                                              "memory_forget", "undo"},
                            logger=_log)


def _json_schema(gemini_schema):
    """Gemini declarations spell types in upper case ("OBJECT", "STRING");
    JSON Schema, which MCP speaks, wants them lower case. Nothing else differs."""
    if isinstance(gemini_schema, dict):
        return {k: (v.lower() if k == "type" and isinstance(v, str) else _json_schema(v))
                for k, v in gemini_schema.items()}
    if isinstance(gemini_schema, list):
        return [_json_schema(v) for v in gemini_schema]
    return gemini_schema


_BUILTINS = [
    types.Tool(
        name="memory_save",
        description="Remember a durable fact about the user (preferences, names, "
                    "projects, clients). Stored locally on this machine.",
        inputSchema={"type": "object", "required": ["key", "value"], "properties": {
            "key": {"type": "string", "description": "Short label, e.g. 'favourite_tea'"},
            "value": {"type": "string"},
            "category": {"type": "string", "enum": ["identity", "preferences", "projects", "relationships", "wishes", "notes"]},
        }},
    ),
    types.Tool(
        name="memory_recall",
        description="Search what you have remembered about the user. Use before "
                    "saying you do not know something personal.",
        inputSchema={"type": "object", "required": ["query"], "properties": {
            "query": {"type": "string"},
        }},
    ),
    types.Tool(
        name="memory_forget",
        description="Delete a remembered fact when the user asks you to forget it.",
        inputSchema={"type": "object", "required": ["key"], "properties": {
            "key": {"type": "string"},
            "category": {"type": "string"},
        }},
    ),
    types.Tool(
        name="undo",
        description="Take back the last file or setting change these tools made, "
                    "or list what can be undone (action='list').",
        inputSchema={"type": "object", "properties": {
            "action": {"type": "string", "enum": ["last", "list"]},
        }},
    ),
]


def _run_builtin(name: str, args: dict) -> str:
    if name == "memory_save":
        return remember(args.get("key", ""), args.get("value", ""), args.get("category") or "notes")
    if name == "memory_recall":
        return search_memory(args.get("query", ""), limit=8)
    if name == "memory_forget":
        return forget(args.get("key", ""), args.get("category") or "notes")
    if str(args.get("action", "")).lower() == "list":
        items = undo_stack.history()
        return ("Things I can undo, most recent first:\n"
                + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(items))
                ) if items else "Nothing to undo yet."
    return undo_stack.undo_last()


server = Server("friday-hands")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    tools = list(_BUILTINS)
    for decl in registry.get_tool_declarations():
        tools.append(types.Tool(name=decl["name"], description=decl["description"],
                                inputSchema=_json_schema(decl["parameters"])))
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    args = dict(arguments or {})
    _log(f"call {name} {args}")
    if any(t.name == name for t in _BUILTINS):
        result = await asyncio.to_thread(_run_builtin, name, args)
    else:
        result = await asyncio.to_thread(registry.run, name, args, _CTX)
    return [types.TextContent(type="text", text=str(result))]


async def main() -> None:
    stdin = anyio.wrap_file(io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8"))
    stdout = anyio.wrap_file(io.TextIOWrapper(_PROTOCOL_OUT, encoding="utf-8",
                                              write_through=True))
    async with stdio_server(stdin=stdin, stdout=stdout) as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
