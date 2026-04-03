# LookupApi Workflow

Retrieve function signatures, class definitions, and parameter documentation from indexed source code.

## Principle

API lookups are precision queries — target the exact symbol name. A single well-formed query usually suffices; avoid over-querying for something with a known name.

## Steps

1. **Extract the exact symbol**
   - Identify: class name, function name, method name from the user's question
   - Normalise casing to match Python/JS conventions where possible

2. **Issue a tight primary query**
   - Use the exact symbol name as the query: `"httpx.Client"`, `"BaseModel.model_validate"`
   - `k=3` is enough for an API lookup — signatures are compact
   - If the first query returns low-score results (<0.4), try a broader form: `"Client class httpx"`

3. **Fallback query if needed**
   - Add `"def <name>"` or `"class <name>"` prefix — these strings appear literally in source
   - Example: `"def model_validate"`, `"class AsyncClient"`

4. **Extract the signature**
   - From the retrieved chunk, locate the `def`/`class` line and its docstring
   - Include the full parameter list and return type annotation if present
   - Note the source file path

5. **Present cleanly**
   - Show the signature with syntax highlighting
   - Include the docstring if available
   - Note the version/source repo from chunk metadata
   - If a parameter's meaning is unclear from the signature, include the relevant docstring section

## Output

The function/class signature, parameter types and defaults, return type, and docstring — sourced directly from indexed code.
