# Lorade

Tools to build and serve a local knowledge base for Claude Code and Open Code via MCP.

## Expected output

- Always keep up-to-date software references
- Reduce amount of tokens consumed

## Overview

The pipeline clones git repositories, compacts them with `gitingest`, indexes them into a local FAISS vector database, and serves the knowledge via MCP.

## Installation

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv sync
```

**Install the LocalRag skill** (Claude Code):

```bash
ln -s "$(pwd)/skills/LocalRag" ~/.claude/skills/LocalRag
```

**Configure MCP** so the skill can query the vector store — add to `~/.claude/mcp.json` or project-level `.mcp.json`:

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

For OpenCode, add to `~/.config/opencode/opencode.json`:

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

## Usage

### 1. Populate repos from project dependencies

Scan a project's dependencies and resolve them to GitHub URLs, appending to `repos.csv`:

```bash
# Python (reads pyproject.toml / requirements.txt)
uv run pipeline deps /path/to/python-project

# JavaScript (reads package.json)
uv run pipeline deps /path/to/js-project

# Resolve deps and immediately ingest
uv run pipeline deps /path/to/project --ingest
```

Or manually edit `repos.csv` — one git URL per line, `#` lines are ignored.

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

## LocalRag Skill

The `skills/LocalRag/` directory contains a Claude Code skill that queries the local vector store on demand — issuing targeted semantic searches instead of loading full documents. Three workflows are included:

| Workflow | Triggers |
|----------|----------|
| `QueryKnowledge` | conceptual questions — "how does X work" |
| `FindExamples` | usage questions — "show me an example of X" |
| `LookupApi` | signature lookups — "what parameters does X take" |

## Tools

- [gitingest](https://github.com/coderamp-labs/gitingest) — compacts a repo into a single LLM-readable file
- [local-faiss-mcp](https://github.com/nonatofabio/local_faiss_mcp) — local FAISS vector DB with MCP interface
