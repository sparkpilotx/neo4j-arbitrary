"""Geocode two addresses via Amap, fetch routes, and upsert into Neo4j."""

import argparse
import json
import os
import sys

import structlog
from neo4j import GraphDatabase

from neo4j_arbitrary.amap import geocode, get_routes
from neo4j_arbitrary.errors import AppError, ErrorCode
from neo4j_arbitrary.graph import upsert_location, upsert_route


def _print_error(err: AppError, *, as_json: bool) -> None:
    payload = err.to_dict()
    if as_json:
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    else:
        print(f"[{err.code}] {err.message}", file=sys.stderr)
    sys.exit(1)


def _load_neo4j_env() -> tuple[str, str, str, str]:
    keys = ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE")
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        raise AppError(
            ErrorCode.VALIDATION,
            "Missing required environment variables",
            context={"missing": missing},
            suggestion=f"Export {', '.join(missing)} before running.",
        )
    return (
        os.environ["NEO4J_URI"],
        os.environ["NEO4J_USER"],
        os.environ["NEO4J_PASSWORD"],
        os.environ["NEO4J_DATABASE"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin_name", help="Display name for the origin location")
    parser.add_argument("origin_address", help="Origin address to geocode (Chinese address string)")
    parser.add_argument("dest_name", help="Display name for the destination location")
    parser.add_argument("dest_address", help="Destination address to geocode (Chinese address)")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Emit NDJSON to stdout")
    args = parser.parse_args()

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
            if args.as_json
            else structlog.dev.ConsoleRenderer(),
        ]
    )
    log: structlog.BoundLogger = structlog.get_logger()

    try:
        uri, user, password, database = _load_neo4j_env()

        origin = geocode(args.origin_name, args.origin_address)
        log.info("geocoded", name=origin.name, lng=origin.lng, lat=origin.lat)

        dest = geocode(args.dest_name, args.dest_address)
        log.info("geocoded", name=dest.name, lng=dest.lng, lat=dest.lat)

        routes = get_routes(origin, dest)
        log.info("routes_fetched", count=len(routes), modes=[r.mode for r in routes])

        with GraphDatabase.driver(uri, auth=(user, password)) as driver:  # pyright: ignore[reportUnknownMemberType]
            upsert_location(driver, origin, database=database)
            log.info("location_upserted", name=origin.name)

            upsert_location(driver, dest, database=database)
            log.info("location_upserted", name=dest.name)

            for route in routes:
                upsert_route(driver, origin, dest, route, database=database)
                log.info(
                    "route_upserted",
                    mode=route.mode,
                    distance_m=route.distance_m,
                    duration_s=route.duration_s,
                    taxi_cost=route.taxi_cost,
                )

        log.info("done", origin=origin.name, destination=dest.name, routes=len(routes))

    except AppError as exc:
        _print_error(exc, as_json=args.as_json)


if __name__ == "__main__":
    main()
