from parquette.lights.dmx import DMXManager, DMXValue


class RadianceHazer(object):
    def __init__(self, dmx: DMXManager, addr: int):
        self.dmx = dmx
        self.addr = addr
        self.num_chans = 2
        self._output: DMXValue = 0
        self._fan: DMXValue = 0
        # PWM-style cycle config (intensity/fan are the on-phase targets,
        # interval is total period in seconds, duration is on-time per cycle).
        # interval == 0 (or duration >= interval) means continuous on.
        self.intensity: DMXValue = 0
        self.cycle_fan: DMXValue = 0
        self.interval: float = 0.0
        self.duration: float = 0.0

    def tick(self, now: float) -> None:
        if self.interval <= 0 or self.duration >= self.interval:
            on = True
        else:
            on = (now % self.interval) < self.duration
        if on:
            self.output = self.intensity
            self.fan = self.cycle_fan
        else:
            self.output = 0
            self.fan = 0

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
