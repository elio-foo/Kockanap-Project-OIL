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
    ) -> Unit:
        return Unit(
            unit_id=unit_id,
            owner="ObudaInnovationLab",
            unit_type=UnitType.Firecopter,
            position=Position(*position),
            sight_tiles=sight_tiles,
            seen_fires=seen_fires or [],
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

    def test_fire_memory_clears_after_visible_recheck(self) -> None:
        tracker = self._tracker()
        first_tick = self._unit(
            position=(0, 0),
            sight_tiles=2,
            seen_fires=[SeenFire(Position(1, 0), 100)],
        )
        tracker.update_from_units({1: first_tick})

        second_tick = self._unit(position=(1, 1), sight_tiles=2)
        tracker.update_from_units({1: second_tick})

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


if __name__ == "__main__":
    unittest.main()
