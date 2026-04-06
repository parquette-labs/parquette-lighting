from parquette.lights.dmx import DMXManager, DMXValue


class RadianceHazer(object):
    def __init__(self, dmx: DMXManager, addr: int):
        self.dmx = dmx
        self.addr = addr
        self.num_chans = 2
        self._output: DMXValue = 0
        self._fan: DMXValue = 0

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
