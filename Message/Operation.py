from enum import Enum

class OperationId(Enum):
    NOP = "NOP"
    ACK = "ACK"
    UP  = "Up"
    LEFT  = "Left"
    RIGHT = "Right"
    DOWN  = "Down"
    EXTINGUISH = "ExtinguishFire"
    REFILL = "RefillWithWater"
    SERVER_INFO = "InformationFromServer"
    SERVER_UNITS = "UnitsFromServer"

    @classmethod
    def from_direction(cls, direction: str):
        normalized_direction = direction.strip().lower()
        aliases = {
            "up": cls.UP,
            "w": cls.UP,
            "left": cls.LEFT,
            "a": cls.LEFT,
            "right": cls.RIGHT,
            "d": cls.RIGHT,
            "down": cls.DOWN,
            "s": cls.DOWN,
        }

        if normalized_direction not in aliases:
            raise ValueError(f"Unknown move direction: {direction}")

        return aliases[normalized_direction]
