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
    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        todos("Implement firefighter behavior here.")
        _ = (unit, context)


class FiretruckLogic(BaseUnitLogic):
    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        todos("Implement firetruck behavior here.")
        _ = (unit, context)


class FirecopterLogic(BaseUnitLogic):
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
                # The copter ignores fire as blocked terrain and flies straight to the target tile.
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

            # Prefer less-visited tiles first, then stay relatively close to the starting area,
            # while still rotating tie-breaks so the copter doesn't bias one direction forever.
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


DEFAULT_UNIT_LOGIC_BY_TYPE: dict[UnitType, BaseUnitLogic] = {
    UnitType.Firefighter: FirefighterLogic(),
    UnitType.Firetruck: FiretruckLogic(),
    UnitType.Firecopter: FirecopterLogic(),
}
