import tempfile
import unittest
from pathlib import Path

from Entity import Position, Unit, UnitType
from UnitLogic.context import UnitLogicContext
from UnitLogic.handlers import FirecopterLogic
from UnitLogic.map_tracker import MapTracker


class FirecopterLogicTests(unittest.IsolatedAsyncioTestCase):
    async def test_firecopter_returns_to_zero_zero_before_sweeping(self) -> None:
        moves: list[tuple[int, str]] = []
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        tracker = MapTracker(Path(temp_dir.name) / "map.txt")
        logic = FirecopterLogic()

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation, extra_json=None) -> None:
            raise AssertionError("No command expected")

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(5, 5),
            sight_tiles=1,
        )

        tracker.update_from_units({1: unit})
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        await logic.run(unit, context)
        self.assertEqual(moves, [(1, "left")])

    async def test_firecopter_heads_to_scan_start_after_reaching_corner(self) -> None:
        moves: list[tuple[int, str]] = []
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        tracker = MapTracker(Path(temp_dir.name) / "map.txt")
        logic = FirecopterLogic()

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation, extra_json=None) -> None:
            raise AssertionError("No command expected")

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(0, 0),
            sight_tiles=16,
        )

        tracker.update_from_units({1: unit})
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        await logic.run(unit, context)
        self.assertEqual(moves, [(1, "right")])

    async def test_firecopter_falls_back_to_scan_start_when_corner_is_unreachable(self) -> None:
        moves: list[tuple[int, str]] = []
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        tracker = MapTracker(Path(temp_dir.name) / "map.txt")
        logic = FirecopterLogic()

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation, extra_json=None) -> None:
            raise AssertionError("No command expected")

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(5, 5),
            sight_tiles=16,
        )

        tracker.update_from_units({1: unit})
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        state = logic._get_or_create_roam_state(unit)
        state["blocked_cells"] = {(4, 5), (5, 4)}

        await logic.run(unit, context)

        self.assertEqual(moves, [(1, "right")])

    async def test_firecopter_skips_corner_when_zero_zero_is_water(self) -> None:
        moves: list[tuple[int, str]] = []
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        tracker = MapTracker(Path(temp_dir.name) / "map.txt")
        logic = FirecopterLogic()

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation, extra_json=None) -> None:
            raise AssertionError("No command expected")

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(5, 5),
            sight_tiles=16,
            seen_waters=[Position(0, 0)],
        )

        tracker.update_from_units({1: unit})
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        await logic.run(unit, context)

        self.assertEqual(moves, [(1, "right")])

    async def test_single_stalled_update_does_not_detect_border(self) -> None:
        moves: list[tuple[int, str]] = []
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        tracker = MapTracker(Path(temp_dir.name) / "map.txt")
        logic = FirecopterLogic()

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation, extra_json=None) -> None:
            raise AssertionError("No command expected")

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(0, 0),
            sight_tiles=1,
        )

        tracker.update_from_units({1: unit})
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        await logic.run(unit, context)
        self.assertEqual(moves, [(1, "right")])

        stalled_unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(0, 0),
            sight_tiles=1,
        )

        tracker.update_from_units({1: stalled_unit})
        stalled_context = UnitLogicContext(
            units_by_id={1: stalled_unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        await logic.run(stalled_unit, stalled_context)

        self.assertTrue(tracker.is_within_detected_bounds((1, 0)))
        self.assertEqual(moves[-1][1], "right")

    async def test_repeated_stalled_updates_detect_right_border(self) -> None:
        moves: list[tuple[int, str]] = []
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        tracker = MapTracker(Path(temp_dir.name) / "map.txt")
        logic = FirecopterLogic()

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation, extra_json=None) -> None:
            raise AssertionError("No command expected")

        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(0, 0),
            sight_tiles=1,
        )

        tracker.update_from_units({1: unit})
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        await logic.run(unit, context)

        stalled_unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(0, 0),
            sight_tiles=1,
        )

        tracker.update_from_units({1: stalled_unit})
        stalled_context = UnitLogicContext(
            units_by_id={1: stalled_unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        await logic.run(stalled_unit, stalled_context)
        tracker.update_from_units({1: stalled_unit})
        await logic.run(stalled_unit, stalled_context)

        self.assertFalse(tracker.is_within_detected_bounds((1, 0)))
        self.assertNotEqual(moves[-1][1], "right")


if __name__ == "__main__":
    unittest.main()
