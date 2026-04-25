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
        visible_tiles=None,
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
        self.visibleTiles: list[Position] = visible_tiles or []
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
        return Position(
            position_data.get("X", position_data.get("x", 0)),
            position_data.get("Y", position_data.get("y", 0)),
        )

    @classmethod
    def _parse_seen_fire(cls, fire_data) -> SeenFire:
        return SeenFire(
            position=cls._parse_position(fire_data),
            hp=cls._coerce_int(
                cls._first_present(fire_data, "HP", "hp", "Intensity", "intensity"),
                0,
            ),
        )

    @staticmethod
    def _first_present(json_data, *keys):
        for key in keys:
            if key in json_data and json_data[key] is not None:
                return json_data[key]
        return None

    @staticmethod
    def _coerce_int(value, fallback: int) -> int:
        if value is None:
            return fallback

        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _coerce_number(value, fallback: int | float) -> int | float:
        if value is None:
            return fallback

        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _parse_optional_json(value):
        if isinstance(value, str):
            try:
                import json

                return json.loads(value)
            except (TypeError, ValueError):
                return value
        return value

    @classmethod
    def _extract_embedded_extra_json(cls, json_data) -> dict:
        if not isinstance(json_data, dict):
            return {}

        merged_extra_json: dict = {}
        for key in ("ExtraJson", "extraJson"):
            raw_extra_json = json_data.get(key)
            parsed_extra_json = cls._parse_optional_json(raw_extra_json)
            if isinstance(parsed_extra_json, dict):
                merged_extra_json.update(parsed_extra_json)

        return merged_extra_json

    @classmethod
    def _try_parse_position_entry(cls, entry) -> Position | None:
        if not isinstance(entry, dict):
            return None

        if "Position" in entry and isinstance(entry["Position"], dict):
            entry = entry["Position"]

        has_x = "X" in entry or "x" in entry
        has_y = "Y" in entry or "y" in entry
        if not (has_x and has_y):
            return None

        return cls._parse_position(entry)

    @classmethod
    def _parse_positions_list(cls, entries) -> list[Position]:
        entries = cls._parse_optional_json(entries)
        if not isinstance(entries, list):
            return []

        positions: list[Position] = []
        for entry in entries:
            position = cls._try_parse_position_entry(entry)
            if position is None:
                continue
            positions.append(position)

        return positions

    @classmethod
    def _normalized_payload(cls, json_data) -> dict:
        if not isinstance(json_data, dict):
            return {}

        normalized_json = dict(json_data)
        normalized_json.update(cls._extract_embedded_extra_json(json_data))
        return normalized_json

    @classmethod
    def _parse_seen_fires_list(cls, entries) -> list[SeenFire]:
        entries = cls._parse_optional_json(entries)
        if not isinstance(entries, list):
            return []

        seen_fires: list[SeenFire] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue

            position = cls._try_parse_position_entry(entry)
            if position is None:
                continue

            seen_fires.append(
                SeenFire(
                    position=position,
                    hp=cls._coerce_int(
                        cls._first_present(entry, "HP", "Hp", "hp", "Intensity", "intensity"),
                        1,
                    ),
                )
            )

        return seen_fires

    @classmethod
    def _discover_seen_fires(cls, json_data) -> list[SeenFire]:
        normalized_json = cls._normalized_payload(json_data)
        fire_keys = (
            "SeenFires",
            "Fires",
            "FireTiles",
            "SeenFireTiles",
            "FirePositions",
            "BurningTiles",
            "TilesOnFire",
            "AllFires",
            "AllFireTiles",
            "seenFires",
            "fires",
            "fireTiles",
            "seenFireTiles",
            "firePositions",
            "burningTiles",
            "tilesOnFire",
            "allFires",
            "allFireTiles",
        )
        seen_fires: list[SeenFire] = []
        seen_coordinates: set[tuple[int, int]] = set()

        for key in fire_keys:
            for seen_fire in cls._parse_seen_fires_list(normalized_json.get(key)):
                coordinates = (seen_fire.position.x, seen_fire.position.y)
                if coordinates in seen_coordinates:
                    continue
                seen_coordinates.add(coordinates)
                seen_fires.append(seen_fire)

        return seen_fires

    @classmethod
    def _discover_seen_waters(cls, json_data) -> list[Position]:
        normalized_json = cls._normalized_payload(json_data)
        water_keys = (
            "SeenWaters",
            "Waters",
            "WaterTiles",
            "WaterSources",
            "SeenWaterTiles",
            "WaterPositions",
            "AllWaters",
            "AllWaterTiles",
            "seenWaters",
            "waters",
            "waterTiles",
            "waterSources",
            "seenWaterTiles",
            "waterPositions",
            "water_sources",
            "allWaters",
            "allWaterTiles",
        )
        seen_waters: list[Position] = []
        seen_coordinates: set[tuple[int, int]] = set()

        for key in water_keys:
            for position in cls._parse_positions_list(normalized_json.get(key)):
                coordinates = (position.x, position.y)
                if coordinates in seen_coordinates:
                    continue
                seen_coordinates.add(coordinates)
                seen_waters.append(position)

        return seen_waters

    @classmethod
    def _discover_visible_tiles(cls, json_data) -> list[Position]:
        normalized_json = cls._normalized_payload(json_data)

        explicit_entries = cls._first_present(
            normalized_json,
            "VisibleTiles",
            "SeenTiles",
            "VisiblePositions",
            "ScannedArea",
            "VisibleArea",
            "visibleTiles",
            "seenTiles",
            "visiblePositions",
            "scannedArea",
            "visibleArea",
        )
        explicit_positions = cls._parse_positions_list(explicit_entries)
        if explicit_positions:
            return explicit_positions

        discovered_positions: list[Position] = []
        seen_coordinates: set[tuple[int, int]] = set()
        excluded_keys = {
            "SeenFires",
            "SeenWaters",
            "Fires",
            "Waters",
            "FireTiles",
            "SeenFireTiles",
            "FirePositions",
            "WaterTiles",
            "WaterSources",
            "SeenWaterTiles",
            "WaterPositions",
            "BurningTiles",
            "TilesOnFire",
            "AllFires",
            "AllFireTiles",
            "AllWaters",
            "AllWaterTiles",
            "visibleTiles",
            "VisibleTiles",
            "seenFires",
            "seenWaters",
            "fires",
            "waters",
            "fireTiles",
            "seenFireTiles",
            "firePositions",
            "waterTiles",
            "waterSources",
            "seenWaterTiles",
            "waterPositions",
            "water_sources",
            "burningTiles",
            "tilesOnFire",
            "allFires",
            "allFireTiles",
            "allWaters",
            "allWaterTiles",
        }

        def collect_positions(node, current_key=None) -> None:
            node = cls._parse_optional_json(node)

            if isinstance(current_key, str) and current_key in excluded_keys:
                return

            positions = cls._parse_positions_list(node)
            if positions:
                for position in positions:
                    coordinates = (position.x, position.y)
                    if coordinates in seen_coordinates:
                        continue
                    seen_coordinates.add(coordinates)
                    discovered_positions.append(position)
                return

            if isinstance(node, dict):
                for key, value in node.items():
                    collect_positions(value, key)
                return

            if isinstance(node, list):
                for value in node:
                    collect_positions(value, current_key)

        collect_positions(normalized_json)

        return discovered_positions

    def from_json(self, json_data):
        self.id = json_data.get("Id")
        self.owner = json_data.get("Owner", "")
        self.type = UnitType.from_value(json_data.get("UnitType"))
        self._apply_unit_type_stats()
        self.position = self._parse_position(json_data.get("Position"))
        self.currentWaterLevel = json_data.get("CurrentWaterLevel", 0)
        self.currentHP = json_data.get("CurrentHP", 0)
        self.damage = self._coerce_int(
            self._first_present(json_data, "Damage", "damage"),
            self.damage,
        )
        self.sightTiles = self._coerce_int(
            self._first_present(
                json_data,
                "SightTiles",
                "Sight",
                "sightTiles",
                "sight",
            ),
            self.sightTiles,
        )
        self.waterSupply = self._coerce_number(
            self._first_present(
                json_data,
                "WaterSupply",
                "MaxWaterLevel",
                "waterSupply",
                "maxWaterLevel",
            ),
            self.waterSupply,
        )
        self.speed = self._coerce_int(
            self._first_present(json_data, "Speed", "speed"),
            self.speed,
        )
        self.seenFires = self._discover_seen_fires(json_data)
        self.seenWaters = self._discover_seen_waters(json_data)
        self.visibleTiles = self._discover_visible_tiles(json_data)

        return self

    def __str__(self):
        return (
            f"Unit(id={self.id}, owner={self.owner}, type={self.type}, "
            f"position={self.position}, hp={self.currentHP}, water={self.currentWaterLevel}, "
            f"damage={self.damage}, sightTiles={self.sightTiles}, waterSupply={self.waterSupply}, "
            f"speed={self.speed}, seenFires={len(self.seenFires)}, "
            f"seenWaters={len(self.seenWaters)}, visibleTiles={len(self.visibleTiles)})"
        )
