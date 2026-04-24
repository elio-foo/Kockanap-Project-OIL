from pathlib import Path

from Entity import Unit


class MapTracker:
    _UNKNOWN = "?"
    _EMPTY = "."
    _FIRE = "F"
    _WATER = "W"
    _UNIT_SYMBOLS = {
        "Firefighter": "H",
        "Firetruck": "T",
        "Firecopter": "C",
    }

    def __init__(self, map_path: str | Path = "map.txt") -> None:
        self.map_path = Path(map_path)
        self._known_cells: dict[tuple[int, int], str] = {}
        self._write_map({})

    def update_from_units(self, units_by_id: dict[int, Unit]) -> None:
        visible_cells: set[tuple[int, int]] = set()
        current_fire_positions: set[tuple[int, int]] = set()
        current_water_positions: set[tuple[int, int]] = set()
        unit_overlays: dict[tuple[int, int], str] = {}

        for unit in units_by_id.values():
            if unit.position is None:
                continue

            unit_position = (unit.position.x, unit.position.y)
            unit_overlays[unit_position] = self._symbol_for_unit(unit)

            visible_cells.update(self._visible_cells_for_unit(unit))

            for seen_fire in unit.seenFires:
                if seen_fire.hp <= 0:
                    continue
                current_fire_positions.add((seen_fire.position.x, seen_fire.position.y))

            for seen_water in unit.seenWaters:
                current_water_positions.add((seen_water.x, seen_water.y))

        for coordinates in visible_cells:
            self._known_cells[coordinates] = self._EMPTY

        for coordinates in current_water_positions:
            self._known_cells[coordinates] = self._WATER

        for coordinates in current_fire_positions:
            self._known_cells[coordinates] = self._FIRE

        self._write_map(unit_overlays)

    def _visible_cells_for_unit(self, unit: Unit) -> set[tuple[int, int]]:
        if unit.position is None:
            return set()

        origin_x = unit.position.x
        origin_y = unit.position.y
        sight = max(0, unit.sightTiles)
        visible_cells: set[tuple[int, int]] = set()

        for dx in range(-sight, sight + 1):
            for dy in range(-sight, sight + 1):
                if abs(dx) + abs(dy) > sight:
                    continue
                cell_x = origin_x + dx
                cell_y = origin_y + dy
                if cell_x < 0 or cell_y < 0:
                    continue
                visible_cells.add((cell_x, cell_y))

        return visible_cells

    def _write_map(self, unit_overlays: dict[tuple[int, int], str]) -> None:
        self.map_path.parent.mkdir(parents=True, exist_ok=True)
        all_coordinates = set(self._known_cells) | set(unit_overlays)

        if not all_coordinates:
            map_contents = [
                "# Team map knowledge",
                "# Legend: ? unknown, . explored, F fire, W water, H firefighter, T firetruck, C firecopter",
                "# No observations yet.",
            ]
            self.map_path.write_text("\n".join(map_contents) + "\n", encoding="utf-8")
            return

        min_x = min(x for x, _ in all_coordinates)
        max_x = max(x for x, _ in all_coordinates)
        min_y = min(y for _, y in all_coordinates)
        max_y = max(y for _, y in all_coordinates)

        map_contents = [
            "# Team map knowledge",
            "# Legend: ? unknown, . explored, F fire, W water, H firefighter, T firetruck, C firecopter",
            f"# Bounds: x={min_x}..{max_x}, y={min_y}..{max_y}",
        ]

        for y in range(min_y, max_y + 1):
            row_cells: list[str] = []
            for x in range(min_x, max_x + 1):
                coordinates = (x, y)
                row_cells.append(unit_overlays.get(coordinates, self._known_cells.get(coordinates, self._UNKNOWN)))

            map_contents.append(f"{y:>4} {' '.join(row_cells)}")

        self.map_path.write_text("\n".join(map_contents) + "\n", encoding="utf-8")

    @classmethod
    def _symbol_for_unit(cls, unit: Unit) -> str:
        unit_type_name = unit.type.name if unit.type is not None else ""
        return cls._UNIT_SYMBOLS.get(unit_type_name, "U")
