"""Drop and re-create the database named by NEO4J_DATABASE."""

import argparse
import json
import os
import sys
import time
from enum import StrEnum
from typing import LiteralString, cast

import structlog
from neo4j import Driver, GraphDatabase
from pydantic import BaseModel, ConfigDict


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


def _wait_online(driver: Driver, database: str, log: structlog.BoundLogger) -> None:
    for _ in range(20):
        with driver.session(database="system") as s:  # pyright: ignore[reportUnknownMemberType]
            row = s.run(
                "SHOW DATABASES YIELD name, currentStatus WHERE name = $n",
                n=database,
            ).single()
            if row and row["currentStatus"] == "online":
                log.info("db_online", database=database)
                return
        time.sleep(0.5)
    raise AppError(
        ErrorCode.EXTERNAL,
        f"{database!r} did not come online within 10 seconds",
        context={"database": database, "timeout_seconds": 10},
        suggestion="Check Neo4j system logs and retry.",
    )


def reset_db(cfg: DbConfig, log: structlog.BoundLogger) -> None:
    with GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password)) as driver:  # pyright: ignore[reportUnknownMemberType]
        with driver.session(database="system") as s:  # pyright: ignore[reportUnknownMemberType]
            # DROP/CREATE DATABASE has no $param support for names; backtick-escaped env var is safe
            s.run(cast(LiteralString, f"DROP DATABASE `{cfg.database}` IF EXISTS"))
            log.info("db_dropped", database=cfg.database)
            s.run(cast(LiteralString, f"CREATE DATABASE `{cfg.database}`"))
            log.info("db_created", database=cfg.database)

        _wait_online(driver, cfg.database, log)

        driver.verify_connectivity()  # pyright: ignore[reportUnknownMemberType]
        with driver.session(database=cfg.database) as s:  # pyright: ignore[reportUnknownMemberType]
            rows = s.run("CALL dbms.components() YIELD name, versions, edition").data()

        by_name = {r["name"]: r for r in rows}
        cypher = by_name.get("Cypher")
        cypher_language = f"CYPHER {cypher['versions'][-1]}" if cypher else "unknown"
        kernel = by_name.get("Neo4j Kernel", {})
        neo4j_version = kernel["versions"][0] if kernel.get("versions") else "unknown"
        edition = kernel.get("edition", "unknown")

        log.info(
            "db_reset_done",
            database=cfg.database,
            edition=edition,
            version=neo4j_version,
            cypher_language=cypher_language,
            status="ok",
        )


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
        reset_db(cfg, log)
    except AppError as exc:
        print_error(exc, as_json=args.as_json)


if __name__ == "__main__":
    main()
