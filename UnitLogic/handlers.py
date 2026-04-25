from heapq import heappop, heappush

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
    _MOVE_OPTIONS = (
        ("right", (1, 0)),
        ("down", (0, 1)),
        ("left", (-1, 0)),
        ("up", (0, -1)),
    )

    def __init__(self) -> None:
        self._roam_state_by_unit: dict[int, dict[str, object]] = {}
        self._state_by_unit: dict[int, dict[str, object]] = {}

    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        if unit.id is None or unit.position is None:
            return

        state = self._get_or_create_state(unit)
        current_position = (unit.position.x, unit.position.y)

        if self._needs_refill(unit, state):
            state["mode"] = "refill"

        if state["mode"] == "firefight":
            handled = await self._run_firefight(unit, context, state)
            if handled:
                return

        if state["mode"] == "refill":
            handled = await self._run_refill(unit, context, state, current_position)
            if handled:
                return

        priority_fire = self._find_priority_fire_from_drone(unit, context)
        if priority_fire is not None and unit.currentWaterLevel > 0:
            self._lock_target_fire(state, priority_fire.position.x, priority_fire.position.y)
            self._reset_roam_progress(unit)
            await self._run_firefight(unit, context, state)
            return

        roam_direction = self._next_roam_direction(unit, context)
        if roam_direction is None:
            return

        state["mode"] = "roam"
        await context.queue_move(unit.id, roam_direction)

    async def _run_firefight(
        self,
        unit: Unit,
        context: UnitLogicContext,
        state: dict[str, object],
    ) -> bool:
        target_coordinates = state.get("target_fire")
        if not isinstance(target_coordinates, tuple):
            state["mode"] = "roam"
            return False

        if unit.currentWaterLevel <= 0:
            state["mode"] = "refill"
            return False

        live_target = self._find_fire_at_coordinates(context, target_coordinates)
        if live_target is None and unit.position.x == target_coordinates[0] and unit.position.y == target_coordinates[1]:
            self._reset_truck_state(unit)
            return False

        destination = live_target.position if live_target is not None else Position(*target_coordinates)
        state["mode"] = "firefight"

        if self._is_on_fire_tile(unit.position, destination):
            await context.queue_command(unit.id, OperationId.EXTINGUISH)
            return True

        direction = self._direction_towards(unit.position, destination)
        if direction is not None:
            await context.queue_move(unit.id, direction)
            return True

        return False

    async def _run_refill(
        self,
        unit: Unit,
        context: UnitLogicContext,
        state: dict[str, object],
        current_position: tuple[int, int],
    ) -> bool:
        if unit.currentWaterLevel >= unit.waterSupply:
            self._reset_truck_state(unit)
            return False

        water_target = self._resolve_refill_target(unit, context, state, current_position)
        if water_target is None:
            return False

        if current_position == water_target:
            await context.queue_command(unit.id, OperationId.REFILL)
            return True

        direction = self._direction_towards_tuple(current_position, water_target)
        if direction is not None:
            await context.queue_move(unit.id, direction)
            return True

        return False

    def _count_adjacent_fires(
        self,
        position: Position,
        fire_positions: set[tuple[int, int]],
    ) -> int:
        x, y = position.x, position.y
        adjacent_positions = [
            (x + 1, y),
            (x - 1, y),
            (x, y + 1),
            (x, y - 1),
        ]
        return sum(1 for pos in adjacent_positions if pos in fire_positions)

    def _find_priority_fire_from_drone(
        self,
        unit: Unit,
        context: UnitLogicContext,
    ) -> SeenFire | None:
        drone_fires = self._collect_active_fires(context, drone_only=True)
        if not drone_fires or unit.position is None:
            return None

        fire_positions = {(fire.position.x, fire.position.y) for fire in drone_fires}
        priority_fires = [
            fire
            for fire in drone_fires
            if self._count_adjacent_fires(fire.position, fire_positions) > 0
        ]
        if not priority_fires:
            return None

        return max(
            priority_fires,
            key=lambda fire: (
                self._count_adjacent_fires(fire.position, fire_positions),
                fire.hp,
                -self._distance(unit.position, fire.position),
            ),
        )

    def _find_fire_at_coordinates(
        self,
        context: UnitLogicContext,
        coordinates: tuple[int, int],
    ) -> SeenFire | None:
        for seen_fire in self._collect_active_fires(context):
            if (seen_fire.position.x, seen_fire.position.y) == coordinates:
                return seen_fire
        return None

    def _collect_active_fires(
        self,
        context: UnitLogicContext,
        drone_only: bool = False,
    ) -> list[SeenFire]:
        fires_by_position: dict[tuple[int, int], SeenFire] = {}

        for tracked_unit in context.units_by_id.values():
            if drone_only and tracked_unit.type is not UnitType.Firecopter:
                continue

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

        frontier_direction = self._direction_towards_frontier(unit, context)
        if frontier_direction is not None:
            return frontier_direction

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

    def _direction_towards_frontier(self, unit: Unit, context: UnitLogicContext) -> str | None:
        if unit.position is None or context.map_tracker is None:
            return None

        frontier = context.map_tracker.nearest_unknown_tile((unit.position.x, unit.position.y))
        if frontier is None:
            return None

        return self._direction_towards_tuple((unit.position.x, unit.position.y), frontier)

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

    def _get_or_create_state(self, unit: Unit) -> dict[str, object]:
        if unit.id is None:
            return {}

        existing_state = self._state_by_unit.get(unit.id)
        if existing_state is not None:
            return existing_state

        state: dict[str, object] = {
            "mode": "roam",
            "target_fire": None,
            "target_water": None,
        }
        self._state_by_unit[unit.id] = state
        return state

    def _lock_target_fire(self, state: dict[str, object], x: int, y: int) -> None:
        state["mode"] = "firefight"
        state["target_fire"] = (x, y)
        state["target_water"] = None

    def _needs_refill(self, unit: Unit, state: dict[str, object]) -> bool:
        mode = state.get("mode")
        return unit.currentWaterLevel <= 0 or mode == "refill"

    def _resolve_refill_target(
        self,
        unit: Unit,
        context: UnitLogicContext,
        state: dict[str, object],
        current_position: tuple[int, int],
    ) -> tuple[int, int] | None:
        known_target = state.get("target_water")
        if isinstance(known_target, tuple):
            return known_target

        water_positions = {
            (seen_water.x, seen_water.y)
            for tracked_unit in context.units_by_id.values()
            for seen_water in tracked_unit.seenWaters
        }

        if context.map_tracker is not None:
            tracked_water = context.map_tracker.nearest_water_tile(current_position)
            if tracked_water is not None:
                water_positions.add(tracked_water)

        if not water_positions:
            return None

        nearest_water = min(
            water_positions,
            key=lambda coordinates: self._distance_tuple(current_position, coordinates),
        )
        state["target_water"] = nearest_water
        return nearest_water

    def _reset_truck_state(self, unit: Unit) -> None:
        if unit.id is None:
            return

        state = self._state_by_unit.get(unit.id)
        if state is not None:
            state["mode"] = "roam"
            state["target_fire"] = None
            state["target_water"] = None

        self._reset_roam_progress(unit)

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


class FirecopterLogic(BaseUnitLogic):
    _FIRE_CELL = "F"
    _WATER_CELL = "W"
    _PATHFINDING_MARGIN = 8
    _MOVE_OPTIONS = (
        ("right", (1, 0)),
        ("down", (0, 1)),
        ("left", (-1, 0)),
        ("up", (0, -1)),
    )

    def __init__(self) -> None:
        self._roam_state_by_unit: dict[int, dict[str, object]] = {}
        self._issued_action_by_unit: dict[int, dict[str, object]] = {}

    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        if unit.id is None or unit.position is None:
            return

        target_fire, path_direction = self._find_nearest_reachable_fire(unit, context)
        if target_fire is not None:
            self._reset_roam_progress(unit)

            if self._is_in_attack_range(unit.position, target_fire.position):
                await self._queue_command_once(
                    unit,
                    context,
                    OperationId.EXTINGUISH,
                    self._coordinates_of(target_fire.position),
                    target_fire.hp,
                )
                return

            if path_direction is not None:
                await self._queue_move_once(
                    unit,
                    context,
                    path_direction,
                    self._coordinates_of(target_fire.position),
                )
            return

        roam_direction = self._next_roam_direction(unit)
        if roam_direction is None:
            return

        await self._queue_move_once(
            unit,
            context,
            roam_direction,
            self._target_for_direction(unit.position, roam_direction),
        )

    def _find_nearest_reachable_fire(
        self,
        unit: Unit,
        context: UnitLogicContext,
    ) -> tuple[SeenFire | None, str | None]:
        active_fires = self._collect_active_fires(context)
        if not active_fires or unit.position is None:
            return None, None

        unit_position = self._coordinates_of(unit.position)
        water_cells = self._collect_water_cells(context)
        known_cells = context.map_tracker.get_known_cells() if context.map_tracker is not None else {}

        sorted_fires = sorted(
            active_fires,
            key=lambda fire: (
                self._distance_tuple(unit_position, self._coordinates_of(fire.position)),
                -fire.hp,
            ),
        )

        for fire in sorted_fires:
            target = self._coordinates_of(fire.position)
            if self._distance_tuple(unit_position, target) <= 1:
                return fire, None

            for attack_position in self._attack_positions_for_fire(target, water_cells):
                path = self._find_path(
                    start=unit_position,
                    goal=attack_position,
                    water_cells=water_cells,
                    known_cells=known_cells,
                )
                if path:
                    return fire, path[0]

        return None, None

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

    def _attack_positions_for_fire(
        self,
        fire_position: tuple[int, int],
        water_cells: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        attack_positions: list[tuple[int, int]] = []

        for _, (dx, dy) in self._MOVE_OPTIONS:
            candidate = (fire_position[0] + dx, fire_position[1] + dy)
            if candidate[0] < 0 or candidate[1] < 0:
                continue
            if candidate in water_cells:
                continue
            attack_positions.append(candidate)

        return sorted(
            attack_positions,
            key=lambda position: (
                self._distance_tuple(position, fire_position),
                position[1],
                position[0],
            ),
        )

    def _collect_water_cells(self, context: UnitLogicContext) -> set[tuple[int, int]]:
        water_cells: set[tuple[int, int]] = set()

        if context.map_tracker is not None:
            water_cells.update(
                coordinates
                for coordinates, cell_type in context.map_tracker.get_known_cells().items()
                if cell_type == self._WATER_CELL
            )

        for tracked_unit in context.units_by_id.values():
            for seen_water in tracked_unit.seenWaters:
                water_cells.add((seen_water.x, seen_water.y))

        return water_cells

    def _find_path(
        self,
        *,
        start: tuple[int, int],
        goal: tuple[int, int],
        water_cells: set[tuple[int, int]],
        known_cells: dict[tuple[int, int], str],
    ) -> list[str] | None:
        if goal in water_cells:
            return None

        min_x, max_x, min_y, max_y = self._pathfinding_bounds(start, goal, known_cells, water_cells)
        frontier: list[tuple[int, int, tuple[int, int]]] = []
        heappush(frontier, (0, 0, start))
        came_from: dict[tuple[int, int], tuple[tuple[int, int], str] | None] = {start: None}
        cost_so_far: dict[tuple[int, int], int] = {start: 0}
        sequence = 0

        while frontier:
            _, _, current = heappop(frontier)

            if current == goal:
                return self._reconstruct_path(came_from, goal)

            for direction, (dx, dy) in self._MOVE_OPTIONS:
                neighbor = (current[0] + dx, current[1] + dy)
                if not self._is_within_bounds(neighbor, min_x, max_x, min_y, max_y):
                    continue
                if neighbor in water_cells:
                    continue

                new_cost = cost_so_far[current] + 1
                if new_cost >= cost_so_far.get(neighbor, 1_000_000_000):
                    continue

                cost_so_far[neighbor] = new_cost
                came_from[neighbor] = (current, direction)
                sequence += 1
                priority = new_cost + self._distance_tuple(neighbor, goal)
                heappush(frontier, (priority, sequence, neighbor))

        return None

    def _pathfinding_bounds(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        known_cells: dict[tuple[int, int], str],
        water_cells: set[tuple[int, int]],
    ) -> tuple[int, int, int, int]:
        relevant_cells = set(known_cells) | water_cells | {start, goal}
        min_x = max(0, min(x for x, _ in relevant_cells) - self._PATHFINDING_MARGIN)
        max_x = max(x for x, _ in relevant_cells) + self._PATHFINDING_MARGIN
        min_y = max(0, min(y for _, y in relevant_cells) - self._PATHFINDING_MARGIN)
        max_y = max(y for _, y in relevant_cells) + self._PATHFINDING_MARGIN
        return min_x, max_x, min_y, max_y

    @staticmethod
    def _is_within_bounds(
        coordinates: tuple[int, int],
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
    ) -> bool:
        x, y = coordinates
        return min_x <= x <= max_x and min_y <= y <= max_y

    @staticmethod
    def _reconstruct_path(
        came_from: dict[tuple[int, int], tuple[tuple[int, int], str] | None],
        goal: tuple[int, int],
    ) -> list[str]:
        path: list[str] = []
        current = goal

        while came_from[current] is not None:
            previous, direction = came_from[current]
            path.append(direction)
            current = previous

        path.reverse()
        return path

    async def _queue_move_once(
        self,
        unit: Unit,
        context: UnitLogicContext,
        direction: str,
        target: tuple[int, int],
    ) -> None:
        if unit.id is None or unit.position is None:
            return

        action = {
            "kind": "move",
            "position": self._coordinates_of(unit.position),
            "direction": direction,
            "target": target,
        }
        if self._is_duplicate_action(unit.id, action):
            return

        self._issued_action_by_unit[unit.id] = action
        await context.queue_move(unit.id, direction)

    async def _queue_command_once(
        self,
        unit: Unit,
        context: UnitLogicContext,
        operation: OperationId,
        target: tuple[int, int],
        target_hp: int,
    ) -> None:
        if unit.id is None or unit.position is None:
            return

        action = {
            "kind": operation.value,
            "position": self._coordinates_of(unit.position),
            "target": target,
            "target_hp": target_hp,
        }
        if self._is_duplicate_action(unit.id, action):
            return

        self._issued_action_by_unit[unit.id] = action
        await context.queue_command(unit.id, operation)

    def _is_duplicate_action(self, unit_id: int, action: dict[str, object]) -> bool:
        return self._issued_action_by_unit.get(unit_id) == action

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
    def _coordinates_of(position: Position) -> tuple[int, int]:
        return (position.x, position.y)

    @classmethod
    def _target_for_direction(cls, position: Position, direction: str) -> tuple[int, int]:
        for candidate_direction, (dx, dy) in cls._MOVE_OPTIONS:
            if candidate_direction == direction:
                return (position.x + dx, position.y + dy)

        return (position.x, position.y)

    @staticmethod
    def _is_on_fire_tile(unit_position: Position, fire_position: Position) -> bool:
        return unit_position.x == fire_position.x and unit_position.y == fire_position.y

    @classmethod
    def _is_in_attack_range(cls, unit_position: Position, fire_position: Position) -> bool:
        return cls._distance_tuple(
            (unit_position.x, unit_position.y),
            (fire_position.x, fire_position.y),
        ) <= 1

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
    _SCAN_START = (16, 16)
    _VERTICAL_SHIFT_OVERLAP_TILES = 2
    _WATER_CELL = "W"
    _FRONTIER_MARGIN = 2
    _LOOP_STREAK_LIMIT = 4
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

    def _collect_water_cells(self, context: UnitLogicContext) -> set[tuple[int, int]]:
        water_cells: set[tuple[int, int]] = set()

        if context.map_tracker is not None:
            water_cells.update(
                coordinates
                for coordinates, cell_type in context.map_tracker.get_known_cells().items()
                if cell_type == self._WATER_CELL
            )

        for tracked_unit in context.units_by_id.values():
            for seen_water in tracked_unit.seenWaters:
                water_cells.add((seen_water.x, seen_water.y))

        return water_cells

    def _next_roam_direction(self, unit: Unit, context: UnitLogicContext) -> str | None:
        if unit.id is None or unit.position is None:
            return None

        state = self._get_or_create_roam_state(unit)
        state["shift_stride"] = self._vertical_shift_stride(unit)
        current_position = (unit.position.x, unit.position.y)
        self._apply_roam_feedback(state, current_position, context, unit)

        move_choice = self._choose_roam_move(state, current_position, context, unit)
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
            "stalled_target": None,
            "stalled_attempts": 0,
            "position_streak": 1,
            "phase": "return_to_corner",
            "sweep_direction": "right",
            "vertical_direction": "down",
            "shift_stride": self._vertical_shift_stride(unit),
            "shift_remaining": 0,
            "blocked_cells": set(),
            "visit_counts": {origin: 1},
        }
        self._roam_state_by_unit[unit.id] = state
        return state

    @classmethod
    def _vertical_shift_stride(cls, unit: Unit) -> int:
        return max(1, unit.sightTiles - cls._VERTICAL_SHIFT_OVERLAP_TILES)

    def _apply_roam_feedback(
        self,
        state: dict[str, object],
        current_position: tuple[int, int],
        context: UnitLogicContext,
        unit: Unit,
    ) -> None:
        last_position = state.get("last_position")
        last_attempted_target = state.get("last_attempted_target")
        phase = state.get("phase")
        shift_remaining = state.get("shift_remaining", 0)
        visit_counts = state.get("visit_counts")
        explicit_visible_cells = self._explicit_visible_cells(unit)
        position_streak = state.get("position_streak", 0)

        if isinstance(last_position, tuple) and current_position == last_position:
            if isinstance(position_streak, int):
                position_streak += 1
            else:
                position_streak = 1
        else:
            position_streak = 1
        state["position_streak"] = position_streak

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
            stalled_target = state.get("stalled_target")
            stalled_attempts = state.get("stalled_attempts", 0)
            if stalled_target == last_attempted_target and isinstance(stalled_attempts, int):
                stalled_attempts += 1
            else:
                stalled_target = last_attempted_target
                stalled_attempts = 1

            state["stalled_target"] = stalled_target
            state["stalled_attempts"] = stalled_attempts

            if stalled_attempts >= 2:
                self._mark_blocked(state, last_attempted_target)
                if (
                    context.map_tracker is not None
                    and last_attempted_target not in explicit_visible_cells
                ):
                    context.map_tracker.record_failed_move(current_position, last_attempted_target)
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
                state["stalled_target"] = None
                state["stalled_attempts"] = 0
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

        if not (
            isinstance(last_position, tuple)
            and isinstance(last_attempted_target, tuple)
            and current_position == last_position
        ):
            state["stalled_target"] = None
            state["stalled_attempts"] = 0

        if position_streak >= self._LOOP_STREAK_LIMIT:
            self._break_loop(state, current_position, context, unit)
            state["position_streak"] = 1

        state["last_position"] = current_position
        state["last_attempted_target"] = None
        state["last_attempted_direction"] = None

    def _choose_roam_move(
        self,
        state: dict[str, object],
        current_position: tuple[int, int],
        context: UnitLogicContext,
        unit: Unit,
    ) -> tuple[str, tuple[int, int]] | None:
        blocked_cells = state.get("blocked_cells")
        visit_counts = state.get("visit_counts")
        water_cells = self._collect_water_cells(context)
        if not isinstance(blocked_cells, set):
            return None
        if not isinstance(visit_counts, dict):
            return None

        phase = state.get("phase")
        if phase == "return_to_corner":
            move_choice = self._move_towards_corner(state, current_position, water_cells)
            if move_choice is not None:
                return move_choice
            if state.get("phase") == "move_to_scan_start":
                return self._move_towards_scan_start(state, current_position, context, water_cells, unit)
            return None
        if phase == "move_to_scan_start":
            return self._move_towards_scan_start(state, current_position, context, water_cells, unit)
        if self._should_switch_to_frontier_hunt(state, context):
            state["phase"] = "frontier_hunt"
        if phase == "frontier_hunt" or state.get("phase") == "frontier_hunt":
            return self._move_towards_frontier(state, current_position, context, water_cells, unit)

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

                if context.map_tracker is not None and not context.map_tracker.is_within_detected_bounds(target):
                    self._mark_blocked(state, target)
                    if direction == preferred_direction:
                        preferred_target_blocked = True
                    continue

                if target in blocked_cells:
                    if direction == preferred_direction:
                        preferred_target_blocked = True
                    continue
                if target in water_cells:
                    self._mark_blocked(state, target)
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

    def _move_towards_corner(
        self,
        state: dict[str, object],
        current_position: tuple[int, int],
        water_cells: set[tuple[int, int]],
    ) -> tuple[str, tuple[int, int]] | None:
        if (0, 0) in water_cells:
            state["phase"] = "move_to_scan_start"
            return None

        if current_position == (0, 0):
            state["phase"] = "move_to_scan_start"
            return None

        candidate_directions: list[str] = []
        if current_position[0] > 0:
            candidate_directions.append("left")
        if current_position[1] > 0:
            candidate_directions.append("up")

        blocked_cells = state.get("blocked_cells")
        if not isinstance(blocked_cells, set):
            return None

        for direction in candidate_directions:
            target = self._apply_direction(current_position, direction)
            if target in water_cells:
                self._mark_blocked(state, target)
                continue
            if target in blocked_cells:
                continue
            return direction, target

        # If we cannot make progress toward the corner, fall back to the scan-start phase.
        state["phase"] = "move_to_scan_start"

        return None

    def _move_towards_scan_start(
        self,
        state: dict[str, object],
        current_position: tuple[int, int],
        context: UnitLogicContext,
        water_cells: set[tuple[int, int]],
        unit: Unit,
    ) -> tuple[str, tuple[int, int]] | None:
        target_position = self._resolved_scan_start(context, water_cells, unit)
        if current_position == target_position:
            state["phase"] = "sweep"
            state["sweep_direction"] = self._assigned_sweep_direction(unit, context)
            state["vertical_direction"] = self._assigned_vertical_direction(unit, context)
            state["shift_remaining"] = 0
            return self._choose_roam_move(state, current_position, context, unit)

        blocked_cells = state.get("blocked_cells")
        if not isinstance(blocked_cells, set):
            return None

        candidate_directions: list[str] = []
        rank, _ = self._copter_rank(unit, context)
        prefer_vertical_first = rank % 3 == 1

        if prefer_vertical_first:
            if current_position[1] < target_position[1]:
                candidate_directions.append("down")
            elif current_position[1] > target_position[1]:
                candidate_directions.append("up")
            if current_position[0] < target_position[0]:
                candidate_directions.append("right")
            elif current_position[0] > target_position[0]:
                candidate_directions.append("left")
        else:
            if current_position[0] < target_position[0]:
                candidate_directions.append("right")
            elif current_position[0] > target_position[0]:
                candidate_directions.append("left")
            if current_position[1] < target_position[1]:
                candidate_directions.append("down")
            elif current_position[1] > target_position[1]:
                candidate_directions.append("up")

        for direction in candidate_directions:
            target = self._apply_direction(current_position, direction)
            if context.map_tracker is not None and not context.map_tracker.is_within_detected_bounds(target):
                self._mark_blocked(state, target)
                continue
            if target in water_cells:
                self._mark_blocked(state, target)
                continue
            if target in blocked_cells:
                continue
            return direction, target

        return None

    @classmethod
    def _resolved_scan_start(
        cls,
        context: UnitLogicContext,
        water_cells: set[tuple[int, int]],
        unit: Unit,
    ) -> tuple[int, int]:
        target_x, target_y = cls._assigned_scan_start(unit, context)
        map_tracker = context.map_tracker
        if map_tracker is None:
            while (target_x, target_y) in water_cells and (target_x > 0 or target_y > 0):
                if target_x > 0:
                    target_x -= 1
                if target_y > 0:
                    target_y -= 1
            return target_x, target_y

        while target_x > 0 and not map_tracker.is_within_detected_bounds((target_x, 0)):
            target_x -= 1
        while target_y > 0 and not map_tracker.is_within_detected_bounds((0, target_y)):
            target_y -= 1

        while (target_x, target_y) in water_cells and (target_x > 0 or target_y > 0):
            if target_x > 0:
                target_x -= 1
            if target_y > 0:
                target_y -= 1

        return target_x, target_y

    @staticmethod
    def _explicit_visible_cells(unit: Unit) -> set[tuple[int, int]]:
        return {
            (tile.x, tile.y)
            for tile in unit.visibleTiles
            if tile.x >= 0 and tile.y >= 0
        }

    def _should_switch_to_frontier_hunt(
        self,
        state: dict[str, object],
        context: UnitLogicContext,
    ) -> bool:
        if state.get("phase") == "frontier_hunt":
            return True
        if context.map_tracker is None:
            return False
        return context.map_tracker.has_detected_full_bounds()

    def _move_towards_frontier(
        self,
        state: dict[str, object],
        current_position: tuple[int, int],
        context: UnitLogicContext,
        water_cells: set[tuple[int, int]],
        unit: Unit,
    ) -> tuple[str, tuple[int, int]] | None:
        map_tracker = context.map_tracker
        if map_tracker is None:
            return None

        blocked_cells = state.get("blocked_cells")
        if not isinstance(blocked_cells, set):
            return None

        center = map_tracker.detected_center()
        if center is None:
            return None

        if current_position != center:
            path = self._find_copter_path(
                start=current_position,
                goal=center,
                water_cells=water_cells,
                blocked_cells=blocked_cells,
                map_tracker=map_tracker,
            )
            if path:
                direction = path[0]
                return direction, self._apply_direction(current_position, direction)

        frontier_cells = [
            coordinates
            for coordinates in map_tracker.get_frontier_cells()
            if coordinates not in water_cells and coordinates not in blocked_cells
        ]
        if not frontier_cells:
            return self._best_local_unknown_move(
                current_position=current_position,
                blocked_cells=blocked_cells,
                water_cells=water_cells,
                context=context,
            )

        anchor = self._frontier_anchor(unit, context, center)
        target = min(
            frontier_cells,
            key=lambda coordinates: (
                self._distance_tuple(anchor, coordinates),
                self._distance_tuple(current_position, coordinates),
                -map_tracker.count_unknown_neighbors(coordinates),
                coordinates[1],
                coordinates[0],
            ),
        )
        path = self._find_copter_path(
            start=current_position,
            goal=target,
            water_cells=water_cells,
            blocked_cells=blocked_cells,
            map_tracker=map_tracker,
        )
        if path:
            direction = path[0]
            return direction, self._apply_direction(current_position, direction)

        blocked_cells.add(target)
        return self._best_local_unknown_move(
            current_position=current_position,
            blocked_cells=blocked_cells,
            water_cells=water_cells,
            context=context,
        )

    def _best_local_unknown_move(
        self,
        *,
        current_position: tuple[int, int],
        blocked_cells: set[tuple[int, int]],
        water_cells: set[tuple[int, int]],
        context: UnitLogicContext,
    ) -> tuple[str, tuple[int, int]] | None:
        candidates: list[tuple[tuple[int, int, int], str, tuple[int, int]]] = []
        for candidate_index, direction in enumerate(("right", "down", "left", "up")):
            target = self._apply_direction(current_position, direction)
            if target[0] < 0 or target[1] < 0:
                continue
            if context.map_tracker is not None and not context.map_tracker.is_within_detected_bounds(target):
                continue
            if target in blocked_cells or target in water_cells:
                continue
            unknown_score = 0
            if context.map_tracker is not None:
                unknown_score = -context.map_tracker.count_unknown_neighbors(target)
            candidates.append(((unknown_score, candidate_index, self._distance_tuple(current_position, target)), direction, target))

        if not candidates:
            return None

        _, direction, target = min(candidates, key=lambda item: item[0])
        return direction, target

    def _find_copter_path(
        self,
        *,
        start: tuple[int, int],
        goal: tuple[int, int],
        water_cells: set[tuple[int, int]],
        blocked_cells: set[tuple[int, int]],
        map_tracker,
    ) -> list[str] | None:
        if goal in water_cells or goal in blocked_cells:
            return None
        if not map_tracker.is_within_detected_bounds(goal):
            return None

        min_x, max_x, min_y, max_y = self._copter_path_bounds(start, goal, map_tracker)
        frontier: list[tuple[int, int, tuple[int, int]]] = [(0, 0, start)]
        came_from: dict[tuple[int, int], tuple[tuple[int, int], str] | None] = {start: None}
        cost_so_far: dict[tuple[int, int], int] = {start: 0}
        sequence = 0

        while frontier:
            _, _, current = heappop(frontier)
            if current == goal:
                return self._reconstruct_copter_path(came_from, goal)

            for direction, (dx, dy) in self._DIRECTION_VECTORS.items():
                neighbor = (current[0] + dx, current[1] + dy)
                if not (min_x <= neighbor[0] <= max_x and min_y <= neighbor[1] <= max_y):
                    continue
                if not map_tracker.is_within_detected_bounds(neighbor):
                    continue
                if neighbor in water_cells or neighbor in blocked_cells:
                    continue

                new_cost = cost_so_far[current] + 1
                if new_cost >= cost_so_far.get(neighbor, 1_000_000_000):
                    continue

                cost_so_far[neighbor] = new_cost
                came_from[neighbor] = (current, direction)
                sequence += 1
                priority = new_cost + self._distance_tuple(neighbor, goal)
                heappush(frontier, (priority, sequence, neighbor))

        return None

    def _copter_path_bounds(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        map_tracker,
    ) -> tuple[int, int, int, int]:
        relevant_cells = set(map_tracker.get_known_cells()) | {start, goal}
        min_x = max(0, min(x for x, _ in relevant_cells) - self._FRONTIER_MARGIN)
        max_x = max(x for x, _ in relevant_cells) + self._FRONTIER_MARGIN
        min_y = max(0, min(y for _, y in relevant_cells) - self._FRONTIER_MARGIN)
        max_y = max(y for _, y in relevant_cells) + self._FRONTIER_MARGIN
        return min_x, max_x, min_y, max_y

    @staticmethod
    def _reconstruct_copter_path(
        came_from: dict[tuple[int, int], tuple[tuple[int, int], str] | None],
        goal: tuple[int, int],
    ) -> list[str]:
        path: list[str] = []
        current = goal
        while came_from[current] is not None:
            previous, direction = came_from[current]
            path.append(direction)
            current = previous
        path.reverse()
        return path

    def _break_loop(
        self,
        state: dict[str, object],
        current_position: tuple[int, int],
        context: UnitLogicContext,
        unit: Unit,
    ) -> None:
        blocked_cells = state.get("blocked_cells")
        if isinstance(blocked_cells, set):
            last_attempted_target = state.get("last_attempted_target")
            if isinstance(last_attempted_target, tuple):
                blocked_cells.add(last_attempted_target)

        state["shift_remaining"] = 0
        state["stalled_target"] = None
        state["stalled_attempts"] = 0
        state["sweep_direction"] = self._reverse_horizontal_direction(
            state.get("sweep_direction")
        )
        state["vertical_direction"] = self._reverse_vertical_direction(
            state.get("vertical_direction")
        )
        if context.map_tracker is not None and context.map_tracker.has_detected_full_bounds():
            state["phase"] = "frontier_hunt"
        else:
            state["phase"] = "move_to_scan_start"

    @classmethod
    def _firecopter_units(cls, context: UnitLogicContext) -> list[Unit]:
        return sorted(
            [
                tracked_unit
                for tracked_unit in context.units_by_id.values()
                if tracked_unit.type == UnitType.Firecopter and tracked_unit.id is not None
            ],
            key=lambda tracked_unit: tracked_unit.id,
        )

    @classmethod
    def _copter_rank(cls, unit: Unit, context: UnitLogicContext) -> tuple[int, int]:
        firecopters = cls._firecopter_units(context)
        if unit.id is None or not firecopters:
            return 0, 1
        for index, tracked_unit in enumerate(firecopters):
            if tracked_unit.id == unit.id:
                return index, len(firecopters)
        return 0, max(1, len(firecopters))

    @classmethod
    def _assigned_scan_start(cls, unit: Unit, context: UnitLogicContext) -> tuple[int, int]:
        rank, count = cls._copter_rank(unit, context)
        base_x, base_y = cls._SCAN_START
        if count <= 1:
            return cls._SCAN_START
        if rank % 3 == 0:
            return (base_x, max(4, base_y // 4))
        if rank % 3 == 1:
            return (max(4, base_x // 4), base_y)
        return cls._SCAN_START

    @classmethod
    def _assigned_sweep_direction(cls, unit: Unit, context: UnitLogicContext) -> str:
        rank, _ = cls._copter_rank(unit, context)
        return "right" if rank % 2 == 0 else "down"

    @classmethod
    def _assigned_vertical_direction(cls, unit: Unit, context: UnitLogicContext) -> str:
        _ = (unit, context)
        return "down"

    @classmethod
    def _frontier_anchor(
        cls,
        unit: Unit,
        context: UnitLogicContext,
        center: tuple[int, int],
    ) -> tuple[int, int]:
        rank, count = cls._copter_rank(unit, context)
        if count <= 1:
            return center
        cx, cy = center
        if rank % 3 == 0:
            return (cx, max(0, cy // 2))
        if rank % 3 == 1:
            return (max(0, cx // 2), cy)
        return center

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
