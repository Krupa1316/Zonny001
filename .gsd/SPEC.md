# SPEC.md — Zonny v0.3.0 Project Specification

> **Status**: `FINALIZED`

## Vision

Transform Zonny from a single-model CLI tool into a **multi-LLM collaborative agent platform** with a premium desktop-class web UI that makes AI agent teamwork visible and interactive. Each specialist agent runs its own optimal language model, and users can watch agents think, collaborate, and produce results in real time.

## Goals

1. **AutoGen Integration** — Replace the custom runtime (`runtime/engine.py`, `zonny/planner.py`, `zonny/executor.py`, `zonny/reflector.py`) with AutoGen v0.4 agent teams, gaining battle-tested orchestration, message streaming, and tool execution
2. **Multi-LLM Per Agent** — Each agent manifest specifies its own Ollama model; a `coder` agent can use `deepseek-coder`, a `planner` uses `llama3.2`, lightweight agents use `nemotron-3-nano`
3. **Web Chat UI** — A FastAPI-served web interface with: chat input, real-time agent activity panel (who is active/thinking/idle), message thread per agent, pipeline visualization (User → Planner → Coder → Final), and agent detail sidebar (current task, tool usage, activity log)
4. **New MCP Server** — Rebuilt on AutoGen, exposing Zonny's agent team as MCP tools; retire the Claude Desktop dependency but keep MCP protocol compatibility

## Non-Goals (Out of Scope for v0.3)

- Cloud LLM providers (OpenAI, Anthropic API) — local Ollama only for now
- Mobile UI
- Multi-user / auth beyond existing `key.json` mechanism
- Paid/SaaS features

## Users

Developers running Zonny locally who want to issue complex multi-step tasks to a team of specialized AI agents and observe the agents' reasoning, tool use, and collaboration in real time via a browser UI.

## Constraints

- All LLMs must run via local Ollama (`localhost:11434`) — zero cloud API cost
- FastAPI backend must remain the primary server (not replaced)
- Existing `key.json` / `create_key.py` auth mechanism is preserved
- Python ≥3.10, Windows-compatible
- AutoGen `autogen-agentchat` + `autogen-ext[ollama]` (MIT licensed, free)

## Success Criteria

- [ ] `pip install autogen-agentchat autogen-ext` installs without conflict
- [ ] At least 3 agents run with different Ollama models defined in their YAML manifests
- [ ] `POST /mcp` endpoint uses AutoGen teams instead of custom runtime
- [ ] Web UI accessible at `http://localhost:8000` in any browser
- [ ] Agent activity panel updates in real time as agents work (SSE streaming)
- [ ] Pipeline visualization shows active agent highlighted during execution
- [ ] New MCP server file (`mcp_server_v2.py`) exposes AutoGen team as tools
- [ ] All existing `/v1/chat/completions` and `/v1/upload` endpoints still work
