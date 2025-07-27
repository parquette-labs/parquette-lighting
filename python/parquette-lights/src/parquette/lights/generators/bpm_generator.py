from typing import Optional
import time
import math
from .generator import Generator


class BPMGenerator(Generator):
    duty: int
    bpm: float
    offset_time: float
    manual_offset: float
    bpm_mult: float

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        amp: float = 1,
        offset: float = 0,
        duty: int = 100,
        bpm: float = 126,
        offset_time: int = 0,
    ):
        super().__init__(name=name, amp=amp, offset=offset, period=0, phase=0)

        self.bpm = bpm
        self.offset_time = offset_time
        self.duty = duty
        self.bpm_mult = 1
        self.manual_offset = 0

    def set_offset_time(self, new_offset):
        try:
            period = 1000 * 60 / (self.bpm)
            mod_old_offset = self.offset_time % period
            mod_new_offset = self.offset_time % new_offset
            self.offset_time = 1 / 3 * mod_new_offset + 2 / 3 * mod_old_offset
        except ZeroDivisionError:
            return

    def value(self, millis: float) -> float:
        try:
            ellapsed: float = millis - self.offset_time - self.manual_offset
            period = 1000 * 60 / (self.bpm * self.bpm_mult)

            if ellapsed % period >= 0 and ellapsed % period < self.duty:
                return self.amp + self.offset
            else:
                return self.offset
        except ZeroDivisionError:
            return 0
