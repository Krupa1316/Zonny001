"""
🤖 Zonny AutoGen Runtime — v0.3.0

Replaces the custom runtime/engine.py + zonny/planner.py + zonny/executor.py pipeline.

Uses AutoGen v0.4 (autogen-agentchat) with Ollama as the LLM backend.
Each agent loads its own model from its YAML manifest — enabling per-agent LLM selection.

Architecture:
  User Task
    → load_team()          — reads manifests, creates AssistantAgents per model
    → SelectorGroupChat    — LLM picks which agent speaks next
    → run_team()           — runs to completion, returns final string
    → stream_team()        — async generator yielding AgentEvents for SSE

Design rules:
  ✅ Each agent uses manifest["model"] — falls back to DEFAULT_MODEL if absent
  ✅ Async-first — all public functions are async
  ✅ Stateless — no global mutable state between calls
  ✅ Events emitted for every message — feeds the Web UI live activity panel
"""

import yaml
import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.messages import AgentEvent, ChatMessage
from autogen_ext.models.ollama import OllamaChatCompletionClient


# ────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────

OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "nemotron-3-nano:latest"
MANIFESTS_DIR = Path(__file__).parent.parent / "agents" / "manifests"

# Termination: stop when any agent says TERMINATE or after 20 messages
TERMINATION = TextMentionTermination("TERMINATE") | MaxMessageTermination(20)


# ────────────────────────────────────────────────────────────────────────────
# Manifest Loading
# ────────────────────────────────────────────────────────────────────────────

def _load_manifests() -> list[dict]:
    """Load all enabled agent manifests from agents/manifests/*.yaml"""
    manifests = []
    for path in sorted(MANIFESTS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if data and data.get("enabled", True):
                manifests.append(data)
        except Exception as e:
            print(f"⚠️  Failed to load manifest {path.name}: {e}")
    return manifests


def _make_client(model: str) -> OllamaChatCompletionClient:
    """Create an Ollama client for the given model name."""
    return OllamaChatCompletionClient(
        model=model,
        host=OLLAMA_HOST,
    )


# ────────────────────────────────────────────────────────────────────────────
# Team Builder
# ────────────────────────────────────────────────────────────────────────────

def _build_team() -> SelectorGroupChat:
    """
    Build an AutoGen SelectorGroupChat from loaded manifests.

    - Each enabled manifest becomes an AssistantAgent
    - Each agent uses its own model (from manifest["model"])
    - A separate selector LLM (lightweight nemotron) picks the next agent
    """
    manifests = _load_manifests()

    if not manifests:
        raise RuntimeError(
            "No enabled agent manifests found in agents/manifests/. "
            "Check that YAML files exist and have 'enabled: true'."
        )

    agents = []
    for m in manifests:
        model_name = m.get("model", DEFAULT_MODEL)
        system_prompt = m.get("system_prompt", "You are a helpful AI assistant.")
        name = m.get("name", "agent").replace("-", "_").replace(" ", "_")

        agent = AssistantAgent(
            name=name,
            model_client=_make_client(model_name),
            system_message=system_prompt,
        )
        agents.append(agent)
        print(f"  [OK] Loaded agent: {name} -> {model_name}")

    # Selector uses lightweight model to pick which agent speaks next
    selector_client = _make_client(DEFAULT_MODEL)

    team = SelectorGroupChat(
        participants=agents,
        model_client=selector_client,
        termination_condition=TERMINATION,
        allow_repeated_speaker=False,
    )

    return team


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

async def run_team(task: str, session_id: str = "default") -> str:
    """
    Run the AutoGen agent team on a task.

    Replaces: runtime/engine.py + zonny/planner.py + zonny/executor.py

    Args:
        task: Natural language task/question from the user
        session_id: Session identifier (for future memory scoping)

    Returns:
        Final response string
    """
    team = _build_team()

    result = await team.run(task=task)

    # Extract final message text
    messages = result.messages
    if messages:
        last = messages[-1]
        # Handle both string content and list content (tool calls etc.)
        if hasattr(last, "content"):
            content = last.content
            if isinstance(content, list):
                # Flatten list content to string
                parts = [c.text if hasattr(c, "text") else str(c) for c in content]
                return "\n".join(parts)
            return str(content)
    return "No response generated."


async def stream_team(
    task: str,
    session_id: str = "default",
) -> AsyncGenerator[dict, None]:
    """
    Stream AutoGen agent events as they happen.

    Used by the FastAPI SSE endpoint to power the Web UI live activity panel.

    Yields dicts with:
        {
            "agent": str,           # agent name
            "type": str,            # "message" | "thinking" | "tool_call" | "complete"
            "content": str,         # message text or tool name
            "model": str,           # model used (from manifest)
        }
    """
    team = _build_team()

    # Build manifest lookup for model name display
    model_map = {
        m.get("name", "").replace("-", "_"): m.get("model", DEFAULT_MODEL)
        for m in _load_manifests()
    }

    async for event in team.run_stream(task=task):
        if hasattr(event, "source") and hasattr(event, "content"):
            agent_name = str(event.source)
            content = event.content

            # Normalise content
            if isinstance(content, list):
                text = "\n".join(
                    c.text if hasattr(c, "text") else str(c) for c in content
                )
            else:
                text = str(content)

            yield {
                "agent": agent_name,
                "type": "message",
                "content": text,
                "model": model_map.get(agent_name, DEFAULT_MODEL),
            }

        elif hasattr(event, "type"):
            # TaskResult or other terminal event
            yield {
                "agent": "system",
                "type": "complete",
                "content": "Task complete.",
                "model": "",
            }


async def get_agent_status() -> list[dict]:
    """
    Return current agent roster with model info for the UI sidebar.

    Returns:
        List of {name, model, description, enabled, priority}
    """
    manifests = _load_manifests()
    return [
        {
            "name": m.get("name", "unknown"),
            "model": m.get("model", DEFAULT_MODEL),
            "description": m.get("description", ""),
            "enabled": m.get("enabled", True),
            "priority": m.get("priority", "medium"),
            "status": "idle",  # Initial state; UI updates this via SSE
        }
        for m in manifests
    ]
