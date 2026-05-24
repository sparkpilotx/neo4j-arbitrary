# Repository-scope Agent Instructions

## Your Identify
You are the agent called **Repo-Agent**.

## Tooling & Execution Principles
- Use `just` as the project-level recipe facade. 
- **Discovery First**: Always run `just --list` to discover existing recipes before running project workflows or creating new scripts.
- **Trust the Tooling**: Do not perform manual pre-checks (e.g., shell loops for env vars) before executing a recipe. Trust the local recipes and tools to fail-fast and report errors themselves.
- Do not change tooling configurations unless explicitly requested by a human.

## Shell Scripting Policy
- Keep all shell scripts compatible with **Ubuntu 24.04** and **macOS Tahoe 26** only. Do not account for other platforms. Use commands, flags, and shell features that work on both target systems unless a script explicitly documents a narrower runtime.

## IDE
- VS Code is the only supported IDE. Do not generate configuration or settings for any other editor (JetBrains, Vim, etc.).

## Python Policy
- Target Python 3.12 only. Do not add compatibility code, syntax constraints, or test branches for other versions.
- Use `uv` as the package manager.

## Neo4j
<neo4j-instance-profile>
- Instance Version: Neo4j Enterprise 2026.04.0
- Cypher Language: [CYPHER 25](https://neo4j.com/docs/cypher-manual/25/introduction/)
- Environmental variables: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- Installed Plugins
  - **APOC** [`apoc-2026.04.0-core.jar`](https://neo4j.com/docs/apoc/2026.04/introduction/)
  - **Graph Data Science** [`neo4j-graph-data-science-2026.04.0.jar`](https://neo4j.com/docs/graph-data-science/current/introduction/)
  - **GenAI Plugin** [`neo4j-genai-plugin-2026.04.0.jar`](https://neo4j.com/docs/genai/plugin/current/)
    - **Text Embedding Model**: Environmental variable `OPENAI_API_KEY` and `OPENAI_TEXT_EMBEDDING_MODEL`
    - Use `ai.text.embedBatch` and `ai.text.embed.providers` — the `genai.vector.*` equivalents are deprecated in this version.
</neo4j-instance-profile>
