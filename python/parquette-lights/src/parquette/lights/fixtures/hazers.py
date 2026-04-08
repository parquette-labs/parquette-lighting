import time

from parquette.lights.dmx import DMXManager, DMXValue


class RadianceHazer(object):
    def __init__(self, dmx: DMXManager, addr: int, *, debug: bool = False):
        self.dmx = dmx
        self.addr = addr

        self.debug = debug

        self._output: DMXValue = 0
        self._fan: DMXValue = 0

        self.target_output: DMXValue = 0
        self.target_fan: DMXValue = 0

        self.interval: float = 0.0
        self.duration: float = 0.0

    def tick(self) -> None:
        now = time.monotonic()

        if self.duration <= 0:
            on = False
        elif self.interval <= 0 or self.duration >= self.interval:
            on = True
        else:
            on = (now % self.interval) < self.duration

        if on:
            self.output = self.target_output
            self.fan = self.target_fan
        else:
            self.output = 0
            self.fan = 0

        if self.debug:
            print(
                "Hazer [intensity, fan] {}".format(
                    self.dmx.chans[self.addr - 1 : self.addr + 1],
                )
            )

    @property
    def output(self) -> DMXValue:
        return self._output

    @output.setter
    def output(self, val: DMXValue) -> None:
        self._output = val
        self.dmx.set_channel(self.addr, val)

    @property
    def fan(self) -> DMXValue:
        return self._fan

    @fan.setter
    def fan(self, val: DMXValue) -> None:
        self._fan = val
        self.dmx.set_channel(self.addr + 1, val)
