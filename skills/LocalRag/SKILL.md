---
name: LocalRag
description: Query the local FAISS knowledge base built from project dependencies. USE WHEN user asks how a library works, what an API does, how to use a package, or any question about indexed dependencies. Issues targeted semantic queries — never loads full documents.
---

# LocalRag

Query the local FAISS vector store (built by `pipeline ingest`) for information about indexed dependency source code and documentation.

**Core principle:** issue multiple narrow queries and compose the answer from retrieved chunks. Never attempt to load or read entire indexed documents — the index exists precisely so context is retrieved on demand.

## MCP Dependency

Requires the `local-faiss-mcp` MCP server to be running or configured. The server exposes two tools:

- **`query_rag_store`** — semantic search, returns ranked chunks with similarity scores
- **`ingest_document`** — index new content (used by the pipeline, not this skill)

If the MCP server is not connected, tell the user to run:
```bash
uv run pipeline serve
# or configure it in .mcp.json (see tools/README.md)
```

## Workflow Routing

| Workflow | Trigger | File |
|----------|---------|------|
| **QueryKnowledge** | "how does X work", "what is X", "explain X", general library questions | `Workflows/QueryKnowledge.md` |
| **FindExamples** | "show me an example", "how do I use X", "example of X" | `Workflows/FindExamples.md` |
| **LookupApi** | "what methods does X have", "signature of X", "parameters for X" | `Workflows/LookupApi.md` |

## Examples

**Example 1: How a library works**
```
User: "How does httpx handle connection pooling?"
→ Invokes QueryKnowledge workflow
→ Queries: "httpx connection pooling", "httpx transport client pool"
→ Composes answer from top chunks
```

**Example 2: Usage example**
```
User: "Show me how to use pydantic validators"
→ Invokes FindExamples workflow
→ Queries: "pydantic validator example", "field_validator usage"
→ Returns concrete code examples from indexed source
```

**Example 3: API lookup**
```
User: "What parameters does httpx.Client accept?"
→ Invokes LookupApi workflow
→ Queries: "httpx Client __init__ parameters", "httpx Client constructor"
→ Returns signature and docstring chunks
```
