import tempfile
import unittest
from pathlib import Path

from Entity import Position, SeenFire, Unit, UnitType
from UnitLogic.map_tracker import MapTracker


class MapTrackerFireMemoryTests(unittest.TestCase):
    def _tracker(self) -> MapTracker:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return MapTracker(Path(temp_dir.name) / "map.txt")

    def _unit(
        self,
        *,
        unit_id: int = 1,
        position: tuple[int, int],
        sight_tiles: int,
        seen_fires: list[SeenFire] | None = None,
        visible_tiles: list[tuple[int, int]] | None = None,
    ) -> Unit:
        return Unit(
            unit_id=unit_id,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(*position),
            sight_tiles=sight_tiles,
            seen_fires=seen_fires or [],
            visible_tiles=[Position(x, y) for x, y in (visible_tiles or [])],
        )

    def test_fire_memory_stays_until_visible_again(self) -> None:
        tracker = self._tracker()
        first_tick = self._unit(
            position=(0, 0),
            sight_tiles=2,
            seen_fires=[SeenFire(Position(1, 0), 100)],
        )

        tracker.update_from_units({1: first_tick})
        self.assertEqual(tracker.get_known_cells()[(1, 0)], "F")

        second_tick = self._unit(position=(5, 5), sight_tiles=1)
        tracker.update_from_units({1: second_tick})

        self.assertEqual(tracker.get_known_cells()[(1, 0)], "F")

    def test_fire_memory_clears_after_leaving_sight_and_recheck(self) -> None:
        tracker = self._tracker()
        first_tick = self._unit(
            position=(0, 0),
            sight_tiles=2,
            seen_fires=[SeenFire(Position(1, 0), 100)],
        )
        tracker.update_from_units({1: first_tick})

        second_tick = self._unit(position=(5, 5), sight_tiles=1)
        tracker.update_from_units({1: second_tick})

        third_tick = self._unit(position=(1, 1), sight_tiles=2)
        tracker.update_from_units({1: third_tick})

        self.assertEqual(tracker.get_known_cells()[(1, 0)], ".")

    def test_server_sight_value_overrides_type_default(self) -> None:
        tracker = self._tracker()
        tracker.update_from_units(
            {
                1: self._unit(
                    position=(0, 0),
                    sight_tiles=4,
                    seen_fires=[SeenFire(Position(4, 0), 100)],
                )
            }
        )

        parsed_unit = Unit().from_json(
            {
                "Id": 1,
                "Owner": "ObudaInnovationLab",
                "UnitType": "Firecopter",
                "Position": {"X": 2, "Y": 0},
                "SightTiles": 1,
                "SeenFires": [],
                "SeenWaters": [],
            }
        )

        tracker.update_from_units({1: parsed_unit})

        self.assertEqual(parsed_unit.sightTiles, 1)
        self.assertEqual(tracker.get_known_cells()[(4, 0)], "F")

    def test_visible_tiles_are_added_to_diamond_radius(self) -> None:
        tracker = self._tracker()
        tracker.update_from_units(
            {
                1: self._unit(
                    position=(10, 10),
                    sight_tiles=2,
                    visible_tiles=[(20, 20)],
                )
            }
        )

        known_cells = tracker.get_known_cells()
        self.assertEqual(known_cells[(10, 10)], ".")
        self.assertEqual(known_cells[(10, 8)], ".")
        self.assertEqual(known_cells[(8, 10)], ".")
        self.assertEqual(known_cells[(20, 20)], ".")
        self.assertNotIn((8, 8), known_cells)

    def test_written_map_is_anchored_at_top_left_origin(self) -> None:
        tracker = self._tracker()
        tracker.update_from_units(
            {
                1: self._unit(
                    position=(10, 10),
                    sight_tiles=1,
                )
            }
        )

        map_lines = tracker.map_path.read_text(encoding="utf-8").splitlines()
        self.assertIn("# Bounds: x=0..11, y=0..11", map_lines)
        self.assertTrue(any(line.startswith("   0 ") for line in map_lines))

    def test_failed_moves_detect_right_and_bottom_borders(self) -> None:
        tracker = self._tracker()
        unit = self._unit(
            position=(10, 10),
            sight_tiles=1,
        )

        tracker.update_from_units({1: unit})
        self.assertIn((11, 10), tracker.get_known_cells())
        self.assertIn((10, 11), tracker.get_known_cells())

        tracker.record_failed_move((10, 10), (11, 10))
        tracker.record_failed_move((10, 10), (10, 11))
        tracker.update_from_units({1: unit})

        known_cells = tracker.get_known_cells()
        self.assertNotIn((11, 10), known_cells)
        self.assertNotIn((10, 11), known_cells)
        self.assertFalse(tracker.is_within_detected_bounds((11, 10)))
        self.assertFalse(tracker.is_within_detected_bounds((10, 11)))

        map_lines = tracker.map_path.read_text(encoding="utf-8").splitlines()
        self.assertIn("# Bounds: x=0..10, y=0..10", map_lines)

    def test_alternate_fire_and_water_lists_are_parsed(self) -> None:
        parsed_unit = Unit().from_json(
            {
                "Id": 1,
                "Owner": "ObudaInnovationLab",
                "UnitType": "Firecopter",
                "Position": {"X": 10, "Y": 10},
                "SightTiles": 2,
                "SeenFires": [],
                "Fires": [
                    {"x": 4, "y": 5, "intensity": 10},
                    {"Position": {"X": 6, "Y": 7}, "HP": 20},
                ],
                "SeenWaters": [],
                "WaterSources": [
                    {"x": 1, "y": 2},
                    {"Position": {"X": 3, "Y": 4}},
                ],
            }
        )

        self.assertEqual(
            [(fire.position.x, fire.position.y, fire.hp) for fire in parsed_unit.seenFires],
            [(4, 5, 10), (6, 7, 20)],
        )
        self.assertEqual(
            [(water.x, water.y) for water in parsed_unit.seenWaters],
            [(1, 2), (3, 4)],
        )

    def test_extra_json_fire_and_water_lists_are_parsed(self) -> None:
        parsed_unit = Unit().from_json(
            {
                "Id": 1,
                "Owner": "ObudaInnovationLab",
                "UnitType": "Firecopter",
                "Position": {"X": 10, "Y": 10},
                "SightTiles": 2,
                "ExtraJson": (
                    '{"FireTiles": [{"X": 8, "Y": 9, "HP": 30}], '
                    '"water_sources": [{"x": 11, "y": 12}]}'
                ),
                "SeenFires": [],
                "SeenWaters": [],
            }
        )

        self.assertEqual(
            [(fire.position.x, fire.position.y, fire.hp) for fire in parsed_unit.seenFires],
            [(8, 9, 30)],
        )
        self.assertEqual(
            [(water.x, water.y) for water in parsed_unit.seenWaters],
            [(11, 12)],
        )

    def test_generic_position_list_can_be_used_as_visible_tiles(self) -> None:
        parsed_unit = Unit().from_json(
            {
                "Id": 1,
                "Owner": "ObudaInnovationLab",
                "UnitType": "Firecopter",
                "Position": {"X": 10, "Y": 10},
                "SightTiles": 16,
                "ScannedArea": [
                    {"Position": {"X": 10, "Y": 10}},
                    {"Position": {"X": 11, "Y": 10}},
                ],
                "SeenFires": [],
                "SeenWaters": [],
            }
        )

        self.assertEqual(
            [(tile.x, tile.y) for tile in parsed_unit.visibleTiles],
            [(10, 10), (11, 10)],
        )

    def test_nested_extra_json_visible_tiles_are_parsed(self) -> None:
        parsed_unit = Unit().from_json(
            {
                "Id": 1,
                "Owner": "ObudaInnovationLab",
                "UnitType": "Firecopter",
                "Position": {"X": 10, "Y": 10},
                "SightTiles": 16,
                "ExtraJson": (
                    '{"VisibleTiles": ['
                    '{"Position": {"X": 10, "Y": 10}}, '
                    '{"Position": {"X": 10, "Y": 11}}, '
                    '{"Position": {"X": 11, "Y": 10}}'
                    "]} "
                ),
                "SeenFires": [],
                "SeenWaters": [],
            }
        )

        self.assertEqual(
            [(tile.x, tile.y) for tile in parsed_unit.visibleTiles],
            [(10, 10), (10, 11), (11, 10)],
        )


if __name__ == "__main__":
    unittest.main()
