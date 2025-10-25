from typing import Union


from ..dmx import DMXManager


class RGBLight(object):
    def __init__(self, dmx: DMXManager, addr: int):
        self.dmx = dmx
        self.addr = addr

    def dimming(self, value: Union[int | float] = 255) -> None:
        self.rgb(value, value, value)

    def off(self) -> None:
        self.rgb(0, 0, 0)

    def rgb(
        self, r: Union[int | float], g: Union[int | float], b: Union[int | float]
    ) -> None:
        self.dmx.set_channel(self.addr, r)
        self.dmx.set_channel(1 + self.addr, g)
        self.dmx.set_channel(2 + self.addr, b)


class SingleLight(object):
    def __init__(self, dmx: DMXManager, addr: int):
        self.dmx = dmx
        self.addr = addr

    def dimming(self, value: Union[int | float] = 255) -> None:
        self.dmx.set_channel(self.addr, value)

    def off(self) -> None:
        self.dimming(0)
