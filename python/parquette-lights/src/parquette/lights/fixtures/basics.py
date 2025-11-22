from typing import List, Callable
from ..dmx import DMXManager, DMXListOrValue, DMXValue

ControlTarget = Callable[[DMXValue], None]


class Fixture(object):
    def __init__(self, dmx: DMXManager, addr: int, num_chans: int = 1):
        self.dmx = dmx
        self.addr = addr
        self.num_chans = num_chans

    def off(self) -> None:
        self.set(0)

    def mix_targets(self) -> List[ControlTarget]:
        return []

    def set(self, val: DMXListOrValue, chan_offset=None) -> None:
        if isinstance(val, list):
            if chan_offset is None:
                chan_offset = 0
            if (len(val) + chan_offset) > self.num_chans:
                raise IndexError(
                    "You're setting more channels than the width of your fixture, fixture addr {} has {} channels but you sent values with chan_offset={} of length {} with the following values {}".format(
                        self.addr, self.num_chans, chan_offset, len(val), val
                    )
                )
            self.dmx.set_channel(self.addr, val)
        else:
            if chan_offset is None:
                self.dmx.set_channel(self.addr, [val for _ in range(self.num_chans)])
            else:
                if chan_offset >= self.num_chans:
                    raise IndexError(
                        "You are setting a value at chan_offset={} but there are only {} channels for your fixture".format(
                            chan_offset, self.num_chans
                        )
                    )
                self.dmx.set_channel(self.addr + chan_offset, val)


class LightFixture(Fixture):
    def __init__(self, dmx: DMXManager, addr: int, num_chans: int = 1):
        super().__init__(dmx=dmx, addr=addr, num_chans=num_chans)
        self._dimming: DMXValue = 0

    def dimming(self, val: DMXValue) -> None:
        self._dimming = val
        self.set(val)

    def on(self) -> None:
        self.dimming(255)

    def off(self) -> None:
        self.dimming(0)

    def mix_targets(self) -> List[ControlTarget]:
        return [self.dimming]


class RGBLight(LightFixture):
    def __init__(self, dmx: DMXManager, addr: int):
        super().__init__(dmx, addr=addr, num_chans=3)

    def rgb(self, r: DMXValue, g: DMXValue, b: DMXValue) -> None:
        self.set([r, g, b])


class RGBWLight(LightFixture):
    def __init__(self, dmx: DMXManager, addr: int):
        super().__init__(dmx, addr=addr, num_chans=4)

    def rgbw(self, r: DMXValue, g: DMXValue, b: DMXValue, w: DMXValue) -> None:
        self.set([r, g, b, w])
