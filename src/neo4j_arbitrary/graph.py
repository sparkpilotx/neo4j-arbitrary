"""Neo4j graph write operations for locations and routes."""

from neo4j import Driver

from neo4j_arbitrary.location import Location, Route


def upsert_location(driver: Driver, loc: Location, *, database: str) -> None:
    with driver.session(database=database) as s:  # pyright: ignore[reportUnknownMemberType]
        s.run(  # pyright: ignore[reportUnknownMemberType]
            """
            MERGE (l:Location {name: $name})
            SET l.address  = $address,
                l.lat      = $lat,
                l.lng      = $lng,
                l.adcode   = $adcode
            """,
            name=loc.name,
            address=loc.address,
            lat=loc.lat,
            lng=loc.lng,
            adcode=loc.adcode,
        )


def upsert_route(
    driver: Driver,
    origin: Location,
    destination: Location,
    route: Route,
    *,
    database: str,
) -> None:
    with driver.session(database=database) as s:  # pyright: ignore[reportUnknownMemberType]
        s.run(  # pyright: ignore[reportUnknownMemberType]
            """
            MATCH (o:Location {name: $origin}), (d:Location {name: $dest})
            MERGE (o)-[r:ROUTE {mode: $mode}]->(d)
            SET r.distance_m = $distance_m,
                r.duration_s = $duration_s,
                r.tolls      = $tolls,
                r.taxi_cost  = $taxi_cost
            """,
            origin=origin.name,
            dest=destination.name,
            mode=route.mode,
            distance_m=route.distance_m,
            duration_s=route.duration_s,
            tolls=route.tolls,
            taxi_cost=route.taxi_cost,
        )
