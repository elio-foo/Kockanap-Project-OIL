import json

from Entity import *

def parse_to_unit(unit_data) -> Unit:
    unit = Unit()

    unit.id = unit_data.get("Id")
    unit.type = UnitType(unit_data.get("UnitType"))
    unit.owner = unit_data.get("Owner")
    unit.position = Position(unit_data["Position"]["X"], unit_data["Position"]["Y"])
    unit.currentHP = unit_data.get("CurrentHP")
    unit.currentWaterLevel = unit_data.get("CurrentWaterLevel")

    return unit
