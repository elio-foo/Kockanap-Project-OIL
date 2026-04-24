from dataclasses import dataclass
from typing import Awaitable, Callable

from Entity import Unit
from Message import OperationId


UnitCommandSender = Callable[[int, OperationId, object | None], Awaitable[None]]
UnitMoveSender = Callable[[int, str], Awaitable[None]]


@dataclass(slots=True)
class UnitLogicContext:
    units_by_id: dict[int, Unit]
    queue_command: UnitCommandSender
    queue_move: UnitMoveSender
