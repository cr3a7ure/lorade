# FindExamples Workflow

Retrieve concrete usage examples for a library or API from the indexed source code.

## Principle

Source code repos indexed via `gitingest` contain tests, examples, and docstrings — these are the best source of usage patterns. Target those specifically rather than querying generically.

## Steps

1. **Identify what to find**
   - Library name + the specific feature/class/function the user wants an example of

2. **Query with example-biased terms**
   - Prefer terms likely to appear in tests or example files:
     - `"<library> <feature> example"`
     - `"<ClassName> usage"`
     - `"test <function_name>"` — test files often show canonical usage
     - `"<function> quickstart"` or `"<function> tutorial"`
   - Issue 2–3 queries with `k=5`

3. **Check similarity scores**
   - Below 0.3: likely not indexed. Suggest `pipeline deps <project>` to add the library.
   - 0.3–0.6: partial match — include with caveat
   - Above 0.6: strong match — use directly

4. **Present examples**
   - Show the code chunk as-is with syntax highlighting
   - Include the source file path from chunk metadata
   - If multiple equivalent examples are found, prefer the one from `tests/` or `examples/` directories (more likely to be idiomatic)

5. **If nothing found**
   - Check which repos are indexed: the user can run `pipeline ingest repos.csv` to see what's available
   - Suggest adding the missing package via `pipeline deps <project_path>`

## Output

Runnable code examples sourced directly from the indexed repositories, with file attribution.
