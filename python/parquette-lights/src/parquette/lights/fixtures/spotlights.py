# pylint: disable=too-many-lines
from __future__ import annotations

import threading
import time
from typing import cast, List, Optional

from enum import Enum


from ..category import Category
from ..coord_system_state import CoordSystemState
from ..osc import OSCManager, OSCParam
from ..util.coord_system import CoordSystem
from ..util.coordinates import SpotCoordFrame
from ..util.math import constrain, value_map
from .basics import LightFixture, MixTarget
from ..dmx import DMXManager, DMXValue, DMXControlChannel, DMXControlRange


class Spot(LightFixture):
    pan_channel: DMXControlChannel
    tilt_channel: DMXControlChannel
    pan_fine_channel: DMXControlChannel
    tilt_fine_channel: DMXControlChannel
    movement_speed_channel: DMXControlChannel
    dimming_channel: DMXControlChannel
    strobe_channel: DMXControlChannel
    color_channel: DMXControlChannel
    pattern_channel: DMXControlChannel
    prisim_channel: DMXControlChannel

    def __init__(
        self,
        *,
        name: str,
        category: Category,
        position_category: Category,
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
        self.position_category = position_category

        if self.osc is not None:
            # Class-level broadcast address: every Spot instance registers
            # its own handler at the same address so one UI trigger fans
            # out to all instances via the OSC dispatcher.
            self.osc.dispatcher.map(
                "/fixture/{}/reset".format(type(self).__name__),
                lambda addr, args, s=self: s.reset(args),
            )

        self._pan: DMXValue = 0
        self._tilt: DMXValue = 0
        self._movement_speed: DMXValue = 0
        self._dimming: DMXValue = 0

        self.strobe_enabled: bool = False
        self._strobe_rate: DMXValue = 0

        # Backing fields for the color_index / pattern_index / prisim_enabled /
        # prisim_rotation properties defined below. The properties exist so
        # that OSCParam.bind can setattr them from the UI and have the full
        # color()/pattern()/prisim() method bodies run (writing DMX), while
        # internal code that only needs to update the cached value (inside the
        # methods themselves) writes to the backing fields directly.
        self.color_index_value: int = 0
        self.pattern_index_value: int = 0
        self.prisim_enabled_value: bool = False
        self.prisim_rotation_value: DMXValue = 0

        self.color_swap_fade_multiplier: float = 1.0
        self.color_swap_fade_time: float = -1.0
        self.color_swap_mechanical_time: float = 0.0
        self.color_swap_fade_cancel: threading.Event = threading.Event()

    @property
    def color_index(self) -> int:
        return self.color_index_value

    @color_index.setter
    def color_index(self, val: int) -> None:
        self.color(int(val))

    @property
    def pattern_index(self) -> int:
        return self.pattern_index_value

    @pattern_index.setter
    def pattern_index(self, val: int) -> None:
        self.pattern(int(val))

    @property
    def prisim_enabled(self) -> bool:
        return self.prisim_enabled_value

    @prisim_enabled.setter
    def prisim_enabled(self, val: bool) -> None:
        self.prisim(bool(val), cast(int, self.prisim_rotation_value))

    @property
    def prisim_rotation(self) -> DMXValue:
        return self.prisim_rotation_value

    @prisim_rotation.setter
    def prisim_rotation(self, val: DMXValue) -> None:
        self.prisim(self.prisim_enabled_value, int(val))

    def pantilt(self, pan: int, tilt: int, fine: bool = False) -> None:
        self.pan(pan, fine=fine)
        self.tilt(tilt, fine=fine)

    def get_pan(self) -> DMXValue:
        return self._pan

    def get_tilt(self) -> DMXValue:
        return self._tilt

    def pan(self, val: DMXValue, fine: bool = False) -> None:
        if fine:
            int_val = int(constrain(val, 0, 65535))
            self._pan = int_val
            self.dmx.set_channel(
                self.addr + self.pan_channel.offset, (int_val >> 8) & 0xFF
            )
            self.dmx.set_channel(
                self.addr + self.pan_fine_channel.offset, int_val & 0xFF
            )
        else:
            mapped = cast(DMXValue, self.pan_channel.map(val))
            self._pan = int(mapped) << 8
            self.dmx.set_channel(self.addr + self.pan_channel.offset, mapped)

    def tilt(self, val: DMXValue, fine: bool = False) -> None:
        if fine:
            int_val = int(constrain(val, 0, 65535))
            self._tilt = int_val
            self.dmx.set_channel(
                self.addr + self.tilt_channel.offset, (int_val >> 8) & 0xFF
            )
            self.dmx.set_channel(
                self.addr + self.tilt_fine_channel.offset, int_val & 0xFF
            )
        else:
            mapped = cast(DMXValue, self.tilt_channel.map(val))
            self._tilt = int(mapped) << 8
            self.dmx.set_channel(self.addr + self.tilt_channel.offset, mapped)

    def movement_speed(self, val: DMXValue) -> None:
        self._movement_speed = cast(DMXValue, self.movement_speed_channel.map(val))
        self.dmx.set_channel(
            self.addr + self.movement_speed_channel.offset, self._movement_speed
        )

    def dimming(self, val: DMXValue) -> None:
        # Store the un-faded mapped value so callers (e.g. the mixer that
        # writes us every 10ms) see their requested level. The fade multiplier
        # only scales what we actually push to DMX.
        self._dimming = cast(DMXValue, self.dimming_channel.map(val))
        self.dmx.set_channel(
            self.addr + self.dimming_channel.offset,
            int(self._dimming * self.color_swap_fade_multiplier),
        )

    def strobe(self, enable: bool, rate: Optional[int] = None) -> None:
        self.strobe_enabled = enable

        if self.strobe_enabled and not rate is None:
            self.strobe_rate(rate)
        else:
            self.dmx.set_channel(
                self.addr + self.strobe_channel.offset,
                self.strobe_channel.map(range_name="on"),
            )

    def strobe_rate(self, val: DMXValue) -> None:
        self._strobe_rate = cast(
            DMXValue, self.strobe_channel.map(val, range_name="strobe")
        )
        self.dmx.set_channel(self.addr + self.strobe_channel.offset, self._strobe_rate)

    def colors(self) -> List[str]:
        return self.color_channel.range_names()

    def color(self, index: int, override_swap_fade: bool = False) -> None:
        clamped = int(constrain(index, 0, len(self.colors()) - 1))

        if override_swap_fade or self.color_swap_fade_time < 0:
            self._color_direct(clamped)
            return

        self._start_color_swap_fade(clamped)

    def _color_direct(self, index: int) -> None:
        self.color_index_value = index
        self.dmx.set_channel(
            self.addr + self.color_channel.offset,
            self.color_channel.map(range_index=self.color_index_value),
        )

    def _start_color_swap_fade(self, color_index: int) -> None:
        # Cancel any in-flight fade. The old thread checks the event on its
        # next 10ms tick and bails out, leaving color_swap_fade_multiplier wherever it
        # happens to be — the new thread picks up from there.
        self.color_swap_fade_cancel.set()
        self.color_swap_fade_cancel = threading.Event()

        thread = threading.Thread(
            target=self._color_fade_sequence,
            args=(color_index, self.color_swap_fade_cancel),
            daemon=True,
        )
        thread.start()

    def _color_fade_sequence(
        self, color_index: int, cancel_event: threading.Event
    ) -> None:
        fade_time = self.color_swap_fade_time
        if fade_time <= 0:
            self._color_direct(color_index)
            self.color_swap_fade_multiplier = 1.0
            return

        # Wall-clock driven so we don't drift when individual time.sleep
        # calls oversleep (which they reliably do under GIL pressure on
        # macOS). Each phase records its own start instant and computes
        # progress as elapsed / duration; the total wall-clock time of
        # each phase is therefore accurate to within one `tick`.
        tick = 0.01

        # ---- fade out ----
        # Scale duration to current multiplier so that interrupting a
        # near-bright in-progress fade still feels snappy instead of
        # taking the full fade_time.
        start_mult = self.color_swap_fade_multiplier
        if start_mult > 0.0:
            fade_out_duration = fade_time * start_mult
            t0 = time.monotonic()
            while True:
                if cancel_event.is_set():
                    return
                elapsed = time.monotonic() - t0
                if elapsed >= fade_out_duration:
                    break
                self.color_swap_fade_multiplier = start_mult * (
                    1.0 - elapsed / fade_out_duration
                )
                time.sleep(tick)

        if cancel_event.is_set():
            return

        self.color_swap_fade_multiplier = 0.0

        # ---- swap color while dark ----
        self._color_direct(color_index)

        # ---- mechanical settle ----
        if self.color_swap_mechanical_time > 0:
            t0 = time.monotonic()
            while time.monotonic() - t0 < self.color_swap_mechanical_time:
                if cancel_event.is_set():
                    return
                time.sleep(tick)

        if cancel_event.is_set():
            return

        # ---- fade in ----
        t0 = time.monotonic()
        while True:
            if cancel_event.is_set():
                return
            elapsed = time.monotonic() - t0
            if elapsed >= fade_time:
                break
            self.color_swap_fade_multiplier = elapsed / fade_time
            time.sleep(tick)

        self.color_swap_fade_multiplier = 1.0

    def white(self, override_swap_fade: bool = False) -> None:
        self.color(0, override_swap_fade=override_swap_fade)

    def patterns(self) -> List[str]:
        return self.pattern_channel.range_names()

    def pattern(self, index: int) -> None:
        self.pattern_index_value = int(constrain(index, 0, len(self.patterns()) - 1))

        self.dmx.set_channel(
            self.addr + self.pattern_channel.offset,
            self.pattern_channel.map(range_index=self.pattern_index_value),
        )

    def no_pattern(self) -> None:
        self.pattern(0)

    def prisim(self, enable: bool, rotation: int = 0) -> None:
        self.prisim_enabled_value = enable
        self.prisim_rotation_value = self.prisim_channel.map(
            rotation, range_name="rotation"
        )

        if not enable:
            self.dmx.set_channel(
                self.addr + self.prisim_channel.offset,
                self.prisim_channel.map(range_name="off"),
            )
        elif rotation == 0:
            self.dmx.set_channel(
                self.addr + self.prisim_channel.offset,
                self.prisim_channel.map(range_name="on"),
            )
        else:
            self.dmx.set_channel(
                self.addr + self.prisim_channel.offset, self.prisim_rotation_value
            )

    def reset(self, reset: bool) -> None:
        pass


class YRXY200Spot(Spot):
    # https://yuerlighting.com/product/280w-rgbw-led-moving-head-light-200w-white-21x-smd-5050-rgb-540-pan-200-tilt-for-dj-shows-weddings-church-services-events/

    STANDARD_ATTRS = [
        "color_index",
        "pattern_index",
        "prisim_enabled",
        "prisim_rotation",
    ]

    class YRXY200Channel(Enum):
        X_AXIS = 0
        X_AXIS_FINE = 1
        Y_AXIS = 2
        Y_AXIS_FINE = 3
        XY_SPEED = 4
        DIMMING = 5
        STROBE = 6
        COLOR = 7
        PATTERN = 8
        PRISIM = 9
        COLORFUL = 10
        SELF_PROPELLED = 11
        RESET = 12
        LIGHT_STRIP_SCENE = 13
        SCENE_SPEED = 14

    class YRXY200Strobe(Enum):
        CLOSE = 0
        STROBE = 10
        OPEN = 250

    class YRXY200Color(Enum):
        WHITE = 0
        COLOR_1 = 10
        COLOR_2 = 20
        COLOR_3 = 30
        COLOR_4 = 40
        COLOR_5 = 50
        COLOR_6 = 60
        COLOR_7 = 70
        HALF_COLOR_1 = 80
        HALF_COLOR_2 = 90
        HALF_COLOR_3 = 100
        HALF_COLOR_4 = 110
        HALF_COLOR_5 = 120
        HALF_COLOR_6 = 130
        REVERSE_FLOW = 140
        FORWARD_FLOW = 198

    class YRXY200Pattern(Enum):
        CIRCULAR_WHITE = 0
        PATTERN_1 = 6
        PATTERN_2 = 12
        PATTERN_3 = 18
        PATTERN_4 = 24
        PATTERN_5 = 30
        PATTERN_6 = 36
        PATTERN_7 = 42
        PATTERN_8 = 48
        PATTERN_9 = 54
        PATTERN_10 = 60
        PATTERN_11 = 66
        PATTERN_DITHER = 72
        FORWARD_FLOW = 144
        REVERSE_FLOW = 200

    class YRXY200Prisim(Enum):
        NONE = 0
        PRISIM = 100
        PRISIM_ROTATION = 128

    class YRXY200Colorful(Enum):
        COLORFUL_OPEN = 0
        COLORFUL_CLOSE = 127

    class YRXY200SelfPropelled(Enum):
        NONE = 0
        SELF_PROPELLED = 30
        VOICE_ACTIVATED = 150

    class YRXY200Reset(Enum):
        NONE = 0
        X_AXIS = 21
        Y_AXIS = 101
        XY_AXIS = 201
        LAMPS = 250

    class YRXY200RingScene(Enum):
        OFF = 0
        COLOR_SELECTION = 16
        EFFECT_SELECTION = 24
        RANDOM_SELECTION = 32

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        name: str,
        category: Category,
        position_category: Category,
        dmx: DMXManager,
        addr: int,
        coord_frame: Optional[SpotCoordFrame] = None,
        osc: Optional[OSCManager] = None,
    ):
        super().__init__(
            name=name,
            category=category,
            position_category=position_category,
            dmx=dmx,
            addr=addr,
            num_chans=15,
            osc=osc,
        )

        # Conservative default for the physical color wheel settle time. Tune
        # against the fixture if it ends up too fast (visible color swap mid
        # fade-in) or too slow (dead time at zero brightness).
        self.color_swap_mechanical_time = 0.2

        # Default frame: ceiling-mount, straight down at tilt=100, north pole
        # horizontal at pan=0 tilt=10. Per-fixture override available if a
        # particular spot is mounted off-axis.
        self.coord_frame: SpotCoordFrame = coord_frame or SpotCoordFrame(
            pan_down=0.0,
            tilt_down=100.0,
            pan_north=0.0,
            tilt_north=10.0,
            pan_range=(0.0, 540.0),
            tilt_range=(0.0, 200.0),
        )
        # Set by the coord system state during patching wiring. Until then
        # post_map_output is a no-op (defensive — should never be hit).
        self.coord_state: Optional[CoordSystemState] = None
        # The OSCParam bound to /chan/{name}/pantilt/offset. Set by
        # SpotsBuilder after the mixer creates the virtual channel.
        # Used by rebind_coords to push refreshed UI values on toggle.
        self.pantilt_param: Optional[OSCParam] = None
        # Cached most recent mapping-space x/y values (16-bit). Mid-tick the
        # MixTargets update one of these; post_map_output runs the paired
        # conversion using both. Init at 16-bit midpoint so the fixture
        # starts in a defined state if no input arrives before the first tick.
        self._x_coord: float = 32767.0
        self._y_coord: float = 32767.0

        self.pan_channel = DMXControlChannel("pan_channel", 0)
        self.tilt_channel = DMXControlChannel("tilt_channel", 2)
        self.pan_fine_channel = DMXControlChannel("pan_fine_channel", 1)
        self.tilt_fine_channel = DMXControlChannel("tilt_fine_channel", 3)
        self.movement_speed_channel = DMXControlChannel("movement_speed_channel", 4)
        self.dimming_channel = DMXControlChannel("dimming_channel", 5)
        self.strobe_channel = DMXControlChannel(
            "strobe_channel",
            6,
            [
                DMXControlRange("off", 0, 10),
                DMXControlRange("strobe", 10, 250),
                DMXControlRange("on", 250, 255),
            ],
        )
        self.color_channel = DMXControlChannel(
            "color_channel",
            7,
            [
                DMXControlRange("WHITE", 0, 10),
                DMXControlRange("COLOR_1", 10, 20),
                DMXControlRange("COLOR_2", 20, 30),
                DMXControlRange("COLOR_3", 30, 40),
                DMXControlRange("COLOR_4", 40, 50),
                DMXControlRange("COLOR_5", 50, 60),
                DMXControlRange("COLOR_6", 60, 70),
                DMXControlRange("COLOR_7", 70, 80),
                DMXControlRange("HALF_COLOR_1", 80, 90),
                DMXControlRange("HALF_COLOR_2", 90, 100),
                DMXControlRange("HALF_COLOR_3", 100, 110),
                DMXControlRange("HALF_COLOR_4", 110, 120),
                DMXControlRange("HALF_COLOR_5", 120, 130),
                DMXControlRange("HALF_COLOR_6", 130, 140),
            ],
        )
        self.pattern_channel = DMXControlChannel(
            "pattern_channel",
            8,
            [
                DMXControlRange("CIRCULAR_WHITE", 0, 6),
                DMXControlRange("PATTERN_1", 6, 12),
                DMXControlRange("PATTERN_2", 12, 18),
                DMXControlRange("PATTERN_3", 18, 24),
                DMXControlRange("PATTERN_4", 24, 30),
                DMXControlRange("PATTERN_5", 30, 36),
                DMXControlRange("PATTERN_6", 36, 42),
                DMXControlRange("PATTERN_7", 42, 48),
                DMXControlRange("PATTERN_8", 48, 54),
                DMXControlRange("PATTERN_9", 54, 60),
                DMXControlRange("PATTERN_10", 60, 66),
                DMXControlRange("PATTERN_11", 66, 72),
            ],
        )
        self.prisim_channel = DMXControlChannel(
            "prisim_channel",
            9,
            [
                DMXControlRange("off", 0, 100),
                DMXControlRange("on", 100, 128),
                DMXControlRange("rotation", 128, 255),
            ],
        )

        pos_cat = self.position_category
        self.wrapped_targets = [
            MixTarget(self.dimming, "dimming", self.category),
            # x_coord and y_coord are mapping-space (active CoordSystem)
            # 16-bit values. The setters only cache; the paired conversion
            # to real pan/tilt happens in post_map_output once both axes
            # have finalised for the tick.
            MixTarget(self.x_coord, "x_coord", pos_cat, max_value=65535),
            MixTarget(self.y_coord, "y_coord", pos_cat, max_value=65535),
        ]

    def x_coord(self, val: DMXValue) -> None:
        self._x_coord = float(val)

    def y_coord(self, val: DMXValue) -> None:
        self._y_coord = float(val)

    def post_map_output(self) -> None:
        """Convert the cached mapping-space (x, y) into real pan/tilt and
        write to DMX. Called by the mixer once per tick after every
        channel has accumulated."""
        if self.coord_state is None:
            return
        real = self.coord_state.active.mapping_to_real(
            [self._x_coord, self._y_coord],
            self.coord_frame,
            current_real=[float(self._pan), float(self._tilt)],
        )
        if real is None:
            # Unreachable mapping point — freeze on the last good real
            # values so the head doesn't jump.
            return
        self.pan(int(real[0]), fine=True)
        self.tilt(int(real[1]), fine=True)

    def rebind_coords(self, old: CoordSystem, new: CoordSystem) -> None:
        """Re-express stored mapping-space offsets when the active coord
        system changes, so the head stays still across the toggle."""
        real = old.mapping_to_real(
            [self._x_coord, self._y_coord],
            self.coord_frame,
            current_real=[float(self._pan), float(self._tilt)],
        )
        if real is None:
            return
        new_xy = new.real_to_mapping(real, self.coord_frame)
        self._x_coord = new_xy[0]
        self._y_coord = new_xy[1]
        # Also update the underlying mix-channel offsets so the mixer's
        # accumulator starts from the re-expressed values on the next tick.
        if self.pantilt_param is not None:
            # Push the pair back onto the mix channel (PantiltChannel.offset
            # is a 2-vec setter that fans into the underlying channels).
            self.pantilt_param.dispatch_lambda(self.pantilt_param.addr, new_xy)
            self.pantilt_param.sync()

    def send_visualizer(self) -> None:
        super().send_visualizer()
        if self.osc is not None:
            self.osc.send_osc(
                "/visualizer/fixture/{}/pantilt".format(self.name),
                [self._pan, self._tilt],
            )

    def shutter(self, close_shutter: bool) -> None:
        self.strobe_enabled = False
        self.strobe_rate(0)

        if close_shutter:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.STROBE.value,
                YRXY200Spot.YRXY200Strobe.CLOSE.value,
            )
        else:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.STROBE.value,
                YRXY200Spot.YRXY200Strobe.OPEN.value,
            )

    def rotate_color(self, forward: bool, rate: int = 0) -> None:
        if forward:
            rate = cast(int, value_map(rate, 0, 255, 0, 197 - 140, True))
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.COLOR.value,
                YRXY200Spot.YRXY200Color.FORWARD_FLOW.value + rate,
            )
        else:
            rate = cast(int, value_map(rate, 0, 255, 0, 255 - 198, True))
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.COLOR.value,
                YRXY200Spot.YRXY200Color.REVERSE_FLOW.value + rate,
            )

    def rotate_pattern(self, forward: bool, rate: int = 0) -> None:
        if forward:
            rate = cast(int, value_map(rate, 0, 255, 0, 144 - 199, True))

            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.PATTERN.value,
                YRXY200Spot.YRXY200Pattern.FORWARD_FLOW.value + rate,
            )
        else:
            rate = cast(int, value_map(rate, 0, 255, 0, 255 - 200, True))

            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.PATTERN.value,
                YRXY200Spot.YRXY200Pattern.REVERSE_FLOW.value + rate,
            )

    # def rotate_dither(self, index: int, rate: int) -> None:
    #     index = int(constrain(index, 0, len(self.patterns()) - 1))
    #     rate = cast(int, value_map(rate, 0, 255, 0, 6, True))

    #     self.dmx.set_channel(
    #         self.addr + YRXY200Spot.YRXY200Channel.PATTERN.value,
    #         YRXY200Spot.YRXY200Pattern.PATTERN_DITHER.value
    #         + self.patterns()[index].value
    #         + rate,
    #     )

    def colorful(self, enabled) -> None:
        # light prisim doing color diffraction
        if enabled:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.COLORFUL.value,
                YRXY200Spot.YRXY200Colorful.COLORFUL_CLOSE.value,
            )
        else:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.COLORFUL.value,
                YRXY200Spot.YRXY200Colorful.COLORFUL_OPEN.value,
            )

    def prisim(self, enable: bool, rotation: int = 0) -> None:
        self.prisim_enabled_value = enable
        self.prisim_rotation_value = rotation

        if not enable:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.PRISIM.value,
                YRXY200Spot.YRXY200Prisim.NONE.value,
            )
        elif rotation == 0:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.PRISIM.value,
                YRXY200Spot.YRXY200Prisim.PRISIM.value,
            )
        else:
            self.prisim_rotation_value = cast(
                int, value_map(rotation, 0, 255, 0, 255 - 192, True)
            )
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.PRISIM.value,
                YRXY200Spot.YRXY200Prisim.PRISIM_ROTATION.value
                + self.prisim_rotation_value,
            )

    def self_propelled(
        self, self_propelled: YRXY200SelfPropelled, offset: int = 0
    ) -> None:
        if self_propelled == YRXY200Spot.YRXY200SelfPropelled.SELF_PROPELLED:
            offset = cast(int, value_map(offset, 0, 255, 0, 149 - 30, True))
        elif self_propelled == YRXY200Spot.YRXY200SelfPropelled.VOICE_ACTIVATED:
            offset = cast(int, value_map(offset, 0, 255, 0, 255 - 150, True))
        else:
            offset = 0

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.SELF_PROPELLED.value,
            self_propelled.value + offset,
        )

    def reset(self, reset: bool) -> None:
        value = YRXY200Spot.YRXY200Reset.NONE
        if reset:
            value = YRXY200Spot.YRXY200Reset.LAMPS

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.RESET.value, value.value
        )

    def light_strip_scene(
        self, light_strip_scene: YRXY200RingScene, rate: int = 0
    ) -> None:
        if light_strip_scene == YRXY200Spot.YRXY200RingScene.COLOR_SELECTION:
            rate = cast(int, value_map(rate, 0, 255, 0, 74 - 5, True))
        elif light_strip_scene == YRXY200Spot.YRXY200RingScene.EFFECT_SELECTION:
            rate = cast(int, value_map(rate, 0, 255, 0, 248 - 75, True))
        elif light_strip_scene == YRXY200Spot.YRXY200RingScene.RANDOM_SELECTION:
            rate = cast(int, value_map(rate, 0, 255, 0, 255 - 249, True))
        else:
            rate = 0

        self.dmx.set_channel(
            YRXY200Spot.YRXY200Channel.LIGHT_STRIP_SCENE.value,
            light_strip_scene.value + rate,
        )

    def scene_speed(self, scene_speed):
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.SCENE_SPEED.value,
            scene_speed,
        )


# class YUER150Spot(Spot):
#     channels = [
#         DMXControlChannel("X_AXIS", 0),
#         DMXControlChannel("X_AXIS_FINE", 1),
#         DMXControlChannel("Y_AXIS", 2),
#         DMXControlChannel("Y_AXIS_FINE", 3),
#         DMXControlChannel("XY_SPEED", 4),
#         DMXControlChannel("DIMMING", 5),
#         DMXControlChannel(
#             "STROBE",
#             6,
#             [DMXControlRange("NO_STROBE", 0, 15), DMXControlRange("STROBE", 16, 255)],
#         ),
#         DMXControlChannel("COLOR", 7),
#         DMXControlChannel("PATTERN", 8),
#         DMXControlChannel("PRISIM", 9),
#         DMXControlChannel("SELF_PROPELLED", 10),
#         DMXControlChannel("RESET", 11),
#     ]

#     class YUER150Channel(Enum):
#         X_AXIS = 0
#         X_AXIS_FINE = 1
#         Y_AXIS = 2
#         Y_AXIS_FINE = 3
#         XY_SPEED = 4
#         DIMMING = 5
#         STROBE = 6
#         COLOR = 7
#         PATTERN = 8
#         PRISIM = 9
#         SELF_PROPELLED = 10
#         RESET = 11

#     class YUER150Strobe(Enum):
#         NO_STROBE = 0
#         STROBE = 16

#     class YUER150Color(Enum):
#         WHITE = 0
#         COLOR_1_RED = 16
#         COLOR_2_GREEN = 32
#         COLOR_3_BLUE = 48
#         COLOR_4_PURPLE = 64
#         COLOR_5_ORANGE = 80
#         COLOR_6_TEAL = 96
#         COLOR_7_YELLOW = 112
#         FORWARD_FLOW = 128

#     class YUER150Pattern(Enum):
#         CIRCULAR_WHITE = 0
#         PATTERN_1_MUSIC = 16
#         PATTERN_2_ZIG = 32
#         PATTERN_3_CROSS = 48
#         PATTERN_4_FLOWER = 64
#         PATTERN_5_CROSS = 80
#         PATTERN_6_TRIDENT = 96
#         PATTERN_7_SMALL_FLOWER = 112
#         REVERSE_FLOW = 128

#     class YUER150Prisim(Enum):
#         NONE = 0
#         PRISIM = 128
#         PRISIM_ROTATION = 137

#     class YUER150SelfPropelled(Enum):
#         NONE = 0
#         FAST = 51
#         SLOW = 101
#         SOUND = 201

#     class YUER150Reset(Enum):
#         NONE = 0
#         RESET = 250

#     def __init__(self, dmx: DMXManager, addr: int):
#         super().__init__(dmx=dmx, addr=addr, num_chans=12)

#     def x(self, x: int) -> None:
#         self.x_val[0] = cast(int, constrain(x, 0, 255))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.X_AXIS.value, self.x_val[0]
#         )

#     def x_fine(self, x_fine: int) -> None:
#         self.x_val[1] = cast(int, constrain(x_fine, 0, 255))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.X_AXIS_FINE.value, self.x_val[1]
#         )

#     def y(self, y: int) -> None:
#         self.y_val[0] = cast(int, constrain(y, 0, 255))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.Y_AXIS.value, self.y_val[0]
#         )

#     def y_fine(self, y_fine: int) -> None:
#         self.y_val[1] = cast(int, constrain(y_fine, 0, 255))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.Y_AXIS_FINE.value, self.y_val[1]
#         )

#     def xy_speed(self, speed: int) -> None:
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.XY_SPEED.value, speed
#         )

#     def dimming(self, value: DMXValue) -> None:
#         self.dimming_val = cast(int, constrain(value, 0, 255))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.DIMMING.value, value
#         )

#     def strobe(self, enable: bool, rate: int = 0) -> None:
#         self.strobe_enabled = enable

#         if not enable:
#             self.dmx.set_channel(
#                 self.addr + YUER150Spot.YUER150Channel.STROBE.value,
#                 YUER150Spot.YUER150Strobe.NO_STROBE.value,
#             )
#             self.strobe_rate = 0
#         else:
#             self.strobe_rate = cast(int, value_map(rate, 0, 255, 0, 255 - 16, True))
#             self.dmx.set_channel(
#                 self.addr + YUER150Spot.YUER150Channel.STROBE.value,
#                 YUER150Spot.YUER150Strobe.STROBE.value + self.strobe_rate,
#             )

#     def colors(self) -> List[YUER150Color]:
#         return [
#             YUER150Spot.YUER150Color.WHITE,
#             YUER150Spot.YUER150Color.COLOR_1_RED,
#             YUER150Spot.YUER150Color.COLOR_2_GREEN,
#             YUER150Spot.YUER150Color.COLOR_3_BLUE,
#             YUER150Spot.YUER150Color.COLOR_4_PURPLE,
#             YUER150Spot.YUER150Color.COLOR_5_ORANGE,
#             YUER150Spot.YUER150Color.COLOR_6_TEAL,
#             YUER150Spot.YUER150Color.COLOR_7_YELLOW,
#         ]

#     def color(self, index: int) -> None:
#         self.color_index = int(constrain(index, 0, len(self.colors()) - 1))

#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.COLOR.value,
#             self.colors()[self.color_index].value,
#         )

#     def white(self) -> None:
#         self.color(0)

#     # pylint: disable-next=unused-argument
#     def rotate_color(self, forward: bool, rate: int = 0) -> None:
#         # no reverse flow available

#         rate = cast(int, value_map(rate, 0, 255, 0, 255 - 128, True))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.PATTERN.value,
#             YUER150Spot.YUER150Color.FORWARD_FLOW.value + rate,
#         )

#     def patterns(self) -> List[YUER150Pattern]:
#         return [
#             YUER150Spot.YUER150Pattern.CIRCULAR_WHITE,
#             YUER150Spot.YUER150Pattern.PATTERN_1_MUSIC,
#             YUER150Spot.YUER150Pattern.PATTERN_2_ZIG,
#             YUER150Spot.YUER150Pattern.PATTERN_3_CROSS,
#             YUER150Spot.YUER150Pattern.PATTERN_4_FLOWER,
#             YUER150Spot.YUER150Pattern.PATTERN_5_CROSS,
#             YUER150Spot.YUER150Pattern.PATTERN_6_TRIDENT,
#             YUER150Spot.YUER150Pattern.PATTERN_7_SMALL_FLOWER,
#         ]

#     def pattern(self, index: int) -> None:
#         self.pattern_index = int(constrain(index, 0, len(self.patterns()) - 1))

#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.PATTERN.value,
#             self.patterns()[self.pattern_index].value,
#         )

#     def no_pattern(self) -> None:
#         self.pattern(0)

#     # pylint: disable-next=unused-argument
#     def rotate_pattern(self, forward: bool, rate: int = 0) -> None:
#         rate = cast(int, constrain(rate, 0, 255 - 128))

#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.PATTERN.value,
#             YUER150Spot.YUER150Pattern.REVERSE_FLOW.value + rate,
#         )

#     def prisim(self, enable: bool, rotation: int = 0) -> None:
#         self.prisim_enabled = enable
#         self.prisim_rotation = rotation

#         if not enable:
#             self.dmx.set_channel(
#                 self.addr + YUER150Spot.YUER150Channel.PRISIM.value,
#                 YUER150Spot.YUER150Prisim.NONE.value,
#             )
#         elif rotation == 0:
#             self.dmx.set_channel(
#                 self.addr + YUER150Spot.YUER150Channel.PRISIM.value,
#                 YUER150Spot.YUER150Prisim.PRISIM.value,
#             )
#         else:
#             self.prisim_rotation = cast(
#                 int, value_map(rotation, 0, 255, 0, 255 - 137, True)
#             )
#             self.dmx.set_channel(
#                 self.addr + YUER150Spot.YUER150Channel.PRISIM.value,
#                 YUER150Spot.YUER150Prisim.PRISIM_ROTATION.value + self.prisim_rotation,
#             )

#     def self_propelled(
#         self, self_propelled: YUER150SelfPropelled, offset: int = 0
#     ) -> None:
#         if self_propelled == YUER150Spot.YUER150SelfPropelled.FAST:
#             offset = cast(int, value_map(offset, 0, 255, 0, 100 - 51, True))
#         elif self_propelled == YUER150Spot.YUER150SelfPropelled.SLOW:
#             offset = cast(int, value_map(offset, 0, 255, 0, 200 - 101, True))
#         elif self_propelled == YUER150Spot.YUER150SelfPropelled.SOUND:
#             offset = cast(int, value_map(offset, 0, 255, 0, 255 - 201, True))

#         else:
#             offset = 0

#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.SELF_PROPELLED.value,
#             self_propelled.value + offset,
#         )

#     def reset(self, reset: YUER150Reset) -> None:
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.RESET.value, reset.value
#         )


class PinSpot(LightFixture):
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
            name=name, category=category, dmx=dmx, addr=addr, num_chans=6, osc=osc
        )

    def dimming(self, val: DMXValue) -> None:
        self.rgbw(val, val, val, val)

    def rgbw(self, r, g, b, w) -> None:
        self.set([255, r, g, b, w, 0])
