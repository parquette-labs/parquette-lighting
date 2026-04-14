import time
from typing import Optional

from ..category import Category
from ..dmx import DMXManager, DMXValue
from ..osc import OSCManager
from .basics import Fixture


class RadianceHazer(Fixture):
    def __init__(
        self,
        *,
        name: str,
        category: Category,
        dmx: DMXManager,
        addr: int,
        osc: Optional[OSCManager] = None,
        debug: bool = False,
    ):
        super().__init__(
            name=name, category=category, dmx=dmx, addr=addr, num_chans=2, osc=osc
        )
        self.runnable = True
        self.debug = debug

        self.target_output: DMXValue = 0
        self.target_fan: DMXValue = 0

        self.interval: float = 0.0
        self.duration: float = 0.0

    def run(self) -> None:
        now = time.monotonic()

        if self.duration <= 0:
            on = False
        elif self.interval <= 0 or self.duration >= self.interval:
            on = True
        else:
            on = (now % self.interval) < self.duration

        if on:
            self.set([self.target_output, self.target_fan])
        else:
            self.set([0, 0])

        if self.debug:
            print(
                "Hazer [intensity, fan] {}".format(
                    self.dmx.chans[self.addr - 1 : self.addr + 1],
                )
            )
