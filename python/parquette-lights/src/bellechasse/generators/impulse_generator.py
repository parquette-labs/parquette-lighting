from typing import Optional
import time
import math
from .generator import Generator


class ImpulseGenerator(Generator):
    punch_point: float = 0

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        amp: float = 1,
        offset: float = 0,
        period: float = 350,
        echo: int = 1,
        echo_decay: float = 1,
        duty: float = 100
    ):
        super().__init__(name=name, amp=amp, offset=offset, period=period, phase=0)

        self._echo = echo
        self._echo_decay = echo_decay
        self.duty = duty

    @property
    def echo(self) -> int:
        return self._echo

    @echo.setter
    def echo(self, value: int) -> None:
        self._echo = max(value, 1)

    @property
    def echo_decay(self) -> float:
        return self._echo_decay

    @echo_decay.setter
    def echo_decay(self, value: float) -> None:
        self._echo_decay = max(value, 0)

    def punch(self, millis: Optional[float] = None) -> None:
        if millis is None:
            millis = time.time() * 1000
        self.punch_point = millis

    def value(self, millis: float) -> float:
        ellapsed: float = millis - self.punch_point
        count: int = math.floor(ellapsed / self.period)

        if count >= self.echo:
            return self.offset

        if ellapsed % self.period >= 0 and ellapsed % self.period < self.duty:
            return self.amp * self.echo_decay**count + self.offset
        else:
            return self.offset
