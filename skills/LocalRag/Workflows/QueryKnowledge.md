# QueryKnowledge Workflow

Answer conceptual questions about indexed libraries using targeted semantic queries.

## Principle

Do **not** load full documents. Each `query_rag_store` call returns the most relevant chunks for that specific query. Build the answer by composing multiple narrow queries.

## Steps

1. **Identify the subject and scope**
   - Extract the library name and the specific concept from the user's question
   - If ambiguous, clarify before querying

2. **Decompose into 2–4 targeted queries**
   - Each query should target a distinct facet of the question
   - Examples for "how does httpx handle retries?":
     - `"httpx retry transport"`
     - `"httpx HTTPTransport retries"`
     - `"httpx Retry configuration"`
   - Prefer concrete technical terms over vague descriptions

3. **Call `query_rag_store` for each query**
   - Use `k=5` (top 5 chunks) per query — enough signal, minimal noise
   - Note the similarity scores: chunks below ~0.3 are likely off-topic, discard them
   - If all scores are low (<0.3), the topic is probably not indexed — tell the user

4. **Deduplicate and rank chunks**
   - Merge results across queries, drop exact duplicates
   - Prefer chunks with higher similarity scores
   - Keep 5–8 most relevant chunks total

5. **Compose the answer**
   - Synthesise from the retrieved chunks
   - Cite the source (file path / repo) from chunk metadata when available
   - If chunks are insufficient, state what was found and suggest running `pipeline deps` to index the missing library

## Output

A clear answer grounded in the retrieved source code or docs, with source references where available.
