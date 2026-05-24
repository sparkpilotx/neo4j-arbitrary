"""Drop and re-create the database named by NEO4J_DATABASE."""
import json
import os
import sys
import time

from neo4j import GraphDatabase

uri = os.environ["NEO4J_URI"]
user = os.environ["NEO4J_USER"]
password = os.environ["NEO4J_PASSWORD"]
db = os.environ["NEO4J_DATABASE"]


def emit(event: str, **kwargs) -> None:
    print(json.dumps({"event": event, **kwargs}), flush=True)


try:
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session(database="system") as s:
            s.run(f"DROP DATABASE `{db}` IF EXISTS")
            emit("dropped", database=db)
            s.run(f"CREATE DATABASE `{db}`")
            emit("created", database=db)

        for _ in range(20):
            with driver.session(database="system") as s:
                row = s.run(
                    "SHOW DATABASES YIELD name, currentStatus WHERE name = $n",
                    n=db,
                ).single()
                if row and row["currentStatus"] == "online":
                    emit("online", database=db)
                    break
            time.sleep(0.5)
        else:
            raise RuntimeError(f"{db} did not come online in time")

        driver.verify_connectivity()
        emit("done", database=db, uri=uri, status="ok")

except Exception as exc:
    emit("error", database=db, message=str(exc))
    sys.exit(1)
