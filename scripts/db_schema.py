"""Apply schema constraints and indexes to the target database."""

import argparse
import json
import os
import sys
from enum import StrEnum
from typing import LiteralString, cast

import structlog
from neo4j import Driver, GraphDatabase
from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Shared error types
# ---------------------------------------------------------------------------


class ErrorCode(StrEnum):
    EXTERNAL = "EXTERNAL"
    VALIDATION = "VALIDATION"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        context: dict[str, object] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context: dict[str, object] = context or {}
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, object]:
        return {
            "error": str(self.code),
            "message": self.message,
            "context": self.context,
            **({"suggestion": self.suggestion} if self.suggestion else {}),
        }


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class DbConfig(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    uri: str
    user: str
    password: str
    database: str


def load_config() -> DbConfig:
    keys = ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE")
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        ctx: dict[str, object] = {"missing": missing}
        raise AppError(
            ErrorCode.VALIDATION,
            "Missing required environment variables",
            context=ctx,
            suggestion=f"Export {', '.join(missing)} before running.",
        )
    return DbConfig(
        uri=os.environ["NEO4J_URI"],
        user=os.environ["NEO4J_USER"],
        password=os.environ["NEO4J_PASSWORD"],
        database=os.environ["NEO4J_DATABASE"],
    )


# ---------------------------------------------------------------------------
# Schema statements
# ---------------------------------------------------------------------------

# Each tuple: (constraint_name, cypher)
# NODE KEY enforces uniqueness + non-null in a single constraint (Enterprise).
_CONSTRAINTS: list[tuple[str, LiteralString]] = [
    (
        "repo_github_url",
        cast(
            LiteralString,
            "CREATE CONSTRAINT repo_github_url IF NOT EXISTS "
            "FOR (r:Repo) REQUIRE r.github_url IS NODE KEY",
        ),
    ),
]


def apply_schema(driver: Driver, cfg: DbConfig, log: structlog.BoundLogger) -> None:
    with driver.session(database=cfg.database) as s:  # pyright: ignore[reportUnknownMemberType]
        for name, cypher in _CONSTRAINTS:
            s.run(cypher)
            log.info("constraint_applied", name=name, database=cfg.database)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def print_error(err: AppError, *, as_json: bool) -> None:
    payload = err.to_dict()
    if as_json:
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    else:
        print(f"[{err.code}] {err.message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", dest="as_json", action="store_true", help="Emit NDJSON events to stdout"
    )
    args = parser.parse_args()

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
            if args.as_json
            else structlog.dev.ConsoleRenderer(),
        ],
    )
    log: structlog.BoundLogger = structlog.get_logger()

    try:
        cfg = load_config()
        with GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password)) as driver:  # pyright: ignore[reportUnknownMemberType]
            apply_schema(driver, cfg, log)
        log.info("schema_done", database=cfg.database, status="ok")
    except AppError as exc:
        print_error(exc, as_json=args.as_json)


if __name__ == "__main__":
    main()
