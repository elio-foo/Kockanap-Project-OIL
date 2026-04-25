from .Position import Position


class SeenFire:
    def __init__(self, position: Position, hp: int):
        self.position: Position = position
        self.hp: int = hp

    def __str__(self):
        return f"SeenFire(position={self.position}, hp={self.hp})"
