from Entity import *
from Message import *

class Unit:

    def __init__(
        self,
        # id: int,
        # owner: str,
        # unittype: UnitType,
        # position: Position,
        # currentWaterLevel: int,
        # currentHP: int
    ):
        self.id: int
        self.owner: str
        self.type: UnitType
        self.position: Position
        self.currentWaterLevel: int
        self.currentHP: int
        # self.id = id
        # self.owner = owner
        # self.type = type
        # self.position = position
        # self.currentWaterLevel = CurrentWaterLevel
        # self.currentHP = currentHP

    def from_json(self, json_data):
        self.id = json_data["Id"]
        self.owner = json_data["Owner"]
        self.type = UnitType(json_data["UnitType"])
        self.position = Position(json_data["Position"]["X"], json_data["Position"]["Y"])
        self.currentWaterLevel = json_data["CurrentWaterLevel"]
        self.currentHP = json_data["CurrentHP"]