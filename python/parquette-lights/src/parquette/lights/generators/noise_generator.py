import random
from .generator import Generator


class NoiseGenerator(Generator):
    last_value: float = 0
    last_millis: float = 0

    def __init__(
        self,
        *,
        name: str,
        amp: float = 1,
        offset: float = 0,
        period: float = 500,
    ):
        super().__init__(name=name, amp=amp, offset=offset, period=period, phase=0)

        self.random_base = random.random()

    def value(self, millis: float) -> float:
        period_range = millis // self.period
        random.seed(period_range + self.random_base)
        return random.random() * self.amp + self.offset
