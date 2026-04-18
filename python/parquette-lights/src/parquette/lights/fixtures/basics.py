from __future__ import annotations

from typing import Callable, ClassVar, List, Optional
from ..category import Category
from ..dmx import DMXManager, DMXListOrValue, DMXValue
from ..osc import OSCManager, OSCParam
from ..util.math import constrain, value_map


class MixTarget:
    """Wraps a fixture control method with optional additive accumulation.

    The fixture is always updated on every call. When accumulate=True, the
    value is added to a running total and the total is sent. When
    accumulate=False (default), the accumulator is cleared first and just
    the given value is sent.

    Each target carries its own category so the mixer knows which preset
    group the resulting MixChannel belongs to.
    """

    def __init__(
        self,
        target: Callable[[int], None],
        name: str,
        category: Category,
        max_value: int = 255,
    ) -> None:
        self.target = target
        self.name = name
        self.category: Category = category
        self.max_value: int = max_value
        self.accumulator: float = 0.0

    def __call__(self, value: float, accumulate: bool = False) -> None:
        if accumulate:
            self.accumulator += value
            self.target(int(constrain(self.accumulator, 0, self.max_value)))
        else:
            self.accumulator = 0.0
            self.target(int(constrain(value, 0, self.max_value)))


class Fixture(object):
    STANDARD_ATTRS: ClassVar[List[str]] = []

    def __init__(
        self,
        *,
        name: str,
        category: Category,
        dmx: DMXManager,
        addr: int,
        num_chans: int = 1,
        osc: Optional[OSCManager] = None,
    ):
        self.name = name
        self.dmx = dmx
        self.addr = addr
        self.num_chans = num_chans
        self.category = category
        self.osc = osc
        self.runnable: bool = False
        self.wrapped_targets: List[MixTarget] = []

    def run(self) -> None:
        pass

    def send_visualizer(self) -> None:
        pass

    def standard_params(self, osc: OSCManager) -> List[OSCParam]:
        """Return OSCParam binds for this fixture's standard attributes.

        Addresses follow /fixture/{ClassName}/{name}/{attribute}.
        """
        cls_name = type(self).__name__
        return [
            OSCParam.bind(
                osc,
                "/fixture/{}/{}/{}".format(cls_name, self.name, attr),
                self,
                attr,
            )
            for attr in self.STANDARD_ATTRS
        ]

    def set_mix_targets(self, *targets: Callable[[int], None]) -> None:
        self.wrapped_targets = [
            MixTarget(t, t.__name__, self.category) for t in targets
        ]

    def off(self) -> None:
        self.set(0)

    def mix_targets(self) -> List[MixTarget]:
        return self.wrapped_targets

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
    def __init__(
        self,
        *,
        name: str,
        category: Category,
        dmx: DMXManager,
        addr: int,
        num_chans: int = 1,
        osc: Optional[OSCManager] = None,
    ):
        super().__init__(
            name=name,
            category=category,
            dmx=dmx,
            addr=addr,
            num_chans=num_chans,
            osc=osc,
        )
        self._dimming: DMXValue = 0
        self.set_mix_targets(self.dimming)

    def dimming(self, val: DMXValue) -> None:
        self._dimming = val
        self.set(val)

    def send_visualizer(self) -> None:
        if self.osc is not None:
            self.osc.send_osc(
                "/visualizer/fixture/{}/dimming".format(self.name), self._dimming
            )

    def on(self) -> None:
        self.dimming(255)

    def off(self) -> None:
        self.dimming(0)


class RGBLight(LightFixture):
    def __init__(
        self,
        *,
        name: str,
        category: Category,
        dmx: DMXManager,
        addr: int,
        osc: Optional[OSCManager] = None,
    ):
        super().__init__(
            name=name, category=category, dmx=dmx, addr=addr, num_chans=3, osc=osc
        )
        self.r_target: DMXValue = 255
        self.g_target: DMXValue = 255
        self.b_target: DMXValue = 255

    @property
    def color(self) -> List:
        return [self.r_target, self.g_target, self.b_target]

    @color.setter
    def color(self, value: List) -> None:
        if len(value) >= 3:
            self.set_dimming_target(r=value[0], g=value[1], b=value[2])

    def color_param(self, osc: OSCManager) -> OSCParam:
        """Preset-saved class-level color bind at /fixture/{ClassName}/color.

        Every instance registers at the same address; pythonosc fans one
        UI message to all handlers. Preset save/load round-trips the
        [r, g, b] value through the standard OSCParam machinery.
        """
        addr = "/fixture/{}/color".format(type(self).__name__)
        return OSCParam.bind(osc, addr, self, "color")

    def set_dimming_target(
        self,
        r: Optional[DMXValue] = None,
        g: Optional[DMXValue] = None,
        b: Optional[DMXValue] = None,
    ) -> None:
        if not r is None:
            self.r_target = r
        if not g is None:
            self.g_target = g
        if not b is None:
            self.b_target = b

    def dimming(self, val: DMXValue) -> None:
        self._dimming = val

        r = value_map(val, 0, 255, 0, self.r_target)
        g = value_map(val, 0, 255, 0, self.g_target)
        b = value_map(val, 0, 255, 0, self.b_target)

        self.rgb(r, g, b)

    def rgb(self, r: DMXValue, g: DMXValue, b: DMXValue) -> None:
        self.set([r, g, b])


class RGBWLight(LightFixture):
    def __init__(
        self,
        *,
        name: str,
        category: Category,
        dmx: DMXManager,
        addr: int,
        osc: Optional[OSCManager] = None,
        use_rgb_color_broadcast: bool = True,
    ):
        super().__init__(
            name=name, category=category, dmx=dmx, addr=addr, num_chans=4, osc=osc
        )
        self.r_target: DMXValue = 255
        self.g_target: DMXValue = 255
        self.b_target: DMXValue = 255
        self.w_target: DMXValue = 255
        self.use_rgb_color_broadcast = use_rgb_color_broadcast

    @property
    def color(self) -> List:
        return [self.r_target, self.g_target, self.b_target]

    @color.setter
    def color(self, value: List) -> None:
        if len(value) >= 3:
            self.set_dimming_target(r=value[0], g=value[1], b=value[2])

    def color_param(self, osc: OSCManager) -> OSCParam:
        """Preset-saved class-level color bind.

        When use_rgb_color_broadcast is True, binds to /fixture/RGBLight/color
        so one UI message reaches every RGB-family wash. Otherwise binds to
        /fixture/RGBWLight/color.
        """
        color_class = (
            "RGBLight" if self.use_rgb_color_broadcast else type(self).__name__
        )
        addr = "/fixture/{}/color".format(color_class)
        return OSCParam.bind(osc, addr, self, "color")

    def w_target_param(self, osc: OSCManager) -> OSCParam:
        """Preset-saved class-level w_target bind at /fixture/RGBWLight/w_target."""
        addr = "/fixture/{}/w_target".format(type(self).__name__)
        return OSCParam.bind(osc, addr, self, "w_target")

    def set_dimming_target(
        self,
        r: Optional[DMXValue] = None,
        g: Optional[DMXValue] = None,
        b: Optional[DMXValue] = None,
        w: Optional[DMXValue] = None,
    ) -> None:
        if not r is None:
            self.r_target = r
        if not g is None:
            self.g_target = g
        if not b is None:
            self.b_target = b
        if not w is None:
            self.w_target = w

    def dimming(self, val: DMXValue) -> None:
        self._dimming = val

        r = value_map(val, 0, 255, 0, self.r_target)
        g = value_map(val, 0, 255, 0, self.g_target)
        b = value_map(val, 0, 255, 0, self.b_target)
        w = value_map(val, 0, 255, 0, self.w_target)

        self.rgbw(r, g, b, w)

    def rgbw(self, r: DMXValue, g: DMXValue, b: DMXValue, w: DMXValue) -> None:
        self.set([r, g, b, w])
