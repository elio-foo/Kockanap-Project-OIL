from __future__ import annotations

from dataclasses import dataclass

from Entity import Position, Unit
from Message import OperationId

from .context import FireTarget, UnitLogicContext


@dataclass(slots=True)
class UnitDecision:
    operation: OperationId
    extra_json: dict | None = None


class BaseHandler:
    extinguish_range = 2
    low_water_threshold = 2

    @staticmethod
    def distance(a: Position, b: Position) -> int:
        return abs(a.x - b.x) + abs(a.y - b.y)

    def _move_towards(self, start: Position, target: Position) -> UnitDecision:
        dx = target.x - start.x
        dy = target.y - start.y

        if abs(dx) >= abs(dy) and dx != 0:
            return UnitDecision(OperationId.RIGHT if dx > 0 else OperationId.LEFT)

        if dy != 0:
            return UnitDecision(OperationId.DOWN if dy > 0 else OperationId.UP)

        return UnitDecision(OperationId.NOP)


class Firecopter(BaseHandler):
    """
    Drone-style unit logic:
    - refill when water is low
    - prefer isolated fires so other units can cover closer clusters
    - extinguish once close enough, otherwise move one step toward the target
    """

    def choose_target(self, unit: Unit, context: UnitLogicContext) -> FireTarget | None:
        if not context.fires:
            return None

        teammates = [other for other in context.units if other.id != unit.id and other.position is not None]

        if not teammates:
            return min(
                context.fires,
                key=lambda fire: self.distance(unit.position, fire.position),
            )

        def isolation_score(fire: FireTarget) -> int:
            return min(self.distance(fire.position, teammate.position) for teammate in teammates)

        return max(context.fires, key=isolation_score)

    def decide(self, unit: Unit, context: UnitLogicContext) -> UnitDecision:
        if unit.position is None:
            return UnitDecision(OperationId.NOP)

        if unit.currentWaterLevel <= self.low_water_threshold:
            nearest_water = context.nearest_water_source(unit.position)
            if nearest_water is None:
                return UnitDecision(OperationId.NOP)

            if self.distance(unit.position, nearest_water) <= 1:
                return UnitDecision(OperationId.REFILL)

            return self._move_towards(unit.position, nearest_water)

        target = self.choose_target(unit, context)
        if target is None:
            return UnitDecision(OperationId.NOP)

        if self.distance(unit.position, target.position) <= self.extinguish_range:
            return UnitDecision(OperationId.EXTINGUISH, {"target": target.to_payload()})

        return self._move_towards(unit.position, target.position)
