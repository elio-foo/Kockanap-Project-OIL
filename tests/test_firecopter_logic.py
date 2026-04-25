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

    async def test_repeated_logic_without_new_observation_does_not_detect_border(self) -> None:
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
        await logic.run(unit, context)
        await logic.run(unit, context)

        self.assertTrue(tracker.is_within_detected_bounds((1, 0)))
        self.assertEqual(moves, [(1, "right")])

    async def test_firecopter_detects_two_tile_loop_pattern(self) -> None:
        logic = FirecopterLogic()
        self.assertTrue(logic._is_two_tile_loop([(0, 0), (1, 0), (0, 0), (1, 0)]))
        self.assertFalse(logic._is_two_tile_loop([(0, 0), (1, 0), (1, 1), (1, 0)]))

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

    async def test_visible_target_does_not_get_recorded_as_border(self) -> None:
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
            visible_tiles=[Position(1, 0)],
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

        self.assertTrue(tracker.is_within_detected_bounds((1, 0)))

    async def test_copter_heads_to_middle_after_borders_are_known(self) -> None:
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
        tracker.record_failed_move((8, 8), (9, 8))
        tracker.record_failed_move((8, 8), (8, 9))

        moved_unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(0, 0),
            sight_tiles=1,
        )
        tracker.update_from_units({1: moved_unit})
        context = UnitLogicContext(
            units_by_id={1: moved_unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        await logic.run(moved_unit, context)

        self.assertEqual(moves, [(1, "right")])

    async def test_copter_uses_frontier_hunt_from_middle(self) -> None:
        moves: list[tuple[int, str]] = []
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        tracker = MapTracker(Path(temp_dir.name) / "map.txt")
        logic = FirecopterLogic()

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation, extra_json=None) -> None:
            raise AssertionError("No command expected")

        tracker.record_failed_move((8, 8), (9, 8))
        tracker.record_failed_move((8, 8), (8, 9))
        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(4, 4),
            sight_tiles=1,
            visible_tiles=[Position(4, 4), Position(4, 3), Position(4, 5), Position(3, 4)],
        )
        tracker.update_from_units({1: unit})
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        state = logic._get_or_create_roam_state(unit)
        state["phase"] = "frontier_hunt"

        await logic.run(unit, context)

        self.assertEqual(len(moves), 1)
        _, direction = moves[0]
        target = logic._apply_direction((4, 4), direction)
        self.assertIn(target, tracker.get_frontier_cells())

    async def test_multiple_copters_get_different_scan_start_biases(self) -> None:
        first_moves: list[tuple[int, str]] = []
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        tracker = MapTracker(Path(temp_dir.name) / "map.txt")
        logic = FirecopterLogic()

        async def queue_move(unit_id: int, direction: str) -> None:
            first_moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation, extra_json=None) -> None:
            raise AssertionError("No command expected")

        units = {
            1: Unit(
                unit_id=1,
                owner="ObudaInnovationLab",
                unit_type=UnitType.Firecopter,
                position=Position(0, 0),
                sight_tiles=16,
            ),
            2: Unit(
                unit_id=2,
                owner="ObudaInnovationLab",
                unit_type=UnitType.Firecopter,
                position=Position(0, 0),
                sight_tiles=16,
            ),
            3: Unit(
                unit_id=3,
                owner="ObudaInnovationLab",
                unit_type=UnitType.Firecopter,
                position=Position(0, 0),
                sight_tiles=16,
            ),
        }

        tracker.update_from_units(units)
        for unit in units.values():
            context = UnitLogicContext(
                units_by_id=units,
                queue_command=queue_command,
                queue_move=queue_move,
                map_tracker=tracker,
            )
            await logic.run(unit, context)

        directions_by_unit = dict(first_moves)
        self.assertEqual(directions_by_unit[1], "right")
        self.assertEqual(directions_by_unit[2], "down")
        self.assertEqual(directions_by_unit[3], "right")

    async def test_copter_breaks_loop_after_four_same_positions(self) -> None:
        moves: list[tuple[int, str]] = []
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        tracker = MapTracker(Path(temp_dir.name) / "map.txt")
        logic = FirecopterLogic()

        async def queue_move(unit_id: int, direction: str) -> None:
            moves.append((unit_id, direction))

        async def queue_command(unit_id: int, operation, extra_json=None) -> None:
            raise AssertionError("No command expected")

        tracker.record_failed_move((8, 8), (9, 8))
        tracker.record_failed_move((8, 8), (8, 9))
        unit = Unit(
            unit_id=1,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(4, 4),
            sight_tiles=1,
        )
        tracker.update_from_units({1: unit})
        context = UnitLogicContext(
            units_by_id={1: unit},
            queue_command=queue_command,
            queue_move=queue_move,
            map_tracker=tracker,
        )

        state = logic._get_or_create_roam_state(unit)
        state["phase"] = "sweep"
        state["position_streak"] = 3
        state["last_position"] = (4, 4)
        state["last_attempted_target"] = (5, 4)
        state["sweep_direction"] = "right"
        state["vertical_direction"] = "down"

        await logic.run(unit, context)

        self.assertEqual(state["phase"], "frontier_hunt")
        self.assertEqual(len(moves), 1)


if __name__ == "__main__":
    unittest.main()
