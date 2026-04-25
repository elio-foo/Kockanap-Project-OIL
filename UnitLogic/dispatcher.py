from collections.abc import Iterable

from Entity import Unit

from .context import UnitLogicContext
from .handlers import BaseUnitLogic, DEFAULT_UNIT_LOGIC_BY_TYPE


class UnitLogicDispatcher:
    def __init__(self, handlers_by_type: dict | None = None):
        self._handlers_by_type = handlers_by_type or DEFAULT_UNIT_LOGIC_BY_TYPE

    async def run_for_unit(self, unit: Unit, context: UnitLogicContext) -> bool:
        if unit.type is None:
            return False

        handler: BaseUnitLogic | None = self._handlers_by_type.get(unit.type)
        if handler is None:
            return False

        await handler.run(unit, context)
        return True

    async def run_for_units(self, units: Iterable[Unit], context: UnitLogicContext) -> int:
        handled_units = 0

        for unit in units:
            if await self.run_for_unit(unit, context):
                handled_units += 1

        return handled_units
