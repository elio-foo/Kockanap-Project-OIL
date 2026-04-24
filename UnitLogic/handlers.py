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
            "blocked_cells": set(),
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
        state["last_attempted_direction"] = None

    def _apply_roam_feedback(self, state: dict[str, object], current_position: tuple[int, int]) -> None:
        last_position = state.get("last_position")
        last_attempted_target = state.get("last_attempted_target")
        phase = state.get("phase")

        if (
            isinstance(last_position, tuple)
            and isinstance(last_attempted_target, tuple)
            and current_position == last_position
        ):
            self._mark_blocked(state, last_attempted_target)
            if phase == "sweep":
                state["phase"] = "shift_row"
            elif phase == "shift_row":
                state["phase"] = "done"
        elif phase == "shift_row":
            state["phase"] = "sweep"
            state["sweep_direction"] = self._reverse_horizontal_direction(
                state.get("sweep_direction")
            )

        state["last_position"] = current_position
        state["last_attempted_target"] = None
        state["last_attempted_direction"] = None

    def _choose_roam_move(
        self,
        state: dict[str, object],
        current_position: tuple[int, int],
    ) -> tuple[str, tuple[int, int]] | None:
        blocked_cells = state.get("blocked_cells")
        if not isinstance(blocked_cells, set):
            return None

        for _ in range(4):
            phase = state.get("phase")
            if phase == "done":
                return None

            direction = state.get("vertical_direction") if phase == "shift_row" else state.get("sweep_direction")
            if not isinstance(direction, str):
                return None

            target = self._apply_direction(current_position, direction)
            if target[0] < 0 or target[1] < 0:
                self._mark_blocked(state, target)
                if phase == "sweep":
                    state["phase"] = "shift_row"
                    continue
                state["phase"] = "done"
                return None

            if target in blocked_cells:
                if phase == "sweep":
                    state["phase"] = "shift_row"
                    continue
                state["phase"] = "done"
                return None

            return direction, target

        return None

    @classmethod
    def _reverse_horizontal_direction(cls, direction: object) -> str:
        if direction == "left":
            return "right"
        return "left"

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
