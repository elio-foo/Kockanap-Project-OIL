from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from Entity import Position, Unit


def _position_from_payload(payload: Any) -> Position | None:
    if isinstance(payload, Position):
        return payload

    if isinstance(payload, dict):
        if "x" in payload and "y" in payload:
            return Position(int(payload["x"]), int(payload["y"]))

        if "X" in payload and "Y" in payload:
            return Position(int(payload["X"]), int(payload["Y"]))

        if "Position" in payload and isinstance(payload["Position"], dict):
            nested = payload["Position"]
            return Position(int(nested.get("X", 0)), int(nested.get("Y", 0)))

    return None


@dataclass(slots=True)
class FireTarget:
    position: Position
    intensity: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Any) -> "FireTarget | None":
        if isinstance(payload, FireTarget):
            return payload

        position = _position_from_payload(payload)
        if position is None:
            return None

        intensity = 0
        if isinstance(payload, dict):
            intensity = int(payload.get("intensity", payload.get("Intensity", 0)))

        return cls(position=position, intensity=intensity, raw=payload if isinstance(payload, dict) else {})

    def to_payload(self) -> dict[str, int]:
        return {
            "x": self.position.x,
            "y": self.position.y,
            "intensity": self.intensity,
        }


class UnitLogicContext:
    def __init__(
        self,
        fires: Iterable[FireTarget] | None = None,
        units: Iterable[Unit] | None = None,
        water_sources: Iterable[Position] | None = None,
    ):
        self.fires = list(fires or [])
        self.units = list(units or [])
        self.water_sources = list(water_sources or [])

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None, units: Iterable[Unit] | None = None) -> "UnitLogicContext":
        payload = payload or {}

        raw_fires = payload.get("fires", payload.get("Fires", []))
        fires = [fire for fire in (FireTarget.from_payload(item) for item in raw_fires) if fire is not None]

        raw_water_sources = payload.get("water_sources", payload.get("WaterSources", []))
        water_sources = [pos for pos in (_position_from_payload(item) for item in raw_water_sources) if pos is not None]

        parsed_units = list(units or [])
        raw_units = payload.get("units", payload.get("Units", []))
        for item in raw_units:
            if isinstance(item, Unit):
                parsed_units.append(item)

        return cls(fires=fires, units=parsed_units, water_sources=water_sources)

    @staticmethod
    def distance(a: Position, b: Position) -> int:
        return abs(a.x - b.x) + abs(a.y - b.y)

    def nearest_water_source(self, position: Position) -> Position | None:
        if not self.water_sources:
            return None
        return min(self.water_sources, key=lambda source: self.distance(position, source))
