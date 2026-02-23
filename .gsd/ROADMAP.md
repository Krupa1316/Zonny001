# ROADMAP.md

> **Current Phase**: Phase 1
> **Milestone**: Zonny v0.3.0 — Multi-LLM Agent Platform + Web UI

## Must-Haves (from SPEC)

- [ ] AutoGen replaces custom runtime engine
- [ ] Multi-LLM per agent via manifest `model:` field
- [ ] Web chat UI served at localhost:8000
- [ ] Real-time agent activity streaming (SSE)
- [ ] New MCP server on AutoGen
- [ ] All legacy endpoints preserved

---

## Phases

### Phase 1: AutoGen Foundation
**Status**: 🔄 In Progress
**Objective**: Install AutoGen, wire it to Ollama, extend agent YAML manifests with `model:` field, and create the AutoGen team runner that replaces `runtime/engine.py`. Legacy endpoints must still work.
**Requirements**: AutoGen installed, per-agent model works, `POST /mcp` routes through AutoGen, event stream available

### Phase 2: Web Chat UI
**Status**: ⬜ Not Started
**Objective**: Build the premium web chat interface served by FastAPI at `/`. Three-panel layout: agent roster (left), chat + agent activity feed (center), agent detail sidebar (right). Real-time SSE powers the agent activity panel and pipeline visualization at the bottom.
**Requirements**: UI loads at localhost:8000, agent activity updates live, pipeline shows active agent, document upload works, API key input in settings

### Phase 3: New MCP Server
**Status**: ⬜ Not Started
**Objective**: Rebuild `mcp_server.py` on AutoGen. Expose the AutoGen agent team as MCP tools. Retire Claude Desktop dependency while keeping MCP protocol compatibility for any MCP client.
**Requirements**: `zonny-mcp` command starts the new server, at least 4 tools exposed, integrates with AutoGen team

### Phase 4: Polish & Integration
**Status**: ⬜ Not Started
**Objective**: Key management UI in the web interface (generate/list/revoke keys via `create_key.py`), agent manifest editor in the UI, README update, final smoke test of the complete system.
**Requirements**: Key gen works from UI, manifest model field editable, README reflects v0.3 architecture
