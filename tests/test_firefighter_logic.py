import unittest

from Entity import Position, SeenFire, Unit, UnitType
from Message import OperationId
from UnitLogic.context import UnitLogicContext
from UnitLogic.handlers import FirefighterLogic


class FirefighterLogicTests(unittest.IsolatedAsyncioTestCase):
    async def test_firefighter_paths_around_water_to_nearest_fire(self) -> None:
        moves: list[tuple[int, str]] = []
        commands: list[tuple[int, OperationId, object | None]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            commands.append((unit_id, operation, extra_json))

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firefighter,
            position=Position(0, 0),
            seen_fires=[SeenFire(Position(2, 0), 100)],
            seen_waters=[Position(1, 0)],
        )
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
        )

        await FirefighterLogic().run(unit, context)

        self.assertEqual(moves, [(1, "down")])
        self.assertEqual(commands, [])

    async def test_firefighter_does_not_repeat_same_move_before_position_changes(self) -> None:
        moves: list[tuple[int, str]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            raise AssertionError("No command expected")

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firefighter,
            position=Position(0, 0),
            seen_fires=[SeenFire(Position(2, 0), 100)],
            seen_waters=[Position(1, 0)],
        )
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
        )
        logic = FirefighterLogic()

        await logic.run(unit, context)
        await logic.run(unit, context)

        self.assertEqual(moves, [(1, "down")])

    async def test_firefighter_extinguishes_when_on_fire_tile(self) -> None:
        moves: list[tuple[int, str]] = []
        commands: list[tuple[int, OperationId, object | None]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            commands.append((unit_id, operation, extra_json))

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firefighter,
            position=Position(2, 0),
            seen_fires=[SeenFire(Position(2, 0), 100)],
        )
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
        )

        await FirefighterLogic().run(unit, context)

        self.assertEqual(moves, [])
        self.assertEqual(commands, [(1, OperationId.EXTINGUISH, None)])

    async def test_firefighter_extinguishes_when_next_to_fire_tile(self) -> None:
        moves: list[tuple[int, str]] = []
        commands: list[tuple[int, OperationId, object | None]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            commands.append((unit_id, operation, extra_json))

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firefighter,
            position=Position(1, 0),
            seen_fires=[SeenFire(Position(2, 0), 100)],
        )
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
        )

        await FirefighterLogic().run(unit, context)

        self.assertEqual(moves, [])
        self.assertEqual(commands, [(1, OperationId.EXTINGUISH, None)])

    async def test_firefighter_paths_to_adjacent_attack_tile(self) -> None:
        moves: list[tuple[int, str]] = []
        commands: list[tuple[int, OperationId, object | None]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            commands.append((unit_id, operation, extra_json))

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firefighter,
            position=Position(0, 0),
            seen_fires=[SeenFire(Position(2, 0), 100)],
        )
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
        )

        await FirefighterLogic().run(unit, context)

        self.assertEqual(moves, [(1, "right")])
        self.assertEqual(commands, [])

    async def test_firefighter_uses_drone_fire_data_when_it_sees_no_fire(self) -> None:
        moves: list[tuple[int, str]] = []

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation: OperationId, extra_json=None) -> None:
            raise AssertionError("No command expected")

        firefighter = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firefighter,
            position=Position(0, 0),
        )
        drone = Unit(
            unit_id=2,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(5, 5),
            seen_fires=[SeenFire(Position(2, 0), 100)],
        )
        context = UnitLogicContext(
            units_by_id={1: firefighter, 2: drone},
            queue_command=queue_command,
            queue_move=queue_move,
        )

        await FirefighterLogic().run(firefighter, context)

        self.assertEqual(moves, [(1, "right")])


if __name__ == "__main__":
    unittest.main()
