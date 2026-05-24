"""Domain models for geographic locations and routes."""

from pydantic import BaseModel, ConfigDict


class Location(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    name: str
    address: str
    lng: float
    lat: float
    adcode: str


class Route(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    mode: str
    distance_m: int
    duration_s: int
    tolls: int
    taxi_cost: float | None
