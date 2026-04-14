import math
import time
from enum import Enum, auto

from .generator import Generator
from ..category import Category
from ..util.math import value_map


class WaveGenerator(Generator):
    # period is a property so we can re-anchor self.phase whenever the period
    # changes, keeping the current cycle position continuous instead of jumping.
    @property
    def period(self) -> float:
        return self._period

    @period.setter
    def period(self, new_period: float) -> None:
        old_period = getattr(self, "_period", None)
        if old_period and old_period > 0 and new_period and new_period > 0:
            millis = time.time() * 1000
            new_offset = Generator.reanchor_offset(
                millis, old_period, new_period, -self.phase
            )
            self.phase = -new_offset
        self._period = new_period

    class Shape(Enum):
        TRIANGLE = auto()
        SQUARE = auto()
        SIN = auto()

    def __init__(
        self,
        *,
        name: str,
        category: Category,
        amp: float = 0.5,
        period: float = 1000,
        phase: float = 0,
        offset: float = 0.5,
        shape: Shape = Shape.SIN,
        duty: float = 0.5,
    ):
        super().__init__(
            name=name,
            category=category,
            amp=amp,
            offset=offset,
            period=period,
            phase=phase,
        )

        if not isinstance(shape, self.Shape):
            raise TypeError("Shape Enum not provided")
        self.shape = shape
        self.duty = duty

    def value(self, millis: float) -> float:
        if self.shape == WaveGenerator.Shape.TRIANGLE:
            modtime = (millis + self.phase + self.period / 4) % self.period
            if modtime < (self.period / 2):
                return value_map(
                    modtime,
                    0.0,
                    self.period / 2.0,
                    self.offset - self.amp,
                    self.offset + self.amp,
                )
            else:
                return value_map(
                    modtime - self.period / 2,
                    0.0,
                    self.period / 2,
                    self.offset + self.amp,
                    self.offset - self.amp,
                )
        elif self.shape == WaveGenerator.Shape.SQUARE:
            modtime = (millis + self.phase) % self.period
            if ((self.duty is not None) and (modtime < self.period * self.duty)) or (
                (self.duty is None) and (modtime < (self.period / 2))
            ):
                return self.offset + self.amp
            else:
                return self.offset - self.amp
        elif self.shape == WaveGenerator.Shape.SIN:
            return (
                self.amp * math.sin((millis + self.phase) / self.period * 2 * math.pi)
                + self.offset
            )

        return 0
