from dataclasses import dataclass
from pathlib import Path

from Entity import Unit


@dataclass(slots=True)
class FireMemory:
    awaiting_revisit: bool = False
    was_visible_last_update: bool = False


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
        self._fire_memory: dict[tuple[int, int], FireMemory] = {}
        self._water_memory: set[tuple[int, int]] = set()
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

        self._water_memory.update(current_water_positions)

        self._update_fire_memory(visible_cells, current_fire_positions)

        for coordinates in self._water_memory:
            self._known_cells[coordinates] = self._WATER

        for coordinates in self._fire_memory:
            self._known_cells[coordinates] = self._FIRE

        self._write_map(unit_overlays)

    def get_known_cells(self) -> dict[tuple[int, int], str]:
        return dict(self._known_cells)

    def get_frontier_cells(self) -> set[tuple[int, int]]:
        frontier_cells: set[tuple[int, int]] = set()

        for coordinates in self._known_cells:
            if self._has_unknown_neighbor(coordinates):
                frontier_cells.add(coordinates)

        return frontier_cells

    def count_unknown_neighbors(self, coordinates: tuple[int, int]) -> int:
        unknown_neighbors = 0

        for neighbor in self._neighbors_of(coordinates):
            if neighbor not in self._known_cells:
                unknown_neighbors += 1

        return unknown_neighbors

    def _update_fire_memory(
        self,
        visible_cells: set[tuple[int, int]],
        current_fire_positions: set[tuple[int, int]],
    ) -> None:
        for coordinates in current_fire_positions:
            fire_memory = self._fire_memory.get(coordinates)
            if fire_memory is None:
                fire_memory = FireMemory()
                self._fire_memory[coordinates] = fire_memory

            fire_memory.awaiting_revisit = False
            fire_memory.was_visible_last_update = True

        fire_positions_to_remove: list[tuple[int, int]] = []

        for coordinates, fire_memory in self._fire_memory.items():
            if coordinates in current_fire_positions:
                continue

            currently_visible = coordinates in visible_cells

            if not currently_visible:
                if fire_memory.was_visible_last_update:
                    fire_memory.awaiting_revisit = True
                fire_memory.was_visible_last_update = False
                continue

            if fire_memory.awaiting_revisit:
                fire_positions_to_remove.append(coordinates)
                continue

            # Still in the same visibility session as when the fire was last remembered.
            # Keep the fire on the map until the tile leaves vision and is later rechecked.
            fire_memory.was_visible_last_update = True

        for coordinates in fire_positions_to_remove:
            self._fire_memory.pop(coordinates, None)

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
                row_cells.append(self._display_symbol(coordinates, unit_overlays))

            map_contents.append(f"{y:>4} {' '.join(row_cells)}")

        self.map_path.write_text("\n".join(map_contents) + "\n", encoding="utf-8")

    def _has_unknown_neighbor(self, coordinates: tuple[int, int]) -> bool:
        return any(neighbor not in self._known_cells for neighbor in self._neighbors_of(coordinates))

    def _display_symbol(
        self,
        coordinates: tuple[int, int],
        unit_overlays: dict[tuple[int, int], str],
    ) -> str:
        remembered_symbol = self._known_cells.get(coordinates, self._UNKNOWN)

        if remembered_symbol == self._FIRE:
            return self._FIRE

        if remembered_symbol == self._WATER:
            return self._WATER

        return unit_overlays.get(coordinates, remembered_symbol)

    @staticmethod
    def _neighbors_of(coordinates: tuple[int, int]) -> tuple[tuple[int, int], ...]:
        x, y = coordinates
        neighbors = (
            (x + 1, y),
            (x - 1, y),
            (x, y + 1),
            (x, y - 1),
        )
        return tuple(neighbor for neighbor in neighbors if neighbor[0] >= 0 and neighbor[1] >= 0)

    @classmethod
    def _symbol_for_unit(cls, unit: Unit) -> str:
        unit_type_name = unit.type.name if unit.type is not None else ""
        return cls._UNIT_SYMBOLS.get(unit_type_name, "U")
