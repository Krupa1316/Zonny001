"""
zonny/company_runtime.py — Software Company Agent Pipeline

6-agent pipeline: CEO → Architect → Frontend → Backend → QA → Reviewer
Each agent is specialised. Reviewer ends with TERMINATE.
Generated files are extracted from agent output and saved to disk.
"""
from __future__ import annotations

import asyncio
import re
import os
from pathlib import Path
from typing import AsyncGenerator, Dict, List

import yaml
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models.ollama import OllamaChatCompletionClient

# ─── Config ───────────────────────────────────────────────────
OLLAMA_HOST   = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MANIFEST_DIR  = Path(__file__).parent.parent / "agents" / "manifests"
OUTPUTS_DIR   = Path(__file__).parent.parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

COMPANY_AGENTS = ["ceo", "architect", "frontend", "backend", "qa", "reviewer"]
TERMINATION    = TextMentionTermination("TERMINATE")

MODEL_INFO = {
    "vision": False,
    "function_calling": False,
    "json_output": False,
    "family": "unknown",
    "structured_output": False,
}


# ─── Helpers ──────────────────────────────────────────────────
def _load_manifest(agent_key: str) -> dict:
    path = MANIFEST_DIR / f"{agent_key}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Company agent manifest not found: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _make_client(model: str) -> OllamaChatCompletionClient:
    return OllamaChatCompletionClient(
        model=model,
        host=OLLAMA_HOST,
        model_info=MODEL_INFO,
    )


def _make_agent(agent_key: str) -> AssistantAgent:
    m = _load_manifest(agent_key)
    return AssistantAgent(
        name=m.get("name", f"{agent_key}_agent"),
        model_client=_make_client(m.get("model", "nemotron-3-nano:latest")),
        system_message=m.get("system_prompt", "").strip(),
    )


def _extract_files(text: str) -> Dict[str, str]:
    """
    Parse agent output for file markers and extract file contents.
    Supports:
      // FILE: filename.ext   (JS style)
      # FILE: filename.ext    (Python style)
      --- FILE: filename.ext  (generic)
    Also extracts fenced code blocks with filename hints.
    """
    files: Dict[str, str] = {}

    # Pattern 1: explicit FILE markers
    marker_pattern = re.compile(
        r'(?://|#|---)\s*FILE:\s*(\S+)\s*\n(.*?)(?=(?://|#|---)\s*FILE:|\Z)',
        re.DOTALL
    )
    for m in marker_pattern.finditer(text):
        fname = m.group(1).strip()
        content = m.group(2).strip()
        # Strip surrounding fences if present
        content = re.sub(r'^```\w*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        files[fname] = content

    # Pattern 2: fenced blocks with filename in info string (```python:main.py)
    fence_pattern = re.compile(
        r'```(?:\w+:)?(\S+\.\w+)\n(.*?)```',
        re.DOTALL
    )
    for m in fence_pattern.finditer(text):
        fname = m.group(1).strip()
        if fname not in files:  # don't overwrite explicit markers
            files[fname] = m.group(2).strip()

    return files


def _save_files(session_id: str, files: Dict[str, str]) -> List[str]:
    """Write extracted files to outputs/<session_id>/ and return list of paths."""
    session_dir = OUTPUTS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for fname, content in files.items():
        # Sanitise filename
        safe = Path(fname).name
        fpath = session_dir / safe
        fpath.write_text(content, encoding="utf-8")
        saved.append(str(fpath))
        print(f"[company] wrote {fpath}")
    return saved


# ─── Main API ─────────────────────────────────────────────────
async def run_company(
    prompt: str,
    session_id: str = "default",
) -> Dict:
    """
    Run the full 6-agent software company pipeline.

    Returns:
        {
          "ship_report":  <reviewer's final message>,
          "conversation": [{"agent": ..., "content": ...}, ...],
          "files":        {"filename": "content", ...},
          "saved_paths":  ["/abs/path/to/file", ...],
        }
    """
    # Build agents
    agents = [_make_agent(k) for k in COMPANY_AGENTS]
    team   = RoundRobinGroupChat(
        participants=agents,
        termination_condition=TERMINATION,
    )

    # Run
    result = await team.run(task=prompt)

    # Parse transcript
    conversation = []
    all_files: Dict[str, str] = {}
    ship_report = ""

    for msg in result.messages:
        name    = getattr(msg, "source", "unknown")
        content = getattr(msg, "content", "")
        if not isinstance(content, str):
            content = str(content)

        conversation.append({"agent": name, "content": content})

        # Extract any code files from this message
        extracted = _extract_files(content)
        all_files.update(extracted)

        # Reviewer's message is the ship report
        if "reviewer" in name.lower():
            ship_report = content

    # Write files to disk
    saved = _save_files(session_id, all_files)

    return {
        "ship_report":  ship_report or conversation[-1]["content"] if conversation else "",
        "conversation": conversation,
        "files":        all_files,
        "saved_paths":  saved,
    }


async def stream_company(
    prompt: str,
    session_id: str = "default",
) -> AsyncGenerator[Dict, None]:
    """
    Stream company pipeline events for SSE.
    Yields dicts: {type, agent, content, files_extracted}
    Final event: {type: "done", ship_report, files, saved_paths}
    """
    agents = [_make_agent(k) for k in COMPANY_AGENTS]
    team   = RoundRobinGroupChat(
        participants=agents,
        termination_condition=TERMINATION,
    )

    all_files: Dict[str, str] = {}
    saved: List[str] = []
    ship_report = ""
    conversation = []

    async for event in team.run_stream(task=prompt):
        # Event types vary — handle TextMessage and TaskResult
        event_type = type(event).__name__

        if event_type == "TextMessage":
            name    = getattr(event, "source", "unknown")
            content = getattr(event, "content", "")
            if not isinstance(content, str):
                content = str(content)

            extracted = _extract_files(content)
            all_files.update(extracted)
            conversation.append({"agent": name, "content": content})

            if "reviewer" in name.lower():
                ship_report = content

            yield {
                "type":            "message",
                "agent":           name,
                "content":         content,
                "files_extracted": list(extracted.keys()),
            }

        elif event_type == "TaskResult":
            # Pipeline finished
            saved = _save_files(session_id, all_files)
            yield {
                "type":        "done",
                "ship_report": ship_report,
                "conversation": conversation,
                "files":       all_files,
                "saved_paths": saved,
            }
            return

    # Safety: emit done even if TaskResult never arrived
    if not saved:
        saved = _save_files(session_id, all_files)
    yield {
        "type":        "done",
        "ship_report": ship_report,
        "conversation": conversation,
        "files":       all_files,
        "saved_paths": saved,
    }
