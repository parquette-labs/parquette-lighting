import math
from enum import Enum, auto

from .generator import Generator
from ..util.math import value_map


class WaveGenerator(Generator):
    class Shape(Enum):
        TRIANGLE = auto()
        SQUARE = auto()
        SIN = auto()

    def __init__(
        self,
        *,
        name: str,
        amp: float = 0.5,
        period: float = 1000,
        phase: float = 0,
        offset: float = 0.5,
        shape: Shape = Shape.SIN
    ):
        super().__init__(name=name, amp=amp, offset=offset, period=period, phase=phase)

        if not isinstance(shape, self.Shape):
            raise TypeError("Shape Enum not provided")
        self.shape = shape

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
            if modtime < (self.period / 2):
                return self.offset + self.amp
            else:
                return self.offset - self.amp
        elif self.shape == WaveGenerator.Shape.SIN:
            return (
                self.amp * math.sin((millis + self.phase) / self.period * 2 * math.pi)
                + self.offset
            )

        return 0
