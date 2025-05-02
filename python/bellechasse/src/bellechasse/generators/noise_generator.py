from typing import Optional
import random
from .generator import Generator


class NoiseGenerator(Generator):
    last_value: float = 0
    last_millis: float = 0

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        amp: float = 1,
        offset: float = 0,
        period: float = 500,
    ):
        super().__init__(name=name, amp=amp, offset=offset, period=period, phase=0)

    def value(self, millis: float) -> float:
        if (millis - self.last_millis) % (self.period * 2) > self.period:
            self.last_value = random.random() * self.amp + self.offset
            self.last_millis = 0

        return self.last_value
