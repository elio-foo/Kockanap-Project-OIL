"""
ADVANCED FIREFIGHTING UNIT AI MODULE
====================================
Enhancements added:
- Dynamic path recalculation
- Multi-unit coordination (target reservation)
- Predictive fire targeting (future risk)
- Water-aware strategy (truck refill planning)
- Drone pre-scan (OpenRA-style map scan hook)
- Support for additional units (0–4 arbitrary units)

NOTE:
This remains ENGINE-AGNOSTIC. Hooks are provided where engine data can plug in.
"""

import heapq
import random
from typing import List, Tuple, Dict, Optional

# ============================================================
# A* PATHFINDING
# ============================================================


def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(start, goal, grid_size=(100, 100), weighted_nodes=None):
    if weighted_nodes is None:
        weighted_nodes = {}

    open_set = []
    heapq.heappush(open_set, (0, start))

    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1]

        neighbors = [
            (current[0] + 1, current[1]),
            (current[0] - 1, current[1]),
            (current[0], current[1] + 1),
            (current[0], current[1] - 1),
        ]

        for n in neighbors:
            if not (0 <= n[0] < grid_size[0] and 0 <= n[1] < grid_size[1]):
                continue

            weight = weighted_nodes.get(n, 1)
            tentative_g = g_score[current] + weight

            if n not in g_score or tentative_g < g_score[n]:
                came_from[n] = current
                g_score[n] = tentative_g
                f_score = tentative_g + heuristic(n, goal)
                heapq.heappush(open_set, (f_score, n))

    return []


# ============================================================
# FIRE MODEL
# ============================================================


class Fire:
    def __init__(self, position: Tuple[int, int], intensity: int):
        self.position = position
        self.intensity = intensity


# ============================================================
# BASE UNIT
# ============================================================


class Unit:
    def __init__(self, name, dmg, sight, water, speed, position=(0, 0)):
        self.name = name
        self.damage = dmg
        self.sight = sight
        self.max_water = water
        self.water = water
        self.speed = speed
        self.position = position

        self.path: List[Tuple[int, int]] = []
        self.target: Optional[Fire] = None

    def distance(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    # -----------------------------
    # CLUSTER + PREDICTION
    # -----------------------------

    def compute_weighted_nodes(self, fires: List[Fire]):
        weights = {}

        for f in fires:
            cluster_strength = 0

            for other in fires:
                d = self.distance(f.position, other.position)
                if d <= 3:
                    cluster_strength += other.intensity / (d + 1)

            # Predictive growth factor (simple heuristic)
            predicted = f.intensity * 0.1

            weights[f.position] = max(0.1, 1 - (cluster_strength + predicted) * 0.001)

        return weights

    # -----------------------------
    # MOVEMENT
    # -----------------------------

    def move(self):
        for _ in range(max(1, self.speed // 50)):  # speed scaling
            if self.path:
                self.position = self.path.pop(0)

    # -----------------------------
    # FIRE INTERACTION
    # -----------------------------

    def fight_fire(self, fire: Fire):
        if self.water == 0:
            return

        fire.intensity -= self.damage

        if self.max_water != float("inf"):
            self.water -= 1

    def needs_refill(self):
        return self.water != float("inf") and self.water <= 2

    def choose_target(self, fires, friendly_units, reserved_targets):
        raise NotImplementedError


# ============================================================
# UNITS
# ============================================================


class FireFighter(Unit):
    def __init__(self, pos=(0, 0)):
        super().__init__("FireFighter", 50, 2, float("inf"), 50, pos)

    def choose_target(self, fires, friendly_units, reserved_targets):
        choices = [f for f in fires if f not in reserved_targets]
        return min(choices or fires, key=lambda f: self.distance(self.position, f.position))


class Truck(Unit):
    def __init__(self, pos=(0, 0)):
        super().__init__("Truck", 200, 8, 20, 100, pos)

    def choose_target(self, fires, friendly_units, reserved_targets):
        # Prefer large fires but avoid overcrowding
        choices = sorted(fires, key=lambda f: f.intensity, reverse=True)
        for f in choices:
            if f not in reserved_targets:
                return f
        return choices[0]


class Drone(Unit):
    def __init__(self, pos=(0, 0)):
        super().__init__("Drone", 100, 16, 5, 200, pos)

    def scan_map(self, engine_callback=None):
        """
        Optional full-map scan (OpenRA-style).
        engine_callback: function that returns updated fire list
        """
        if engine_callback:
            return engine_callback()
        return None

    def choose_target(self, fires, friendly_units, reserved_targets):
        def isolation_score(fire):
            closest = min(
                self.distance(fire.position, u.position)
                for u in friendly_units
                if u != self
            )
            return closest

        choices = [f for f in fires if f not in reserved_targets]
        return max(choices or fires, key=isolation_score)


# ============================================================
# EXTRA RANDOM UNITS (0–4)
# ============================================================


class SupportUnit(Unit):
    """
    Randomized unit type for variability.
    """

    def __init__(self, pos=(0, 0)):
        dmg = random.randint(40, 120)
        sight = random.randint(3, 10)
        water = random.randint(5, 30)
        speed = random.randint(40, 150)
        super().__init__("Support", dmg, sight, water, speed, pos)

    def choose_target(self, fires, friendly_units, reserved_targets):
        return random.choice(fires)


def spawn_additional_units(n: int):
    """
    Spawn up to 4 additional units.
    """
    n = min(n, 4)
    return [SupportUnit((random.randint(0, 50), random.randint(0, 50))) for _ in range(n)]


# ============================================================
# COORDINATED DECISION STEP
# ============================================================


def unit_step(unit: Unit, fires: List[Fire], friendly_units: List[Unit], reserved_targets: set, engine_scan=None):
    active_fires = [f for f in fires if f.intensity > 0]
    if not active_fires:
        return

    # Drone optional scan before acting
    if isinstance(unit, Drone):
        scanned = unit.scan_map(engine_scan)
        if scanned:
            active_fires = scanned

    # Refill behavior (placeholder logic)
    if unit.needs_refill():
        return  # engine should redirect to water source

    # Target selection with coordination
    target = unit.choose_target(active_fires, friendly_units, reserved_targets)
    unit.target = target
    reserved_targets.add(target)

    # Path recalculation trigger
    if not unit.path or unit.distance(unit.position, target.position) > len(unit.path):
        weights = unit.compute_weighted_nodes(active_fires)
        unit.path = astar(unit.position, target.position, weighted_nodes=weights)

    # Act
    if unit.distance(unit.position, target.position) > unit.sight:
        unit.move()
    else:
        unit.fight_fire(target)
