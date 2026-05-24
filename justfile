# Neo4j database recipes

# Delete and re-create the target database
reset:
    uv run scripts/db_reset.py --json

# ── Python toolchain ────────────────────────────────────────────────────────

# Install / sync all dependencies (including dev)
sync:
    uv sync

# Lint and auto-fix with ruff
lint:
    uv run ruff check --fix .
    uv run ruff format .

# Type-check with pyright
typecheck:
    uv run pyright .

# Run the test suite (exit 5 = no tests collected, treated as success)
test:
    uv run pytest -x --tb=short || [ "$?" = "5" ]

# Full pre-commit gate: lint → typecheck → test (required before every commit)
check: lint typecheck test
