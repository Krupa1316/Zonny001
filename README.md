```
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   ███████╗ ██████╗ ███╗   ██╗███╗   ██╗██╗   ██╗                     ║
║   ╚══███╔╝██╔═══██╗████╗  ██║████╗  ██║╚██╗ ██╔╝                     ║
║     ███╔╝ ██║   ██║██╔██╗ ██║██╔██╗ ██║ ╚████╔╝                      ║
║    ███╔╝  ██║   ██║██║╚██╗██║██║╚██╗██║  ╚██╔╝                       ║
║   ███████╗╚██████╔╝██║ ╚████║██║ ╚████║   ██║                        ║
║   ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═══╝   ╚═╝                        ║
║                                                                      ║
║                    Welcome to the zone                               ║
╚══════════════════════════════════════════════════════════════════════╝
```

# Zonny — Local AI Agent Runtime

Zonny is a fully **local, privacy-first AI agent runtime** that runs powerful coding and reasoning agents entirely on your own machine. No cloud. No subscription. No data leaving your system.

Built on top of [Ollama](https://ollama.com), Zonny implements the same **ReAct (Reason + Act)** loop architecture found in Gemini CLI and Claude Code — semantic routing, secure dispatching, reflection, vector memory, MCP protocol support, and a REST API — all running locally.

---

## Table of Contents

- [Why Zonny?](#why-zonny)
- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [REST API Reference](#rest-api-reference)
- [MCP Integration](#mcp-integration)
- [Permission Modes](#permission-modes)
- [Agent Manifests](#agent-manifests)
- [Tool Registry](#tool-registry)
- [Memory System](#memory-system)
- [Diagnostics](#diagnostics)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Why Zonny?

Most AI coding agents require cloud connectivity and send your code to external servers. Zonny takes a different approach:

| Feature | Zonny | Cloud Agents |
|---------|-------|-------------|
| Runs locally | ✅ | ❌ |
| Your data stays local | ✅ | ❌ |
| Works offline | ✅ | ❌ |
| MCP protocol | ✅ | Some |
| ReAct loop | ✅ | Some |
| Vector memory | ✅ | Some |
| Free to run | ✅ | Often paid |

---

## Architecture Overview

Zonny is built in layers. Each layer has a single, well-defined responsibility.

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                         │
│         Terminal CLI (zonny)  ·  Web UI (chat)              │
└──────────────────────┬──────────────────────────────────────┘
                       │  HTTP / Zonny Protocol v1
┌──────────────────────▼──────────────────────────────────────┐
│                   MCP Gateway  (server.py)                  │
│         FastAPI · Auth · Session Management · MCP           │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│               Semantic Router  (zonny/semantic_router.py)   │
│    Routes intent → selects Agent + Task (no tool names)     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│               ReAct Loop  (zonny/react_loop.py)             │
│  Think → Act → Observe → Think → Act → Observe → Answer    │
│                   (up to 50 iterations)                     │
└──────────┬───────────────────────────┬──────────────────────┘
           │                           │
┌──────────▼──────────┐    ┌───────────▼───────────────────── ┐
│   Planner           │    │   Dispatcher  (dispatcher.py)    │
│   (planner.py)      │    │   The ONLY component that        │
│   Decides ONE       │    │   touches the OS/filesystem.     │
│   action at a time  │    │   Path-safe, permission-gated.   │
└──────────┬──────────┘    └───────────┬────────────────────── ┘
           │                           │
┌──────────▼──────────────────────────▼──────────────────────┐
│                     Tool Registry                           │
│   filesystem · workspace · code · shell · memory · git     │
└─────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│             Memory Layer  (zonny/memory.py)                 │
│        ChromaDB Vector Store · SentenceTransformers         │
└─────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│               Ollama  (local LLM)                           │
│            nemotron-3-nano:latest  (default)                │
└─────────────────────────────────────────────────────────────┘
```

### Core Loop — ReAct

Unlike static plan-then-execute systems, Zonny uses a reactive loop:

```
Query
  └─► Think   (planner decides a single action)
        └─► Act      (dispatcher executes it securely)
              └─► Observe  (result fed back into world state)
                    └─► Think   (loop continues...)
                          └─► Answer  (done=true → return)
```

No assumptions. No static plans. Each step is decided using the full current context.

---

## Features

- **ReAct Loop** — Adaptive reasoning: Think → Act → Observe until the answer is ready
- **Semantic Router** — Understands intent and routes to the correct agent without exposing tool names
- **Secure Dispatcher** — The one component that touches the OS; enforces path safety and permission modes
- **Reflection Loop** — Evaluates answer confidence; retries on low-quality responses
- **Tool Registry** — Single source of truth for all available tools with capability metadata
- **Agent Manifests** — Agents defined in YAML; easy to add new agents without changing code
- **Vector Memory** — ChromaDB + SentenceTransformers for semantic retrieval across sessions
- **FastAPI Server** — REST API with API key auth, PDF ingestion, chat endpoint
- **MCP Server** — stdio MCP server for Claude Desktop integration
- **Permission Modes** — `safe` (read-only), `dev` (read+write), `full` (all ops)
- **PDF Document Ingestion** — Upload PDFs and query them with your agent
- **Multi-session Support** — Sessions are isolated with per-session context
- **Workspace Awareness** — Scans project structure, generates reports, tracks file trees

---

## Project Structure

```
zonny/                          # Core agent runtime package
│
├── cli.py                      # Interactive terminal UI (entry point: zonny)
├── react_loop.py               # The ReAct Think→Act→Observe engine
├── planner.py                  # Decision engine: makes ONE decision per step
├── executor.py                 # Executes the chosen action
├── dispatcher.py               # Secure OS interface (path safety, permissions)
├── router.py                   # Task-level routing within an agent
├── semantic_router.py          # High-level intent → agent+task routing
├── reflector.py                # Evaluates answer quality, triggers retries
├── world.py                    # Immutable world state passed through the loop
├── tool_registry.py            # Central registry of all tools + capabilities
├── memory.py                   # ChromaDB vector store interface
├── runtime.py                  # Runtime configuration and globals
├── agent.py                    # Base agent definition
├── server_entry.py             # Entry point for zonny-server command
├── mcp_entry.py                # Entry point for zonny-mcp command
└── __init__.py
│
agents/                         # Agent definitions
├── manifests/                  # YAML agent manifests
│   ├── assistant.yaml          #   General-purpose assistant agent
│   ├── codebase.yaml           #   Codebase analysis & editing agent
│   ├── document.yaml           #   PDF document Q&A agent
│   ├── generalist.yaml         #   Generalist fallback agent
│   └── memory.yaml             #   Memory management agent
├── base.py                     # Base agent class
├── code.py                     # Code-specific agent logic
├── docs.py                     # Document agent logic
├── general.py                  # General agent logic
├── memory.py                   # Memory agent logic
├── planner_agent.py            # Planning subagent
├── agent_factory.py            # Creates agent instances from manifests
├── manifest_loader.py          # Loads & validates YAML manifests
├── registry.py                 # Agent registry
├── router.py                   # Agent-level router
└── __init__.py
│
tools/                          # Tool implementations
├── fs.py                       # Filesystem: read, write, list, search files
├── workspace.py                # Workspace: scan, tree, git status
├── analyzer.py                 # Code analysis & report generation
├── shell.py                    # Shell command execution (full mode only)
├── memory_tool.py              # Memory query/store tool
├── vector_tool.py              # Vector search tool
├── file_tool.py                # Extended file operations
├── runner.py                   # Command runner
├── registry.py                 # Tool registry implementation
└── __init__.py
│
commands/                       # CLI command handlers
├── system.py                   # System commands (/help, /agents, etc.)
└── __init__.py
│
runtime/                        # Runtime utilities
├── base.py                     # Base runtime classes
├── context.py                  # Context management
├── engine.py                   # Runtime engine
├── registry.py                 # Runtime registry
├── subagent.py                 # Subagent spawning
└── __init__.py
│
server.py                       # FastAPI REST server (MCP Gateway)
mcp_server.py                   # MCP stdio server (Claude Desktop)
orchestrator.py                 # RAG + memory orchestration layer
memory.py                       # Root-level memory (used by orchestrator)
zonny.py                        # CLI shim (calls zonny.cli:main)
create_key.py                   # API key generator utility
zonny_status.py                 # Full diagnostic test suite (35 tests)
setup.py                        # Package setup (pip install -e .)
requirements.txt                # Python dependencies
```

---

## Prerequisites

Before installing Zonny, make sure you have:

### 1. Python 3.10+
```bash
python --version   # should be 3.10 or higher
```

### 2. Ollama (required — runs the LLM locally)

Download from [https://ollama.com](https://ollama.com), then pull the default model:

```bash
ollama pull nemotron-3-nano:latest
```

Zonny works with any Ollama model. The model can be changed in `zonny/runtime.py` and `orchestrator.py`.

### 3. Git (optional, for git tools)
```bash
git --version
```

---

## Installation

### Quick Install (Global — Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/your-username/zonny.git
cd zonny

# 2. Install in editable mode — makes zonny, zonny-server, zonny-mcp available everywhere
pip install -e .
```

After installation, three commands are available system-wide:

| Command | Description |
|---------|-------------|
| `zonny` | Launch the interactive CLI |
| `zonny-server` | Start the FastAPI REST server on port 8000 |
| `zonny-mcp` | Start the MCP stdio server |

### Development Install (Virtual Environment)

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run directly
python zonny.py
```

---

## Configuration

### API Key

Generate an API key for the REST server:

```bash
python create_key.py
```

This creates (or appends to) `key.json` with a new key in the format `sk-local-<hex>`.

**Never commit `key.json` to git.** It is in `.gitignore` by default.

### Permission Mode

Control what the agent is allowed to do by setting the `ZONNY_MODE` environment variable:

```bash
# Windows
set ZONNY_MODE=dev     # default: read + write to code files

# macOS/Linux
export ZONNY_MODE=dev
```

See [Permission Modes](#permission-modes) for details.

### Model

The default model is `nemotron-3-nano:latest`. To change it, edit the `MODEL` constant in:
- `orchestrator.py`
- `zonny/runtime.py` (if present)

Any model available in your local Ollama installation works.

---

## Usage

### Interactive CLI

Make sure Ollama is running (`ollama serve`), then:

```bash
zonny
```

You'll see the Zonny banner. Type a message to start chatting, or use commands:

```
/agents    List available agents and their capabilities
/help      Show command reference
/exit      Exit Zonny
```

**Example prompts:**
```
> go through this project and explain what it does
> read package.json and tell me the dependencies
> write a function that parses JSON from a file
> what files are in the src/ directory?
```

### Start the REST Server

```bash
zonny-server
# or
python -m uvicorn server:app --reload --port 8000
```

The server starts at `http://127.0.0.1:8000`. See [REST API Reference](#rest-api-reference) for endpoints.

### Start the MCP Server

```bash
zonny-mcp
# or
python mcp_server.py
```

See [MCP Integration](#mcp-integration) for Claude Desktop configuration.

### Running from a Specific Directory

Point Zonny at any project directory:

```bash
cd /path/to/your/project
zonny
```

Zonny uses the current working directory as the workspace root. All file operations are sandboxed to this directory.

---

## REST API Reference

Base URL: `http://127.0.0.1:8000`

All endpoints (except `/`) require an `Authorization` header with an API key from `key.json`.

### Health Check

```http
GET /
```

```json
{ "status": "ok" }
```

### MCP Gateway (Main Agent Endpoint)

```http
POST /mcp
Authorization: sk-local-<your-key>
Content-Type: application/json

{
  "session": "uuid-string",
  "input": "your message here"
}
```

Response:
```json
{
  "response": "Agent's answer",
  "session": "uuid-string"
}
```

### Chat (legacy RAG endpoint)

```http
POST /v1/chat
Authorization: sk-local-<your-key>
Content-Type: application/json

{
  "messages": [
    { "role": "user", "content": "Your question" }
  ],
  "conversation_id": "my-session",
  "document_id": "optional-doc-id"
}
```

### Upload PDF Document

```http
POST /v1/upload
Authorization: sk-local-<your-key>
Content-Type: multipart/form-data

file: <binary PDF>
```

Response:
```json
{
  "document_id": "doc-uuid",
  "chunks": 42,
  "message": "Document indexed successfully"
}
```

### List Agents

```http
GET /agents
Authorization: sk-local-<your-key>
```

---

## MCP Integration

Zonny includes a full [Model Context Protocol](https://modelcontextprotocol.io) server, allowing it to be used as a tool source in Claude Desktop and any MCP-compatible client.

### Claude Desktop Configuration

Add this to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "zonny": {
      "command": "python",
      "args": ["path/to/zonny/mcp_server.py"]
    }
  }
}
```

Or if using the globally installed command:

```json
{
  "mcpServers": {
    "zonny": {
      "command": "zonny-mcp"
    }
  }
}
```

### Available MCP Tools

Once connected, Claude Desktop can use:

| Tool | Description |
|------|-------------|
| `ask_agent` | Send a task to Zonny's ReAct agent |
| `read_file` | Read a file from the workspace |
| `list_files` | List files and directories |
| `search_files` | Search file contents by pattern |
| `write_file` | Write or modify a file |
| `run_command` | Execute a shell command (full mode) |
| `query_memory` | Search the vector memory store |

---

## Permission Modes

Zonny uses a three-tier permission system controlled by the `ZONNY_MODE` environment variable:

| Mode | Read Files | Write Files | Shell Commands | Use Case |
|------|-----------|------------|----------------|----------|
| `safe` | ✅ | ❌ | ❌ | Production, exploratory tasks |
| `dev` | ✅ | ✅ (restricted extensions) | ❌ | Development (default) |
| `full` | ✅ | ✅ (all) | ✅ | Advanced / trusted environments |

In `dev` mode, the following extensions are writable:

```
.py .js .ts .jsx .tsx .html .css .scss
.json .yaml .yml .toml .md .txt .sh .env.example
```

The following are **always blocked** regardless of mode:

```
.exe .dll .so .bin .env .key .pem .cert .p12
```

---

## Agent Manifests

Agents are defined in YAML files under `agents/manifests/`. Each manifest declares the agent's identity, capabilities, and routing behavior.

**Example (`agents/manifests/codebase.yaml`):**

```yaml
name: codebase
display_name: Codebase Agent
description: Analyzes, navigates, and edits codebases
capabilities:
  - read_files
  - write_files
  - analyze_code
  - search_workspace
tasks:
  - explain
  - summarize
  - edit
  - refactor
  - debug
priority: high
```

To add a new agent, create a new YAML manifest and the corresponding Python module in `agents/`.

---

## Tool Registry

All tools register themselves with the central registry (`zonny/tool_registry.py`). This is the single source of truth — the router, dispatcher, and reflection system all reference it.

Each tool entry includes:
- **Name** — unique identifier
- **Description** — what the tool does (used by the planner)
- **Capability tags** — what class of operation this tool performs
- **Permission requirements** — minimum mode required

The dispatcher enforces registry validation: **if a tool is not in the registry, it cannot be executed.**

---

## Memory System

Zonny uses a two-layer memory system:

### 1. In-Session Memory (World State)
During a ReAct loop, `world.knowledge` accumulates everything observed: file listings, file contents, analysis results, etc. This is ephemeral — it resets when the loop ends.

### 2. Persistent Vector Memory (ChromaDB)
Conversations and document chunks are stored as embeddings in ChromaDB using `sentence-transformers/all-MiniLM-L6-v2` (running on CPU). This persists across sessions and is queryable semantically.

**Operations:**
```python
# Store a message
store_message(role, content, conversation_id)

# Retrieve relevant memory
retrieve_memory(query, conversation_id, top_k=5)

# Store document chunks
store_text_blocks(blocks, document_id)
```

The vector store lives in `chroma_db/` in the project directory. This is excluded from git.

---

## Diagnostics

Run the full test suite to verify your installation:

```bash
python zonny_status.py
```

This runs 35 checks across all system components:

- Ollama connectivity & model availability
- All package imports
- Tool registry integrity
- Agent manifest loading
- Semantic router
- ReAct loop execution
- Dispatcher security (path traversal, extension blocking)
- Permission mode enforcement
- Memory subsystem
- FastAPI server health
- MCP protocol

Expected output:
```
✅ Passed: 35/35  |  Score: 100%  |  🎉 All systems nominal.
```

---

## Contributing

Contributions are welcome. Zonny is structured to make extension easy:

### To add a new tool
1. Create `tools/your_tool.py` with a function
2. Register it in `zonny/tool_registry.py`
3. Import it in `tools/__init__.py`

### To add a new agent
1. Create `agents/manifests/your_agent.yaml`
2. Create `agents/your_agent.py` with the agent logic
3. Register it in `agents/registry.py`

### To add a new API endpoint
1. Add the route to `server.py`
2. Add a corresponding MCP tool in `mcp_server.py` if needed

### Code style
- Follow existing patterns in each module
- Keep each file focused on a single responsibility
- Add docstrings to public functions
- Test with `python zonny_status.py` before submitting

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM Runtime | [Ollama](https://ollama.com) |
| Default Model | nemotron-3-nano:latest |
| REST Framework | [FastAPI](https://fastapi.tiangolo.com) |
| ASGI Server | [Uvicorn](https://www.uvicorn.org) |
| Vector Store | [ChromaDB](https://www.trychroma.com) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| MCP Protocol | [mcp Python SDK](https://github.com/modelcontextprotocol/python-sdk) |
| PDF Parsing | pypdf |
| Python | ≥ 3.10 |

---

## Roadmap

Zonny is actively evolving. The following features are planned for upcoming releases. Each item below represents a meaningful architectural expansion — not incremental tweaks — and is scoped to ensure Zonny remains cohesive, well-tested, and production-ready.

---

### 1. Multi-Provider LLM Support (Cloud API Integration)

**Priority: High | Target: v0.3.0**

Zonny is currently built around Ollama for fully local execution. The next major milestone is adding first-class support for **Anthropic Claude**, **Google Gemini**, and **OpenAI GPT** as swappable LLM backends — while keeping local Ollama as the default.

#### What will be built

- A unified `LLMProvider` abstraction layer in `zonny/providers/` that normalises the request/response contract across all backends:
  ```
  zonny/providers/
  ├── base.py          # Abstract LLMProvider interface
  ├── ollama.py        # Current Ollama backend (refactored in)
  ├── openai.py        # OpenAI GPT-4o, GPT-4.1, o3, o4-mini
  ├── anthropic.py     # Claude 3.5 Sonnet, Claude 4 Sonnet/Opus
  ├── gemini.py        # Gemini 2.0 Flash, Gemini 2.5 Pro
  └── registry.py      # Provider selection & fallback logic
  ```
- API key management via environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) with optional encrypted storage in a local keychain
- A provider config section in `.zonny.json` (project-level) and `~/.zonny/config.json` (global):
  ```json
  {
    "provider": "anthropic",
    "model": "claude-sonnet-4-5",
    "fallback_provider": "ollama",
    "fallback_model": "nemotron-3-nano:latest"
  }
  ```
- Automatic fallback: if the cloud provider is unreachable (no key, rate-limited, network error), Zonny falls back to the configured local Ollama model — keeping the agent functional offline
- Per-session provider override: `zonny --provider openai --model gpt-4o`
- Streaming support across all providers so terminal output remains responsive on long responses
- Token usage tracking and cost estimation per session (printed in verbose mode)

#### Why this matters

Developers working on sensitive internal code can stay fully local. Developers who want frontier reasoning on complex tasks (long context analysis, architecture review, refactoring large codebases) can switch to a cloud provider without changing workflows or commands.

---

### 2. Web Dashboard

**Priority: High | Target: v0.4.0**

The current Zonny interface is terminal-only. While the CLI is intentional and will remain the primary interface, a **browser-based dashboard** will make Zonny accessible to developers who prefer a visual environment and enable use cases that the CLI cannot serve well (conversation history browsing, document management, live session monitoring).

#### What will be built

- A self-hosted web UI served directly by `zonny-server` (no separate process needed), accessible at `http://localhost:8000/ui`
- Built with a lightweight frontend stack (likely **React + Vite + TailwindCSS**) compiled to a static bundle and embedded in the Python package

**Dashboard panels:**

| Panel | Description |
|-------|-------------|
| **Chat** | Full-featured chat interface — send messages, view streamed agent responses, see tool call logs inline |
| **Sessions** | Browse, search, resume, rename, and delete past sessions. Session summaries shown alongside. |
| **Documents** | Upload, manage, and query PDFs and text files ingested into the vector store |
| **Memory** | View and edit the persistent vector memory — browse stored facts, delete entries, add manual notes |
| **Agent Monitor** | Live view of the ReAct loop as it executes — each Think/Act/Observe step visible in real time |
| **Provider Settings** | Configure LLM provider, model, API keys, and permission mode without editing config files |
| **Tool Log** | Per-session audit log of every tool the agent invoked, with inputs, outputs, and timing |

- WebSocket endpoint (`/ws/session/{id}`) for live streaming of agent loop steps to the dashboard
- Dark mode by default; system-preference aware
- Fully functional without JavaScript (graceful degradation) for accessibility

#### Why this matters

The dashboard lowers the barrier to entry for developers new to agent runtimes, makes session management practical at scale, and turns Zonny into a tool that non-terminal users (designers, PMs, QA engineers) can also use productively.

---

### 3. Automated Code Review Agent (PR Review)

**Priority: Medium | Target: v0.5.0**

Zonny will gain a dedicated **Code Review Agent** — a specialised agent that performs deep, context-aware analysis of code changes and delivers structured pull request reviews. This is more than a linting wrapper: it uses the full ReAct loop to reason about the intent of a change, cross-reference it against the existing codebase, and produce actionable, prioritised feedback.

#### What will be built

- A new agent manifest and implementation (`agents/manifests/reviewer.yaml`, `agents/reviewer.py`)
- A `zonny review` CLI command:
  ```bash
  # Review uncommitted changes
  zonny review

  # Review a specific branch against main
  zonny review --branch feature/my-feature --base main

  # Review a GitHub PR by URL
  zonny review --pr https://github.com/org/repo/pull/42

  # Output as JSON for CI integration
  zonny review --format json > review.json
  ```
- A new `tools/git_diff.py` tool that extracts structured diffs (file path, hunk, context lines, added/removed line counts)
- A `tools/github.py` tool for authenticated GitHub API access — fetching PR metadata, posting comments, and requesting changes programmatically

**Review output structure** (Markdown and JSON):
```
## Code Review — feature/auth-refactor

### Summary
This PR refactors the authentication layer from session-based to JWT. The
logic is sound but several edge cases and security considerations need
addressing before merge.

### Issues Found

#### 🔴 Critical (1)
- **`auth/jwt.py:47`** — JWT secret falls back to a hardcoded string when
  `JWT_SECRET` env var is unset. This will silently use an insecure default
  in production. Require the env var or raise on startup.

#### 🟡 Warnings (3)
- **`auth/middleware.py:23`** — Token expiry is not validated on refresh.
  An expired token can be refreshed indefinitely.
- **`tests/test_auth.py`** — No test covers the token expiry path.
- **`api/routes.py:89`** — `user_id` extracted from token is not validated
  against the database before use. Could allow access with a valid token for
  a deleted user.

#### 🔵 Suggestions (2)
- Consider extracting token validation into a shared utility to avoid
  duplication across middleware and route guards.
- The `logout` endpoint does not invalidate the token server-side.
  Consider a token denylist for sensitive deployments.

### Test Coverage Delta
Lines added: 312 | Lines with tests: 189 | Coverage delta: -4.2%
Recommendation: Add tests for the expiry and refresh paths.
```

- **CI/CD integration**: Output a non-zero exit code when critical issues are found, making `zonny review` usable as a GitHub Actions step or pre-merge gate
- **GitHub Actions workflow template** included in the repo under `.github/workflows/zonny-review.yml`
- Context-awareness: the agent reads the full codebase (not just the diff) to reason about whether a change is consistent with existing patterns, introduces regressions, or conflicts with other modules
- Review depth configurable: `--depth quick` (diff only) | `--depth standard` (diff + affected files) | `--depth full` (diff + full codebase context)

#### Why this matters

Code review is one of the highest-leverage activities in software development and also one of the most time-consuming. A local, privacy-preserving review agent means internal code never leaves the machine during review, the model can be tuned to the team's specific standards via the agent manifest, and junior developers get structured feedback immediately — before waiting for a human reviewer.

---

### Release Timeline

| Version | Feature | Status |
|---------|---------|--------|
| v0.2.0 | ReAct loop, semantic router, dispatcher security, reflection, tool registry, MCP server | ✅ Released |
| v0.3.0 | Multi-provider LLM support (OpenAI, Anthropic, Gemini) + API key management | 🔜 Planned |
| v0.4.0 | Web dashboard (chat UI, session management, document manager, live agent monitor) | 🔜 Planned |
| v0.5.0 | Code Review Agent (PR review, GitHub integration, CI/CD support) | 🔜 Planned |
| v0.6.0 | Persistent SQLite session storage (conversation history that survives restarts) | 🔜 Planned |

> Feature priorities and timelines may shift based on community feedback. Open an issue to vote on or discuss any roadmap item.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

> Built for developers who want the power of modern AI agents without giving up their privacy or their code.
