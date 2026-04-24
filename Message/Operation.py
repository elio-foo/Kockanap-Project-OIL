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