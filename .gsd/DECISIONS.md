# DECISIONS.md — Architecture Decision Log

> Auto-created by /map on 2026-02-23

| ID | Decision | Date | Rationale | Status |
|----|---------|------|-----------|--------|
| ADR-001 | Use Ollama as local LLM host | - | Privacy, offline operation, no API costs | Accepted |
| ADR-002 | ChromaDB as vector store | - | Embedded, no separate server needed | Accepted |
| ADR-003 | Dual-mode routing (router vs planner) | - | Simple queries go fast; complex queries get planning | Accepted |
| ADR-004 | YAML manifests for agent definitions | - | Hot-reloadable, decoupled from code | Accepted |
