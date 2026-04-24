from .Position import Position
from .UnitType import UnitType

class Unit:

    def __init__(
        self,
        # id: int,
        # owner: str,
        # unittype: UnitType,
        # position: Position,
        # currentWaterLevel: int,
        # currentHP: int
        unit_id=None,
        owner="",
        unit_type=None,
        position=None,
        current_water_level=0,
        current_hp=0,
    ):
        self.id: int | None = unit_id
        self.owner: str = owner
        self.type: UnitType | None = unit_type
        self.position: Position | None = position
        self.currentWaterLevel: int = current_water_level
        self.currentHP: int = current_hp
        # self.id = id
        # self.owner = owner
        # self.type = type
        # self.position = position
        # self.currentWaterLevel = CurrentWaterLevel
        # self.currentHP = currentHP

    def from_json(self, json_data):
        position_data = json_data.get("Position") or {}

        self.id = json_data.get("Id")
        self.owner = json_data.get("Owner", "")
        self.type = UnitType.from_value(json_data.get("UnitType"))
        self.position = Position(position_data.get("X", 0), position_data.get("Y", 0))
        self.currentWaterLevel = json_data.get("CurrentWaterLevel", 0)
        self.currentHP = json_data.get("CurrentHP", 0)

        return self

    def __str__(self):
        return (
            f"Unit(id={self.id}, owner={self.owner}, type={self.type}, "
            f"position={self.position}, hp={self.currentHP}, water={self.currentWaterLevel})"
        )
