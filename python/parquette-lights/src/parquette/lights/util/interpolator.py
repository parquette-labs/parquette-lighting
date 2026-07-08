class Interpolator:
    """Linear interpolator for smooth value transitions.

    Wraps a numeric value with a target and step-per-tick. Call tick()
    each frame to advance the current value toward the target. When
    remaining_ticks reaches zero, current snaps exactly to target.
    """

    def __init__(self, value: float = 0.0) -> None:
        self.current = value
        self.target = value
        self.remaining_ticks = 0
        self.step = 0.0

    def set_target(self, target: float, ticks: int = 0) -> None:
        """Begin interpolating toward target over the given number of ticks."""
        self.target = target
        if ticks <= 0:
            self.current = target
            self.remaining_ticks = 0
            self.step = 0.0
        else:
            self.step = (target - self.current) / ticks
            self.remaining_ticks = ticks

    def tick(self) -> float:
        """Advance one tick and return the current value."""
        if self.active:
            self.remaining_ticks -= 1
            if self.remaining_ticks == 0:
                self.current = self.target
            else:
                self.current += self.step
        return self.current

    @property
    def active(self) -> bool:
        """True while an interpolation is in progress."""
        return self.remaining_ticks > 0
