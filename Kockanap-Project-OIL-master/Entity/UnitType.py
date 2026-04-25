from enum import Enum

class UnitType(Enum):
    Firefighter = "fireFighter"
    Firetruck = "Firetruck"
    Firecopter = "Firecopter"

    @classmethod
    def from_value(cls, raw_value):
        if isinstance(raw_value, cls):
            return raw_value

        if raw_value is None:
            raise ValueError("Unit type is missing")

        normalized_value = raw_value.replace("_", "").replace("-", "").lower()
        aliases = {
            "firefighter": cls.Firefighter,
            "firetruck": cls.Firetruck,
            "firecopter": cls.Firecopter,
        }

        if normalized_value not in aliases:
            raise ValueError(f"Unknown unit type: {raw_value}")

        return aliases[normalized_value]
