"""
Zonny Status — Master Execution Plan Diagnostic
================================================
Runs every component through its paces and reports pass/fail.

Usage:
    python zonny_status.py

Set ZONNY_MODE=safe to test safe-mode blocking.
"""

import sys
import os
import json
import time
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OLLAMA_URL = "http://localhost:11434"
MODEL = "nemotron-3-nano:latest"

PASS = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]️ "

results = {}


def check(name: str, ok: bool, detail: str = ""):
    results[name] = ok
    icon = PASS if ok else FAIL
    line = f" {icon} {name}"
    if detail:
        line += f" → {detail}"
    print(line)
    return ok


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f" {title}")
    print(f"{'─' * 60}")


# ─────────────────────────────────────────────────────────────────────────────
section("PHASE 0 — INFRASTRUCTURE")

# Ollama reachable
try:
    r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
    check("Ollama running", r.status_code == 200, f"HTTP {r.status_code}")
    models = [m["name"] for m in r.json().get("models", [])]
    model_ok = any(MODEL in m for m in models)
    check(f"Model: {MODEL}", model_ok,
          "found" if model_ok else f"not found (available: {', '.join(models[:3])}...)")
except Exception as e:
    check("Ollama running", False, str(e))
    check(f"Model: {MODEL}", False, "Ollama unreachable")

# ─────────────────────────────────────────────────────────────────────────────
section("PHASE 5 — TOOL REGISTRY (single source of truth)")

try:
    from zonny.tool_registry import (
        has_tool, find_by_capability, get_tool_by_name,
        get_tools_by_capability, list_tool_names
    )
    names = list_tool_names()

    check("Registry loads", True, f"{len(names)} tools defined")
    check("has_tool('filesystem.search')", has_tool("filesystem.search"), "")
    check("has_tool('workspace.search') is False",
          not has_tool("workspace.search"), "phantom tool rejected")
    search_tool = find_by_capability("search")
    check("find_by_capability('search')", search_tool == "filesystem.search",
          search_tool or "None")
    check("All tools have 'capability' field",
          all("capability" in t for t in [get_tool_by_name(n) for n in names]),
          "")
except Exception as e:
    check("Tool registry", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("PHASE 1 — ROUTER (agent-intent output, NO tool names)")

try:
    from zonny.semantic_router import route, AGENTS

    check("Router imports", True, f"agents: {list(AGENTS.keys())}")

    # Test structure
    r = route("list files in this directory")
    has_agent = "agent" in r and r["agent"] in AGENTS
    has_task = "task" in r and len(r.get("task", "")) > 5
    no_tool_key = "tool" not in r
    no_args_key = "args" not in r

    check("Router returns 'agent' field", has_agent,
          r.get("agent", "MISSING"))
    check("Router returns 'task' field (natural language)", has_task,
          r.get("task", "MISSING")[:60])
    check("Router does NOT return 'tool' key", no_tool_key,
          "clean" if no_tool_key else f"found tool={r.get('tool')}")
    check("Router does NOT return 'args' key", no_args_key,
          "clean" if no_args_key else "args key present")

    # Test agent selection
    r2 = route("what did we talk about earlier in the session?")
    check("Routes 'recall' → memory agent",
          r2.get("agent") == "memory",
          f"got: {r2.get('agent')}")

    r3 = route("hello there!")
    check("Routes greeting → general agent",
          r3.get("agent") == "general",
          f"got: {r3.get('agent')}")

    r4 = route("read server.py")
    check("Routes file read → code agent",
          r4.get("agent") == "code",
          f"got: {r4.get('agent')}")

except Exception as e:
    check("Router", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("PHASE 3 — DISPATCHER SECURITY LAYER")

try:
    from zonny.dispatcher import (
        _enforce_path_safety, _check_write_permission, PERMISSION_MODE,
        WRITE_ALLOWED_EXTENSIONS, WRITE_BLOCKED_EXTENSIONS
    )

    check("Dispatcher security imports", True,
          f"mode={PERMISSION_MODE}")

    # Path safety: traversal attack should be blocked
    fake_root = os.path.join(ROOT, "sandbox")
    safe, err = _enforce_path_safety("../../../etc/passwd", fake_root)
    check("Blocks path traversal (../../../etc/passwd)", safe is None,
          "blocked" if safe is None else f"UNSAFE: {safe}")

    # Path safety: valid path should pass
    safe2, err2 = _enforce_path_safety("server.py", ROOT)
    check("Allows valid path (server.py)", safe2 is not None and err2 is None,
          os.path.relpath(safe2, ROOT) if safe2 else "BLOCKED")

    # Extension checks
    ok_py, _ = _check_write_permission("main.py")
    check("Allows write to .py files", ok_py, "")

    blocked_exe, reason_exe = _check_write_permission("evil.exe")
    check("Blocks write to .exe files", not blocked_exe, reason_exe[:60])

    blocked_env, reason_env = _check_write_permission(".env")
    check("Blocks write to .env files", not blocked_env, reason_env[:60])

    # Safe mode test
    original_mode = os.environ.get("ZONNY_MODE", "dev")
    os.environ["ZONNY_MODE"] = "safe"
    # Re-import to pick up new env value
    import importlib
    import zonny.dispatcher as disp_mod
    importlib.reload(disp_mod)
    ok_safe, reason_safe = disp_mod._check_write_permission("readme.md")
    check("ZONNY_MODE=safe blocks all writes", not ok_safe, reason_safe[:60])
    os.environ["ZONNY_MODE"] = original_mode
    importlib.reload(disp_mod)

    # Registry validation in dispatch
    result = disp_mod.dispatch({"tool": "workspace.search", "args": {}}, {"project_root": ROOT})
    check("Dispatcher rejects unknown tool (workspace.search)",
          "not in tool registry" in result or "Unknown tool" in result, result[:80])

except Exception as e:
    check("Dispatcher security", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("PHASE 2 — AGENT EXECUTION MODEL")

try:
    from agents.registry import list_available as list_agents
    agents = list_agents()
    agent_names = [a if isinstance(a, str) else a.get("name", str(a)) for a in agents]
    check("Agent registry loads", True, f"{len(agents)} agents: {agent_names}")
except Exception as e:
    try:
        from agents.registry import get as get_agent
        check("Agent registry (get) loads", True, "")
    except Exception as e2:
        check("Agent registry", False, str(e2))

try:
    from zonny.react_loop import ReActLoop, run_react_agent
    check("ReAct loop imports", True, "ReActLoop + run_react_agent")
except Exception as e:
    check("ReAct loop", False, str(e))

try:
    from zonny.executor import execute_plan
    check("Executor imports", True, "execute_plan")
except Exception as e:
    check("Executor", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("PHASE 4 — REFLECTION LOOP")

try:
    from zonny.reflector import reflect, should_retry

    dummy_exec = {
        "success": True,
        "steps_completed": 1,
        "total_steps": 1,
        "results": [{"step": 1, "task": "list files", "tool": "filesystem.list",
                     "result": "Files: server.py, zonny.py", "success": True}]
    }
    ref = reflect("list files in workspace", dummy_exec)

    check("Reflector imports", True, "")
    check("Reflector returns 'done' field", "done" in ref, str(ref.get("done")))
    check("Reflector returns 'confidence' field", "confidence" in ref, str(ref.get("confidence")))
    check("Reflector returns 'approach_quality'", "approach_quality" in ref,
          ref.get("approach_quality", "missing"))
    check("should_retry() works on done=True",
          not should_retry({"done": True, "confidence": 0.9}), "")
    check("should_retry() triggers on low confidence + next_action",
          should_retry({"done": False, "confidence": 0.4, "next_action": "read README"}), "")

except Exception as e:
    check("Reflector", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("PHASE 0 — ADDITIONAL CHECKS")

try:
    from zonny.planner import ReactPlanner
    p = ReactPlanner()
    check("ReactPlanner instantiates", True, f"model={p.model}")
except Exception as e:
    check("ReactPlanner", False, str(e))

try:
    from zonny.world import WorldState, create_initial_world
    w = create_initial_world("test query", ROOT)
    summary = w.get_context_summary()
    check("WorldState context includes files", "File Contents" in summary or "Working in" in summary,
          summary[:80])
except Exception as e:
    check("WorldState", False, str(e))

try:
    from zonny.dispatcher import dispatch
    result = dispatch(
        {"tool": "filesystem.list", "args": {"path": "."}},
        {"project_root": ROOT}
    )
    check("Dispatcher executes filesystem.list", not result.startswith("[FAIL]"), result[:80])
except Exception as e:
    check("Dispatcher execution", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("SUMMARY")

total = len(results)
passed = sum(1 for v in results.values() if v)
failed = total - passed
pct = int(passed / total * 100) if total else 0

print(f"\n {PASS} Passed : {passed}/{total}")
print(f" {FAIL} Failed : {failed}/{total}")
print(f" Score : {pct}%\n")

if failed:
    print(" Failed checks:")
    for k, v in results.items():
        if not v:
            print(f" {FAIL} {k}")
    print()

if pct == 100:
    print(" [DONE] All systems nominal. Zonny is ready.\n")
elif pct >= 75:
    print(" [WARN] Core working. Fix failing checks before production.\n")
else:
    print(" [ERROR] Critical failures detected. Fix before using.\n")

sys.exit(0 if failed == 0 else 1)
