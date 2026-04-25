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
