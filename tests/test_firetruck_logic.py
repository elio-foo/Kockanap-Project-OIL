import unittest

from Entity import Position, SeenFire, Unit, UnitType
from Message import OperationId
from UnitLogic.context import UnitLogicContext
from UnitLogic.handlers import FiretruckLogic


class FiretruckLogicTests(unittest.IsolatedAsyncioTestCase):
    async def test_firetruck_uses_own_seen_fire_immediately(self) -> None:
        moves: list[tuple[int, str]] = []
        commands: list[tuple[int, OperationId, object | None]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            commands.append((unit_id, operation, extra_json))

        truck = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firetruck,
            position=Position(0, 0),
            current_water_level=5,
            seen_fires=[SeenFire(Position(2, 0), 100)],
        )
        context = UnitLogicContext(
            units_by_id={1: truck},
            queue_command=queue_command,
            queue_move=queue_move,
        )

        await FiretruckLogic().run(truck, context)

        self.assertEqual(moves, [(1, "right")])
        self.assertEqual(commands, [])

    async def test_firetruck_extinguishes_when_adjacent_to_seen_fire(self) -> None:
        moves: list[tuple[int, str]] = []
        commands: list[tuple[int, OperationId, object | None]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            commands.append((unit_id, operation, extra_json))

        truck = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firetruck,
            position=Position(1, 0),
            current_water_level=5,
            seen_fires=[SeenFire(Position(2, 0), 100)],
        )
        context = UnitLogicContext(
            units_by_id={1: truck},
            queue_command=queue_command,
            queue_move=queue_move,
        )

        await FiretruckLogic().run(truck, context)

        self.assertEqual(moves, [])
        self.assertEqual(commands, [(1, OperationId.EXTINGUISH, None)])

    async def test_firetruck_extinguishes_when_two_tiles_away_from_seen_fire(self) -> None:
        moves: list[tuple[int, str]] = []
        commands: list[tuple[int, OperationId, object | None]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            commands.append((unit_id, operation, extra_json))

        truck = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firetruck,
            position=Position(0, 0),
            current_water_level=5,
            seen_fires=[SeenFire(Position(2, 0), 100)],
        )
        context = UnitLogicContext(
            units_by_id={1: truck},
            queue_command=queue_command,
            queue_move=queue_move,
        )

        await FiretruckLogic().run(truck, context)

        self.assertEqual(moves, [(1, "right")])
        self.assertEqual(commands, [])

    async def test_firetruck_refills_earlier_when_low_on_water_and_no_fire(self) -> None:
        moves: list[tuple[int, str]] = []
        commands: list[tuple[int, OperationId, object | None]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            commands.append((unit_id, operation, extra_json))

        truck = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firetruck,
            position=Position(1, 1),
            current_water_level=2,
            seen_waters=[Position(2, 1)],
        )
        context = UnitLogicContext(
            units_by_id={1: truck},
            queue_command=queue_command,
            queue_move=queue_move,
        )

        await FiretruckLogic().run(truck, context)

        self.assertEqual(moves, [(1, "right")])
        self.assertEqual(commands, [])

    async def test_firetruck_roams_toward_frontier_around_known_water(self) -> None:
        moves: list[tuple[int, str]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            raise AssertionError("No command expected")

        truck = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firetruck,
            position=Position(0, 0),
            current_water_level=5,
            seen_waters=[Position(1, 0)],
        )

        class StubMapTracker:
            def get_frontier_cells(self) -> set[tuple[int, int]]:
                return {(2, 0)}

            def nearest_unknown_tile(self, origin: tuple[int, int]) -> tuple[int, int] | None:
                _ = origin
                return (2, 0)

            def count_unknown_neighbors(self, coordinates: tuple[int, int]) -> int:
                _ = coordinates
                return 1

            def is_within_detected_bounds(self, coordinates: tuple[int, int]) -> bool:
                return coordinates[0] >= 0 and coordinates[1] >= 0 and coordinates[0] <= 3 and coordinates[1] <= 3

            def get_known_cells(self) -> dict[tuple[int, int], str]:
                return {
                    (0, 0): ".",
                    (1, 0): "W",
                    (0, 1): ".",
                    (1, 1): ".",
                    (2, 1): ".",
                    (2, 0): ".",
                }

        context = UnitLogicContext(
            units_by_id={1: truck},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=StubMapTracker(),
        )

        await FiretruckLogic().run(truck, context)

        self.assertEqual(moves, [(1, "down")])

    async def test_firetruck_paths_around_water_when_chasing_seen_fire(self) -> None:
        moves: list[tuple[int, str]] = []
        commands: list[tuple[int, OperationId, object | None]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            commands.append((unit_id, operation, extra_json))

        truck = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firetruck,
            position=Position(0, 0),
            current_water_level=5,
            seen_fires=[SeenFire(Position(2, 0), 100)],
            seen_waters=[Position(1, 0)],
        )
        context = UnitLogicContext(
            units_by_id={1: truck},
            queue_command=queue_command,
            queue_move=queue_move,
        )

        await FiretruckLogic().run(truck, context)

        self.assertEqual(moves, [(1, "down")])
        self.assertEqual(commands, [])

    async def test_firetruck_roaming_prefers_empty_tile_over_fire_tile(self) -> None:
        moves: list[tuple[int, str]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            raise AssertionError("No command expected")

        truck = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firetruck,
            position=Position(0, 0),
            current_water_level=5,
        )

        class StubMapTracker:
            def get_frontier_cells(self) -> set[tuple[int, int]]:
                return set()

            def nearest_unknown_tile(self, origin: tuple[int, int]) -> tuple[int, int] | None:
                _ = origin
                return None

            def count_unknown_neighbors(self, coordinates: tuple[int, int]) -> int:
                _ = coordinates
                return 0

            def is_within_detected_bounds(self, coordinates: tuple[int, int]) -> bool:
                return coordinates[0] >= 0 and coordinates[1] >= 0

            def get_known_cells(self) -> dict[tuple[int, int], str]:
                return {
                    (0, 0): ".",
                    (1, 0): "F",
                    (0, 1): ".",
                }

        context = UnitLogicContext(
            units_by_id={1: truck},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=StubMapTracker(),
        )

        await FiretruckLogic().run(truck, context)

        self.assertEqual(moves, [(1, "down")])
