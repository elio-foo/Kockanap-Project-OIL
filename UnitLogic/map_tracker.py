from dataclasses import dataclass
from pathlib import Path

from Entity import Unit


@dataclass(slots=True)
class FireMemory:
    awaiting_revisit: bool = False
    was_visible_last_update: bool = False
    last_seen_by_unit_id: int | None = None  # Track which unit last saw this fire


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
        self._detected_right_border: int | None = None
        self._detected_bottom_border: int | None = None
        self._last_unit_overlays: dict[tuple[int, int], str] = {}
        self._observation_version = 0
        self._write_map({})

    def update_from_units(self, units_by_id: dict[int, Unit]) -> None:
        self._observation_version += 1
        visible_cells: set[tuple[int, int]] = set()
        current_fire_positions: set[tuple[int, int]] = set()
        current_water_positions: set[tuple[int, int]] = set()
        unit_overlays: dict[tuple[int, int], str] = {}

        for unit in units_by_id.values():
            if unit.position is None:
                continue

            unit_position = (unit.position.x, unit.position.y)
            if self.is_within_detected_bounds(unit_position):
                unit_overlays[unit_position] = self._symbol_for_unit(unit)

            visible_cells.update(self._visible_cells_for_unit(unit))

            for seen_fire in unit.seenFires:
                if seen_fire.hp <= 0:
                    continue
                fire_position = (seen_fire.position.x, seen_fire.position.y)
                if self.is_within_detected_bounds(fire_position):
                    current_fire_positions.add(fire_position)

            for seen_water in unit.seenWaters:
                water_position = (seen_water.x, seen_water.y)
                if self.is_within_detected_bounds(water_position):
                    current_water_positions.add(water_position)

        for coordinates in visible_cells:
            self._known_cells[coordinates] = self._EMPTY

        self._water_memory.update(current_water_positions)

        self._update_fire_memory(visible_cells, current_fire_positions, units_by_id)

        for coordinates in self._water_memory:
            self._known_cells[coordinates] = self._WATER

        for coordinates in self._fire_memory:
            self._known_cells[coordinates] = self._FIRE

        self._last_unit_overlays = dict(unit_overlays)
        self._write_map(unit_overlays)

    def nearest_unknown_tile(self, origin: tuple[int, int]) -> tuple[int, int] | None:
        if not self._known_cells:
            return None

        frontier_candidates: set[tuple[int, int]] = set()

        for coordinates in self._known_cells:
            for neighbor in self._neighbors(coordinates):
                if neighbor[0] < 0 or neighbor[1] < 0:
                    continue
                if neighbor not in self._known_cells:
                    frontier_candidates.add(neighbor)

        if not frontier_candidates:
            return None

        return min(
            frontier_candidates,
            key=lambda coordinates: self._distance(origin, coordinates),
        )

    def nearest_water_tile(self, origin: tuple[int, int]) -> tuple[int, int] | None:
        water_tiles = [
            coordinates
            for coordinates, marker in self._known_cells.items()
            if marker == self._WATER
        ]
        if not water_tiles:
            return None

        return min(
            water_tiles,
            key=lambda coordinates: self._distance(origin, coordinates),
        )

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
            if not self.is_within_detected_bounds(neighbor):
                continue
            if neighbor not in self._known_cells:
                unknown_neighbors += 1

        return unknown_neighbors

    def is_within_detected_bounds(self, coordinates: tuple[int, int]) -> bool:
        x, y = coordinates
        if x < 0 or y < 0:
            return False
        if self._detected_right_border is not None and x > self._detected_right_border:
            return False
        if self._detected_bottom_border is not None and y > self._detected_bottom_border:
            return False
        return True

    def has_detected_full_bounds(self) -> bool:
        return self._detected_right_border is not None and self._detected_bottom_border is not None

    def detected_center(self) -> tuple[int, int] | None:
        if not self.has_detected_full_bounds():
            return None
        return (self._detected_right_border // 2, self._detected_bottom_border // 2)

    @property
    def observation_version(self) -> int:
        return self._observation_version

    def record_failed_move(
        self,
        current_position: tuple[int, int],
        attempted_target: tuple[int, int],
    ) -> None:
        current_x, current_y = current_position
        target_x, target_y = attempted_target
        updated = False

        if target_x == current_x + 1 and target_y == current_y:
            updated = self._record_right_border(current_x) or updated
        elif target_x == current_x and target_y == current_y + 1:
            updated = self._record_bottom_border(current_y) or updated

        if not updated:
            return

        self._prune_cells_outside_detected_bounds()
        self._write_map(self._last_unit_overlays)

    def _record_right_border(self, border_x: int) -> bool:
        if self._detected_right_border is None or border_x < self._detected_right_border:
            self._detected_right_border = border_x
            return True
        return False

    def _record_bottom_border(self, border_y: int) -> bool:
        if self._detected_bottom_border is None or border_y < self._detected_bottom_border:
            self._detected_bottom_border = border_y
            return True
        return False

    def _prune_cells_outside_detected_bounds(self) -> None:
        self._known_cells = {
            coordinates: cell_type
            for coordinates, cell_type in self._known_cells.items()
            if self.is_within_detected_bounds(coordinates)
        }
        self._fire_memory = {
            coordinates: fire_memory
            for coordinates, fire_memory in self._fire_memory.items()
            if self.is_within_detected_bounds(coordinates)
        }
        self._water_memory = {
            coordinates
            for coordinates in self._water_memory
            if self.is_within_detected_bounds(coordinates)
        }
        self._last_unit_overlays = {
            coordinates: symbol
            for coordinates, symbol in self._last_unit_overlays.items()
            if self.is_within_detected_bounds(coordinates)
        }

    def _update_fire_memory(
        self,
        visible_cells: set[tuple[int, int]],
        current_fire_positions: set[tuple[int, int]],
        units_by_id: dict[int, Unit],
    ) -> None:
        # Track which units saw which fires in this update
        unit_sight: dict[int, set[tuple[int, int]]] = {}
        for unit_id, unit in units_by_id.items():
            if unit.position is None:
                continue
            unit_sight[unit_id] = self._visible_cells_for_unit(unit)

        for coordinates in current_fire_positions:
            fire_memory = self._fire_memory.get(coordinates)
            if fire_memory is None:
                fire_memory = FireMemory()
                self._fire_memory[coordinates] = fire_memory

            fire_memory.awaiting_revisit = False
            fire_memory.was_visible_last_update = True

            # Find which unit saw this fire and track it
            for unit_id, visible in unit_sight.items():
                if coordinates in visible:
                    fire_memory.last_seen_by_unit_id = unit_id
                    break

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

            # Tile is visible but no fire reported.
            # Only clear if the SAME unit that originally saw the fire revisits it.
            # This prevents drones from incorrectly clearing fires seen by firefighters.
            if fire_memory.awaiting_revisit:
                # Check if any unit that originally saw this fire is now seeing it again
                original_unit_id = fire_memory.last_seen_by_unit_id
                if original_unit_id is not None:
                    original_unit_visible = unit_sight.get(original_unit_id, set())
                    if coordinates in original_unit_visible:
                        # Same unit confirmed no fire here - clear it
                        fire_positions_to_remove.append(coordinates)
                        continue

                # Different unit (e.g., drone) is seeing this tile - keep the fire
                fire_memory.awaiting_revisit = False
                fire_memory.was_visible_last_update = True
                continue

            # Still in the same visibility session as when the fire was last remembered.
            # Keep the fire on the map until the tile leaves vision and is later rechecked.
            fire_memory.was_visible_last_update = True

        for coordinates in fire_positions_to_remove:
            self._fire_memory.pop(coordinates, None)

    def _visible_cells_for_unit(self, unit: Unit) -> set[tuple[int, int]]:
        if unit.position is None:
            return set()

        radius_visible_cells = self._radius_visible_cells_for_unit(unit)
        explicit_visible_cells = {
            (tile.x, tile.y)
            for tile in unit.visibleTiles
            if self.is_within_detected_bounds((tile.x, tile.y))
        }

        return radius_visible_cells | explicit_visible_cells

    def _radius_visible_cells_for_unit(self, unit: Unit) -> set[tuple[int, int]]:
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
                if not self.is_within_detected_bounds((cell_x, cell_y)):
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

        min_x = 0
        min_y = 0
        observed_max_x = max(x for x, _ in all_coordinates)
        observed_max_y = max(y for _, y in all_coordinates)
        observed_edge = max(observed_max_x, observed_max_y)

        max_x = self._detected_right_border if self._detected_right_border is not None else observed_edge
        max_y = self._detected_bottom_border if self._detected_bottom_border is not None else observed_edge

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

    @staticmethod
    def _neighbors(coordinates: tuple[int, int]) -> tuple[tuple[int, int], ...]:
        return MapTracker._neighbors_of(coordinates)

    def _has_unknown_neighbor(self, coordinates: tuple[int, int]) -> bool:
        return any(
            self.is_within_detected_bounds(neighbor) and neighbor not in self._known_cells
            for neighbor in self._neighbors_of(coordinates)
        )

    def _display_symbol(
        self,
        coordinates: tuple[int, int],
        unit_overlays: dict[tuple[int, int], str],
    ) -> str:
        if coordinates in unit_overlays:
            return unit_overlays[coordinates]

        remembered_symbol = self._known_cells.get(coordinates, self._UNKNOWN)

        if remembered_symbol == self._FIRE:
            return self._FIRE

        if remembered_symbol == self._WATER:
            return self._WATER

        return remembered_symbol

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

    @staticmethod
    def _distance(a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @classmethod
    def _symbol_for_unit(cls, unit: Unit) -> str:
        unit_type_name = unit.type.name if unit.type is not None else ""
        return cls._UNIT_SYMBOLS.get(unit_type_name, "U")
