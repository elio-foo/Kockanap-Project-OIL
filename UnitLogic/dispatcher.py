from __future__ import annotations

from Entity import Unit, UnitType
from Message import OperationId

from .context import UnitLogicContext
from .handlers import Firecopter, UnitDecision


class UnitLogicDispatcher:
    def __init__(self):
        self._handlers = {
            UnitType.Firecopter: Firecopter(),
        }

    def decide(self, unit: Unit, context: UnitLogicContext) -> UnitDecision:
        handler = self._handlers.get(unit.type)
        if handler is None:
            return UnitDecision(OperationId.NOP)
        return handler.decide(unit, context)
