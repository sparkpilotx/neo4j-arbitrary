"""Amap (高德地图) Web Service API client."""

import os

import httpx
from pydantic import BaseModel, ConfigDict

from neo4j_arbitrary.errors import AppError, ErrorCode
from neo4j_arbitrary.location import Location, Route

_BASE = "https://restapi.amap.com/v3"
_MODES = ("walking", "driving")


# ── Amap response models (external API shape, strict to avoid silent coercion) ──


class _GeoResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    formatted_address: str
    location: str
    adcode: str


class _GeoResponse(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    status: str
    info: str
    geocodes: list[_GeoResult] = []


class _RoutePath(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    distance: str
    duration: str
    tolls: str = "0"


class _RouteBody(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    paths: list[_RoutePath]
    taxi_cost: str | None = None


class _RouteResponse(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    status: str
    info: str
    route: _RouteBody


# ── Public API ───────────────────────────────────────────────────────────────


def _api_key() -> str:
    key = os.environ.get("AMAP_API_KEY", "")
    if not key:
        raise AppError(
            ErrorCode.VALIDATION,
            "AMAP_API_KEY is not set",
            suggestion="Export AMAP_API_KEY before running.",
        )
    return key


def geocode(name: str, address: str) -> Location:
    resp = httpx.get(
        f"{_BASE}/geocode/geo",
        params={"address": address, "key": _api_key()},
        timeout=10,
    )
    resp.raise_for_status()
    parsed = _GeoResponse.model_validate(resp.json())
    if parsed.status != "1" or not parsed.geocodes:
        raise AppError(
            ErrorCode.EXTERNAL,
            "Amap geocoding failed",
            context={"address": address, "info": parsed.info},
            suggestion="Check the address string and AMAP_API_KEY platform permissions.",
        )
    geo = parsed.geocodes[0]
    lng_str, lat_str = geo.location.split(",")
    return Location(
        name=name,
        address=geo.formatted_address,
        lng=float(lng_str),
        lat=float(lat_str),
        adcode=geo.adcode,
    )


def get_routes(origin: Location, destination: Location) -> list[Route]:
    routes: list[Route] = []
    for mode in _MODES:
        resp = httpx.get(
            f"{_BASE}/direction/{mode}",
            params={
                "origin": f"{origin.lng},{origin.lat}",
                "destination": f"{destination.lng},{destination.lat}",
                "key": _api_key(),
            },
            timeout=10,
        )
        resp.raise_for_status()
        parsed = _RouteResponse.model_validate(resp.json())
        if parsed.status != "1" or not parsed.route.paths:
            raise AppError(
                ErrorCode.EXTERNAL,
                f"Amap {mode} routing failed",
                context={"origin": origin.name, "dest": destination.name, "info": parsed.info},
            )
        path = parsed.route.paths[0]
        taxi_raw = parsed.route.taxi_cost
        routes.append(
            Route(
                mode=mode,
                distance_m=int(path.distance),
                duration_s=int(path.duration),
                tolls=int(path.tolls),
                taxi_cost=float(taxi_raw) if taxi_raw else None,
            )
        )
    return routes
