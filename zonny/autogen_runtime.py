"""
Zonny AutoGen Runtime — v0.3.1

Architecture change from v0.3.0:
  BEFORE: SelectorGroupChat — agents pick each other → infinite loop
  NOW:    Orchestrator-Specialists pattern:
            1. UserProxyAgent sends the task
            2. ONE specialist agent is selected based on task content
            3. assistant_agent synthesizes the final reply
            4. TERMINATE is emitted → clean stop

Each agent reads its model from its YAML manifest.
stream_team() yields full transcript for the Agent Conversation page.
"""

import yaml
import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_ext.models.ollama import OllamaChatCompletionClient


# ────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────

OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "nemotron-3-nano:latest"
MANIFESTS_DIR = Path(__file__).parent.parent / "agents" / "manifests"

# Terminate when assistant says TERMINATE or after 10 messages max
TERMINATION = TextMentionTermination("TERMINATE") | MaxMessageTermination(10)

# Suffix added to every agent's system prompt to give clear termination signal
TERMINATE_SUFFIX = """
IMPORTANT INSTRUCTIONS:
- Read the user's request carefully and respond ONCE with your complete answer.
- Do NOT ask follow-up questions or wait for other agents.
- End your response with exactly: TERMINATE
- Never engage in chit-chat or greetings with other agents.
"""


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
            print(f"[WARN] Failed to load manifest {path.name}: {e}")
    return manifests


def _make_client(model: str) -> OllamaChatCompletionClient:
    """
    Create an Ollama client.  AutoGen v0.4 requires explicit model_info
    for non-OpenAI model names — passed as a plain dict (TypedDict).
    """
    return OllamaChatCompletionClient(
        model=model,
        host=OLLAMA_HOST,
        model_info={
            "vision": False,
            "function_calling": False,
            "json_output": False,
            "family": "unknown",
            "structured_output": False,
        },
    )


# ────────────────────────────────────────────────────────────────────────────
# Team Builder — Orchestrator pattern
# ────────────────────────────────────────────────────────────────────────────

def _select_specialist(task: str, manifests: list[dict]) -> dict | None:
    """
    Simple keyword-based specialist selection.
    Picks the most appropriate agent manifest for the given task.
    Falls back to generalist if no match.
    """
    task_lower = task.lower()
    scoring = {}
    for m in manifests:
        name = m.get("name", "")
        tags = m.get("metadata", {}).get("tags", [])
        desc = m.get("description", "").lower()
        score = 0
        if "code" in task_lower and ("code" in tags or "codebase" in name):
            score += 3
        if any(w in task_lower for w in ["file", "function", "class", "import", "bug"]) \
                and "code" in tags:
            score += 2
        if any(w in task_lower for w in ["document", "pdf", "upload", "read"]) \
                and "rag" in tags:
            score += 3
        if any(w in task_lower for w in ["remember", "last time", "previous", "history"]) \
                and "memory" in tags:
            score += 3
        scoring[name] = score

    if scoring:
        best = max(scoring, key=scoring.get)
        if scoring[best] > 0:
            return next(m for m in manifests if m.get("name") == best)

    # Fall back to generalist
    return next(
        (m for m in manifests if "generalist" in m.get("name", "")),
        manifests[0] if manifests else None,
    )


def _build_focused_team(task: str) -> tuple[RoundRobinGroupChat, dict]:
    """
    Build a focused 2-agent team: [specialist → assistant_agent].

    Flow:
      specialist  → deeply answers/analyses the task
      assistant   → synthesises and produces the FINAL clean response + TERMINATE

    Returns the team and the selected specialist manifest.
    """
    manifests = _load_manifests()
    if not manifests:
        raise RuntimeError("No enabled agent manifests found.")

    # Find specialist and assistant manifests
    specialist_manifest = _select_specialist(task, [
        m for m in manifests if "assistant" not in m.get("name", "")
    ])
    assistant_manifest = next(
        (m for m in manifests if "assistant" in m.get("name", "")),
        None,
    )

    team_members = []

    if specialist_manifest:
        specialist = AssistantAgent(
            name=specialist_manifest["name"],
            model_client=_make_client(specialist_manifest.get("model", DEFAULT_MODEL)),
            system_message=(
                specialist_manifest.get("system_prompt", "You are a helpful assistant.")
                + "\n\nProvide a thorough analysis to help the assistant agent produce the best final answer."
            ),
        )
        team_members.append(specialist)
        print(f"  [OK] Specialist: {specialist_manifest['name']} -> {specialist_manifest.get('model', DEFAULT_MODEL)}")

    if assistant_manifest:
        assistant = AssistantAgent(
            name=assistant_manifest["name"],
            model_client=_make_client(assistant_manifest.get("model", DEFAULT_MODEL)),
            system_message=(
                assistant_manifest.get("system_prompt",
                    "You are the final response agent. Synthesise information and respond clearly.")
                + TERMINATE_SUFFIX
            ),
        )
        team_members.append(assistant)
        print(f"  [OK] Synthesiser: {assistant_manifest['name']} -> {assistant_manifest.get('model', DEFAULT_MODEL)}")
    else:
        # No assistant manifest — add a fallback synthesiser
        synthesiser = AssistantAgent(
            name="synthesiser",
            model_client=_make_client(DEFAULT_MODEL),
            system_message=(
                "Read the previous analysis, synthesise a clear final answer, then say TERMINATE."
                + TERMINATE_SUFFIX
            ),
        )
        team_members.append(synthesiser)

    team = RoundRobinGroupChat(
        participants=team_members,
        termination_condition=TERMINATION,
    )
    return team, specialist_manifest or {}


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

async def run_team(task: str, session_id: str = "default") -> dict:
    """
    Run the focused 2-agent team on a task.

    Returns:
        {
            "final_response": str,       # The assistant's synthesised answer
            "conversation": [            # Full agent-to-agent transcript
                {"agent": str, "content": str, "model": str}
            ],
            "specialist": str,           # Which specialist was used
        }
    """
    team, specialist_manifest = _build_focused_team(task)
    result = await team.run(task=task)

    messages = result.messages if result else []
    conversation = []
    final_response = ""

    for msg in messages:
        agent_name = str(getattr(msg, "source", "unknown"))
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            content = "\n".join(c.text if hasattr(c, "text") else str(c) for c in content)
        content = str(content).replace("TERMINATE", "").strip()

        if not content:
            continue

        conversation.append({
            "agent": agent_name,
            "content": content,
        })
        # The LAST non-empty message from the assistant is the final response
        if "assistant" in agent_name.lower() or agent_name == "synthesiser":
            final_response = content

    if not final_response and conversation:
        final_response = conversation[-1]["content"]

    return {
        "final_response": final_response,
        "conversation": conversation,
        "specialist": specialist_manifest.get("name", "generalist_agent"),
    }


async def stream_team(
    task: str,
    session_id: str = "default",
) -> AsyncGenerator[dict, None]:
    """
    Stream AutoGen agent events in real time for the SSE endpoint.

    Yields dicts:
        {"agent": str, "type": str, "content": str, "model": str}

    Types:
      "message"   — agent spoke
      "final"     — the assistant's final synthesised response
      "done"      — all agents finished
    """
    team, specialist_manifest = _build_focused_team(task)

    # Build model map for display
    model_map = {
        m.get("name", ""): m.get("model", DEFAULT_MODEL)
        for m in _load_manifests()
    }

    last_assistant_content = ""

    async for event in team.run_stream(task=task):
        if hasattr(event, "source") and hasattr(event, "content"):
            agent_name = str(event.source)
            content = event.content
            if isinstance(content, list):
                content = "\n".join(
                    c.text if hasattr(c, "text") else str(c) for c in content
                )
            content = str(content).replace("TERMINATE", "").strip()

            if not content:
                continue

            is_assistant = "assistant" in agent_name.lower() or agent_name == "synthesiser"
            event_type = "final" if is_assistant else "message"

            if is_assistant:
                last_assistant_content = content

            yield {
                "agent": agent_name,
                "type": event_type,
                "content": content,
                "model": model_map.get(agent_name, DEFAULT_MODEL),
            }
            await asyncio.sleep(0)

        else:
            # TaskResult — stream is complete
            yield {
                "agent": "system",
                "type": "done",
                "content": last_assistant_content,
                "model": "",
            }


async def get_agent_status() -> list[dict]:
    """Return agent roster with model info for the UI sidebar."""
    manifests = _load_manifests()
    return [
        {
            "name": m.get("name", "unknown"),
            "model": m.get("model", DEFAULT_MODEL),
            "description": m.get("description", ""),
            "enabled": m.get("enabled", True),
            "priority": m.get("priority", "medium"),
            "status": "idle",
        }
        for m in manifests
    ]
