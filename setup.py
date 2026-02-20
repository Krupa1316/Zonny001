"""
Zonny Setup - Global CLI Installation
======================================

Architecture: v0.2.0
  - ReAct agent loop (Think → Act → Observe → Answer)
  - Semantic router  → routes intent to agent + task (NO tool names)
  - Dispatcher       → sole OS-touching component; path-safe; permission modes
  - Reflection loop  → evaluates quality, triggers retry on low confidence
  - Tool registry    → single source of truth; capability metadata on all tools
  - Agent manifests  → YAML definitions in agents/manifests/
  - MCP server       → Claude Desktop / MCP client integration
  - FastAPI server   → REST API + PDF ingest endpoint
  - Vector memory    → ChromaDB + sentence-transformers embeddings

Install globally (editable):
    pip install -e .

After installation the following commands are available everywhere:
    zonny           Launch the interactive CLI chat session
    zonny-server    Start the FastAPI REST server (port 8000)
    zonny-mcp       Start the MCP stdio server

Runtime requirements (NOT pip-installed — must be present on the system):
    Ollama          https://ollama.com  (model: nemotron-3-nano:latest)
    Git             optional; needed for git.status tool
"""

from setuptools import setup, find_packages

setup(
    name="zonny",
    version="0.2.0",
    description="Local AI Agent Runtime: ReAct loop, semantic router, dispatcher security, MCP server",
    long_description=open("README.md", encoding="utf-8").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="Zonny Team",
    python_requires=">=3.10",

    # ── Packages ────────────────────────────────────────────────────────────
    # find_packages() picks up: zonny/, agents/, tools/, commands/, runtime/
    packages=find_packages(exclude=["venv", "venv.*", "__pycache__"]),

    # Top-level .py modules that live outside any package
    py_modules=[
        "server",        # FastAPI REST server
        "orchestrator",  # RAG + memory orchestration
        "mcp_server",    # MCP stdio server
        "zonny",         # thin CLI shim (calls zonny.cli:main)
        "create_key",    # API-key generator utility
        "memory",        # standalone memory module (root-level)
    ],

    # Include non-Python files shipped with the packages
    include_package_data=True,
    package_data={
        # Agent YAML manifests
        "agents": ["manifests/*.yaml"],
    },

    # ── Dependencies ────────────────────────────────────────────────────────
    install_requires=[
        # Web framework & server
        "fastapi>=0.129.0",
        "uvicorn[standard]>=0.40.0",
        "python-multipart>=0.0.22",

        # HTTP client (Ollama calls, CLI → server calls)
        "requests>=2.32.0",

        # Data validation
        "pydantic>=2.12.0",

        # Vector memory
        "chromadb>=1.5.0",
        "sentence-transformers>=5.2.0",

        # PDF ingestion
        "pypdf>=6.7.0",

        # MCP server protocol
        "mcp>=1.26.0",
    ],

    # ── CLI Entry Points ─────────────────────────────────────────────────────
    entry_points={
        "console_scripts": [
            # Interactive chat CLI  →  type 'zonny' anywhere
            "zonny=zonny.cli:main",

            # FastAPI REST server  →  type 'zonny-server' anywhere
            "zonny-server=zonny.server_entry:start",

            # MCP stdio server     →  type 'zonny-mcp' anywhere
            "zonny-mcp=zonny.mcp_entry:start",
        ],
    },

    # ── Metadata ─────────────────────────────────────────────────────────────
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
    ],
    keywords="ai agent llm ollama react-loop mcp fastapi local",
)
