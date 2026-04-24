from Entity import Unit, UnitType

from .context import UnitLogicContext


def todos(message: str) -> None:
    """Document a future unit-logic implementation point without breaking runtime."""
    _ = message


class BaseUnitLogic:
    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        raise NotImplementedError


class FirefighterLogic(BaseUnitLogic):
    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        todos("Implement firefighter behavior here.")
        _ = (unit, context)


class FiretruckLogic(BaseUnitLogic):
    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        todos("Implement firetruck behavior here.")
        _ = (unit, context)


class FirecopterLogic(BaseUnitLogic):
    async def run(self, unit: Unit, context: UnitLogicContext) -> None:
        todos("Implement firecopter behavior here.")
        _ = (unit, context)


DEFAULT_UNIT_LOGIC_BY_TYPE: dict[UnitType, BaseUnitLogic] = {
    UnitType.Firefighter: FirefighterLogic(),
    UnitType.Firetruck: FiretruckLogic(),
    UnitType.Firecopter: FirecopterLogic(),
}
