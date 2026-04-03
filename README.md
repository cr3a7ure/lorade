# Claude/Open Code Tools

Tools to build and serve a local knowledge base for Claude Code and Open Code via MCP.

## Overview

The pipeline clones git repositories, compacts them with `gitingest`, indexes them into a local FAISS vector database, and serves the knowledge via MCP.

## Setup

```bash
uv sync
```

## Usage

### 1. Add repos

Edit `repos.csv` — one git URL per line, lines starting with `#` are ignored:

```
https://github.com/anthropics/anthropic-sdk-python
https://github.com/openai/openai-python
```

### 2. Ingest

Clones repos (main/master), runs `gitingest` on each, and indexes everything into FAISS:

```bash
uv run pipeline ingest repos.csv
```

Produces:
- `repos/<name>/` — cloned repositories
- `ingested/<name>.txt` — gitingest compacted output
- `.vector_store/` — FAISS index

### 3. Refresh

Pulls latest changes in all cloned repos and re-indexes:

```bash
uv run pipeline refresh
```

### 4. Serve via MCP

Starts the `local-faiss-mcp` server against the local vector store:

```bash
uv run pipeline serve
```

Or configure it permanently in your MCP settings:

**Claude Code** — `~/.claude/mcp.json` or project-level `.mcp.json`:

```json
{
  "mcpServers": {
    "local-faiss-mcp": {
      "command": "/path/to/tools/.venv/bin/local-faiss-mcp",
      "args": ["--index-dir", "/path/to/tools/.vector_store"]
    }
  }
}
```

**OpenCode** — `~/.config/opencode/opencode.json` (global) or `opencode.json` in project root:

```json
{
  "mcp": {
    "local-faiss-mcp": {
      "type": "local",
      "command": ["/path/to/tools/.venv/bin/local-faiss-mcp", "--index-dir", "/path/to/tools/.vector_store"],
      "enabled": true
    }
  }
}
```

## Tools

- [gitingest](https://github.com/coderamp-labs/gitingest) — compacts a repo into a single LLM-readable file
- [local-faiss-mcp](https://github.com/nonatofabio/local_faiss_mcp) — local FAISS vector DB with MCP interface
