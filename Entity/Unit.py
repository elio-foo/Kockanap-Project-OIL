from math import inf

from .Position import Position
from .SeenFire import SeenFire
from .UnitType import UnitType


UNIT_STATS_BY_TYPE = {
    UnitType.Firefighter: {
        "damage": 50,
        "sight_tiles": 2,
        "water_supply": inf,
        "speed": 50,
    },
    UnitType.Firetruck: {
        "damage": 200,
        "sight_tiles": 8,
        "water_supply": 20,
        "speed": 100,
    },
    UnitType.Firecopter: {
        "damage": 100,
        "sight_tiles": 16,
        "water_supply": 5,
        "speed": 200,
    },
}


class Unit:

    def __init__(
        self,
        unit_id=None,
        owner="",
        unit_type=None,
        position=None,
        current_water_level=0,
        current_hp=0,
        seen_fires=None,
        seen_waters=None,
        damage=None,
        sight_tiles=None,
        water_supply=None,
        speed=None,
    ):
        self.id: int | None = unit_id
        self.owner: str = owner
        self.type: UnitType | None = unit_type
        self.position: Position | None = position
        self.currentWaterLevel: int = current_water_level
        self.currentHP: int = current_hp
        self.seenFires: list[SeenFire] = seen_fires or []
        self.seenWaters: list[Position] = seen_waters or []
        self.damage: int = 0
        self.sightTiles: int = 0
        self.waterSupply: int | float = 0
        self.speed: int = 0

        self._apply_unit_type_stats()

        if damage is not None:
            self.damage = damage
        if sight_tiles is not None:
            self.sightTiles = sight_tiles
        if water_supply is not None:
            self.waterSupply = water_supply
        if speed is not None:
            self.speed = speed

    def _apply_unit_type_stats(self) -> None:
        stats = UNIT_STATS_BY_TYPE.get(self.type, {})
        self.damage = stats.get("damage", 0)
        self.sightTiles = stats.get("sight_tiles", 0)
        self.waterSupply = stats.get("water_supply", 0)
        self.speed = stats.get("speed", 0)

    @staticmethod
    def _parse_position(position_data) -> Position:
        position_data = position_data or {}
        return Position(position_data.get("X", 0), position_data.get("Y", 0))

    @classmethod
    def _parse_seen_fire(cls, fire_data) -> SeenFire:
        return SeenFire(
            position=cls._parse_position(fire_data),
            hp=fire_data.get("HP", 0),
        )

    def from_json(self, json_data):
        self.id = json_data.get("Id")
        self.owner = json_data.get("Owner", "")
        self.type = UnitType.from_value(json_data.get("UnitType"))
        self._apply_unit_type_stats()
        self.position = self._parse_position(json_data.get("Position"))
        self.currentWaterLevel = json_data.get("CurrentWaterLevel", 0)
        self.currentHP = json_data.get("CurrentHP", 0)
        self.seenFires = [
            self._parse_seen_fire(fire_data)
            for fire_data in json_data.get("SeenFires", [])
        ]
        self.seenWaters = [
            self._parse_position(water_data)
            for water_data in json_data.get("SeenWaters", [])
        ]

        return self

    def __str__(self):
        return (
            f"Unit(id={self.id}, owner={self.owner}, type={self.type}, "
            f"position={self.position}, hp={self.currentHP}, water={self.currentWaterLevel}, "
            f"damage={self.damage}, sightTiles={self.sightTiles}, waterSupply={self.waterSupply}, "
            f"speed={self.speed}, seenFires={len(self.seenFires)}, seenWaters={len(self.seenWaters)})"
        )
