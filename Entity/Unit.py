from Entity import *

class Unit:
    def __init__(
        self,
        id: int,
        owner: str,
        unittype: UnitType,
        position: Position,
        currentWaterLevel: int,
        currentHP: int
    ):
        self.id = id
        self.owner = owner
        self.type = type
        self.position = position
        self.currentWaterLevel = CurrentWaterLevel
        self.currentHP = currentHP