from Entity import Position, SeenFire, Unit, UnitType
from Message import OperationId

from .context import UnitLogicContext


def todos(message: str) -> None:
    """Document a future unit-logic implementation point without breaking runtime."""
    _ = message


class BaseUnitLogic:
    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        raise NotImplementedError


class FirefighterLogic(BaseUnitLogic):
    _MOVE_OPTIONS = (
        ("right", (1, 0)),
        ("down", (0, 1)),
        ("left", (-1, 0)),
        ("up", (0, -1)),
    )

    def __init__(self) -> None:
        self._roam_state_by_unit: dict[int, dict[str, object]] = {}

    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        if unit.id is None or unit.position is None:
            return

        target_fire = self._find_nearest_active_fire(unit, context)
        if target_fire is not None:
            self._reset_roam_progress(unit)

            if self._is_on_fire_tile(unit.position, target_fire.position):
                await context.queue_command(unit.id, OperationId.EXTINGUISH)
                return

            direction = self._direction_towards(unit.position, target_fire.position)
            if direction is not None:
                await context.queue_move(unit.id, direction)
            return

        roam_direction = self._next_roam_direction(unit)
        if roam_direction is None:
            return

        await context.queue_move(unit.id, roam_direction)

    def _find_nearest_active_fire(
        self,
        unit: Unit,
        context: UnitLogicContext,
    ) -> SeenFire | None:
        active_fires = self._collect_active_fires(context)
        if not active_fires or unit.position is None:
            return None

        return min(
            active_fires,
            key=lambda fire: (
                self._distance(unit.position, fire.position),
                -fire.hp,
            ),
        )

    def _collect_active_fires(self, context: UnitLogicContext) -> list[SeenFire]:
        fires_by_position: dict[tuple[int, int], SeenFire] = {}

        for tracked_unit in context.units_by_id.values():
            for seen_fire in tracked_unit.seenFires:
                if seen_fire.hp <= 0:
                    continue

                key = (seen_fire.position.x, seen_fire.position.y)
                existing_fire = fires_by_position.get(key)

                if existing_fire is None or seen_fire.hp > existing_fire.hp:
                    fires_by_position[key] = seen_fire

        return list(fires_by_position.values())

    def _next_roam_direction(self, unit: Unit) -> str | None:
        if unit.id is None or unit.position is None:
            return None

        state = self._get_or_create_roam_state(unit)
        current_position = (unit.position.x, unit.position.y)
        self._apply_roam_feedback(state, current_position)

        move_choice = self._choose_roam_move(state, current_position)
        if move_choice is None:
            return None

        direction, target = move_choice
        state["last_position"] = current_position
        state["last_attempted_target"] = target
        return direction

    def _get_or_create_roam_state(self, unit: Unit) -> dict[str, object]:
        if unit.id is None or unit.position is None:
            return {}

        existing_state = self._roam_state_by_unit.get(unit.id)
        if existing_state is not None:
            return existing_state

        origin = (unit.position.x, unit.position.y)
        state: dict[str, object] = {
            "origin": (unit.position.x, unit.position.y),
            "last_position": origin,
            "last_attempted_target": None,
            "blocked_cells": set(),
            "visit_counts": {origin: 1},
            "move_cursor": 0,
        }
        self._roam_state_by_unit[unit.id] = state
        return state

    def _reset_roam_progress(self, unit: Unit) -> None:
        if unit.id is None:
            return

        state = self._roam_state_by_unit.get(unit.id)
        if state is None:
            return

        if unit.position is not None:
            state["last_position"] = (unit.position.x, unit.position.y)
        state["last_attempted_target"] = None

    def _apply_roam_feedback(self, state: dict[str, object], current_position: tuple[int, int]) -> None:
        last_position = state["last_position"]
        last_attempted_target = state["last_attempted_target"]

        if (
            isinstance(last_position, tuple)
            and isinstance(last_attempted_target, tuple)
            and current_position == last_position
        ):
            self._mark_blocked(state, last_attempted_target)
        else:
            visit_counts = state.get("visit_counts")
            if isinstance(visit_counts, dict):
                visit_counts[current_position] = visit_counts.get(current_position, 0) + 1

        state["last_position"] = current_position
        state["last_attempted_target"] = None

    def _choose_roam_move(
        self,
        state: dict[str, object],
        current_position: tuple[int, int],
    ) -> tuple[str, tuple[int, int]] | None:
        origin = state.get("origin")
        blocked_cells = state.get("blocked_cells")
        visit_counts = state.get("visit_counts")
        move_cursor = state.get("move_cursor", 0)

        if not isinstance(origin, tuple):
            return None
        if not isinstance(blocked_cells, set):
            return None
        if not isinstance(visit_counts, dict):
            return None
        if not isinstance(move_cursor, int):
            move_cursor = 0

        scored_moves: list[tuple[tuple[int, int, int, int], str, tuple[int, int]]] = []

        for offset in range(len(self._MOVE_OPTIONS)):
            direction, (dx, dy) = self._MOVE_OPTIONS[(move_cursor + offset) % len(self._MOVE_OPTIONS)]
            target = (current_position[0] + dx, current_position[1] + dy)

            if target[0] < 0 or target[1] < 0:
                self._mark_blocked(state, target)
                continue

            if target in blocked_cells:
                continue

            visit_count = visit_counts.get(target, 0)
            distance_from_origin = self._distance_tuple(origin, target)
            distance_from_current = self._distance_tuple(current_position, target)

            score = (visit_count, distance_from_origin, offset, distance_from_current)
            scored_moves.append((score, direction, target))

        if not scored_moves:
            return None

        _, direction, target = min(scored_moves, key=lambda item: item[0])
        state["move_cursor"] = (move_cursor + 1) % len(self._MOVE_OPTIONS)
        return direction, target

    @staticmethod
    def _mark_blocked(state: dict[str, object], coordinates: tuple[int, int]) -> None:
        blocked_cells = state.get("blocked_cells")
        if isinstance(blocked_cells, set):
            blocked_cells.add(coordinates)

    @staticmethod
    def _distance_tuple(a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def _distance(a: Position, b: Position) -> int:
        return abs(a.x - b.x) + abs(a.y - b.y)

    @staticmethod
    def _is_on_fire_tile(unit_position: Position, fire_position: Position) -> bool:
        return unit_position.x == fire_position.x and unit_position.y == fire_position.y

    @classmethod
    def _direction_towards(cls, current: Position, target: Position) -> str | None:
        return cls._direction_towards_tuple((current.x, current.y), (target.x, target.y))

    @staticmethod
    def _direction_towards_tuple(current: tuple[int, int], target: tuple[int, int]) -> str | None:
        current_x, current_y = current
        target_x, target_y = target
        dx = target_x - current_x
        dy = target_y - current_y

        if dx != 0:
            return "right" if dx > 0 else "left"

        if dy != 0:
            return "down" if dy > 0 else "up"

        return None


class FiretruckLogic(BaseUnitLogic):
    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        todos("Implement firetruck behavior here.")
        _ = (unit, context)


class FirecopterLogic(BaseUnitLogic):
    _DIRECTION_VECTORS = {
        "right": (1, 0),
        "down": (0, 1),
        "left": (-1, 0),
        "up": (0, -1),
    }

    def __init__(self) -> None:
        self._roam_state_by_unit: dict[int, dict[str, object]] = {}

    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        if unit.id is None or unit.position is None:
            return

        roam_direction = self._next_roam_direction(unit, context)
        if roam_direction is not None:
            await context.queue_move(unit.id, roam_direction)
            return

        target_fire = self._find_nearest_active_fire(unit, context)
        if target_fire is None:
            return

        if self._is_on_fire_tile(unit.position, target_fire.position):
            # Extinguish only as a fallback so visible fires do not interrupt scouting.
            await context.queue_command(unit.id, OperationId.EXTINGUISH)

    def _find_nearest_active_fire(
        self,
        unit: Unit,
        context: UnitLogicContext,
    ) -> SeenFire | None:
        active_fires = self._collect_active_fires(context)
        if not active_fires or unit.position is None:
            return None

        return min(
            active_fires,
            key=lambda fire: (
                self._distance(unit.position, fire.position),
                -fire.hp,
            ),
        )

    def _collect_active_fires(self, context: UnitLogicContext) -> list[SeenFire]:
        fires_by_position: dict[tuple[int, int], SeenFire] = {}

        for tracked_unit in context.units_by_id.values():
            for seen_fire in tracked_unit.seenFires:
                if seen_fire.hp <= 0:
                    continue

                key = (seen_fire.position.x, seen_fire.position.y)
                existing_fire = fires_by_position.get(key)

                if existing_fire is None or seen_fire.hp > existing_fire.hp:
                    fires_by_position[key] = seen_fire

        return list(fires_by_position.values())

    def _next_roam_direction(self, unit: Unit, context: UnitLogicContext) -> str | None:
        if unit.id is None or unit.position is None:
            return None

        state = self._get_or_create_roam_state(unit)
        state["shift_stride"] = max(1, unit.sightTiles)
        current_position = (unit.position.x, unit.position.y)
        self._apply_roam_feedback(state, current_position)

        move_choice = self._choose_roam_move(state, current_position, context)
        if move_choice is None:
            return None

        direction, target = move_choice
        state["last_position"] = current_position
        state["last_attempted_target"] = target
        state["last_attempted_direction"] = direction
        return direction

    def _get_or_create_roam_state(self, unit: Unit) -> dict[str, object]:
        if unit.id is None or unit.position is None:
            return {}

        existing_state = self._roam_state_by_unit.get(unit.id)
        if existing_state is not None:
            return existing_state

        origin = (unit.position.x, unit.position.y)
        state: dict[str, object] = {
            "origin": origin,
            "last_position": origin,
            "last_attempted_target": None,
            "last_attempted_direction": None,
            "phase": "sweep",
            "sweep_direction": "right",
            "vertical_direction": "down",
            "shift_stride": max(1, unit.sightTiles),
            "shift_remaining": 0,
            "blocked_cells": set(),
            "visit_counts": {origin: 1},
        }
        self._roam_state_by_unit[unit.id] = state
        return state

    def _apply_roam_feedback(self, state: dict[str, object], current_position: tuple[int, int]) -> None:
        last_position = state.get("last_position")
        last_attempted_target = state.get("last_attempted_target")
        phase = state.get("phase")
        shift_remaining = state.get("shift_remaining", 0)
        visit_counts = state.get("visit_counts")

        if (
            isinstance(visit_counts, dict)
            and (not isinstance(last_position, tuple) or current_position != last_position)
        ):
            visit_counts[current_position] = visit_counts.get(current_position, 0) + 1

        if (
            isinstance(last_position, tuple)
            and isinstance(last_attempted_target, tuple)
            and current_position == last_position
        ):
            self._mark_blocked(state, last_attempted_target)
            if phase == "sweep":
                state["phase"] = "shift_row"
                state["shift_remaining"] = state.get("shift_stride", 1)
            elif phase == "shift_row":
                state["phase"] = "sweep"
                state["vertical_direction"] = self._reverse_vertical_direction(
                    state.get("vertical_direction")
                )
                state["sweep_direction"] = self._reverse_horizontal_direction(
                    state.get("sweep_direction")
                )
                state["shift_remaining"] = 0
        elif phase == "shift_row":
            if not isinstance(shift_remaining, int):
                shift_remaining = 0

            shift_remaining -= 1
            if shift_remaining <= 0:
                state["phase"] = "sweep"
                state["shift_remaining"] = 0
                state["sweep_direction"] = self._reverse_horizontal_direction(
                    state.get("sweep_direction")
                )
            else:
                state["shift_remaining"] = shift_remaining

        state["last_position"] = current_position
        state["last_attempted_target"] = None
        state["last_attempted_direction"] = None

    def _choose_roam_move(
        self,
        state: dict[str, object],
        current_position: tuple[int, int],
        context: UnitLogicContext,
    ) -> tuple[str, tuple[int, int]] | None:
        blocked_cells = state.get("blocked_cells")
        visit_counts = state.get("visit_counts")
        if not isinstance(blocked_cells, set):
            return None
        if not isinstance(visit_counts, dict):
            return None

        for _ in range(4):
            phase = state.get("phase")
            if phase == "done":
                return None

            preferred_direction = (
                state.get("vertical_direction")
                if phase == "shift_row"
                else state.get("sweep_direction")
            )
            vertical_direction = state.get("vertical_direction")
            sweep_direction = state.get("sweep_direction")
            if not isinstance(preferred_direction, str):
                return None

            candidate_directions = self._candidate_directions(preferred_direction, vertical_direction, sweep_direction)
            valid_candidates: list[tuple[tuple[int, int, int, int], str, tuple[int, int]]] = []
            preferred_target_blocked = False

            for candidate_index, direction in enumerate(candidate_directions):
                target = self._apply_direction(current_position, direction)

                if target[0] < 0 or target[1] < 0:
                    self._mark_blocked(state, target)
                    if direction == preferred_direction:
                        preferred_target_blocked = True
                    continue

                if target in blocked_cells:
                    if direction == preferred_direction:
                        preferred_target_blocked = True
                    continue

                score = self._move_score(
                    target=target,
                    direction=direction,
                    candidate_index=candidate_index,
                    preferred_direction=preferred_direction,
                    current_position=current_position,
                    visit_counts=visit_counts,
                    context=context,
                )
                valid_candidates.append((score, direction, target))

            if valid_candidates:
                _, chosen_direction, chosen_target = min(valid_candidates, key=lambda item: item[0])
                return chosen_direction, chosen_target

            if preferred_target_blocked or phase == "shift_row":
                if phase == "sweep":
                    state["phase"] = "shift_row"
                    state["shift_remaining"] = state.get("shift_stride", 1)
                    continue
                state["phase"] = "sweep"
                state["vertical_direction"] = self._reverse_vertical_direction(
                    state.get("vertical_direction")
                )
                state["sweep_direction"] = self._reverse_horizontal_direction(
                    state.get("sweep_direction")
                )
                state["shift_remaining"] = 0
                continue

        return None

    def _move_score(
        self,
        target: tuple[int, int],
        direction: str,
        candidate_index: int,
        preferred_direction: str,
        current_position: tuple[int, int],
        visit_counts: dict[tuple[int, int], int],
        context: UnitLogicContext,
    ) -> tuple[int, int, int, int, int]:
        known_cells = context.map_tracker.get_known_cells() if context.map_tracker is not None else {}
        is_known = target in known_cells
        frontier_penalty = 0
        if context.map_tracker is not None:
            frontier_penalty = -context.map_tracker.count_unknown_neighbors(target)

        preferred_penalty = 0 if direction == preferred_direction else 1
        visit_penalty = visit_counts.get(target, 0)
        distance_penalty = self._distance_tuple(current_position, target)

        return (
            1 if is_known else 0,
            visit_penalty,
            preferred_penalty,
            frontier_penalty,
            candidate_index + distance_penalty,
        )

    @classmethod
    def _candidate_directions(
        cls,
        preferred_direction: str,
        vertical_direction: object,
        sweep_direction: object,
    ) -> list[str]:
        directions: list[str] = [preferred_direction]

        if isinstance(vertical_direction, str) and vertical_direction not in directions:
            directions.append(vertical_direction)

        if isinstance(sweep_direction, str) and sweep_direction not in directions:
            directions.append(sweep_direction)

        reverse_preferred = cls._reverse_direction(preferred_direction)
        if reverse_preferred not in directions:
            directions.append(reverse_preferred)

        for direction in ("right", "down", "left", "up"):
            if direction not in directions:
                directions.append(direction)

        return directions

    @classmethod
    def _reverse_horizontal_direction(cls, direction: object) -> str:
        if direction == "left":
            return "right"
        return "left"

    @classmethod
    def _reverse_vertical_direction(cls, direction: object) -> str:
        if direction == "up":
            return "down"
        return "up"

    @classmethod
    def _reverse_direction(cls, direction: str) -> str:
        if direction == "right":
            return "left"
        if direction == "left":
            return "right"
        if direction == "down":
            return "up"
        return "down"

    @classmethod
    def _apply_direction(
        cls,
        current_position: tuple[int, int],
        direction: str,
    ) -> tuple[int, int]:
        dx, dy = cls._DIRECTION_VECTORS[direction]
        return (current_position[0] + dx, current_position[1] + dy)

    @staticmethod
    def _mark_blocked(state: dict[str, object], coordinates: tuple[int, int]) -> None:
        blocked_cells = state.get("blocked_cells")
        if isinstance(blocked_cells, set):
            blocked_cells.add(coordinates)

    @staticmethod
    def _distance_tuple(a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def _distance(a: Position, b: Position) -> int:
        return abs(a.x - b.x) + abs(a.y - b.y)

    @staticmethod
    def _is_on_fire_tile(unit_position: Position, fire_position: Position) -> bool:
        return unit_position.x == fire_position.x and unit_position.y == fire_position.y

DEFAULT_UNIT_LOGIC_BY_TYPE: dict[UnitType, BaseUnitLogic] = {
    UnitType.Firefighter: FirefighterLogic(),
    UnitType.Firetruck: FiretruckLogic(),
    UnitType.Firecopter: FirecopterLogic(),
}
