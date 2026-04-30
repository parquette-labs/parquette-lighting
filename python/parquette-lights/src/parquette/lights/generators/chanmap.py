from collections import deque
from typing import Any, Callable, List, Optional

from . import Generator
from ..fixtures.basics import MixTarget
from ..category import Category
from ..osc import OSCManager, OSCParam
from ..util.math import constrain

TICK_MS: int = 20
MAX_STUTTER_MS: int = 2000


class ChannelMapper:
    def map_output(
        self, value: float, channel: "MixChannel", idle: bool = False
    ) -> None:
        pass

    def required_history_ticks(self) -> int:
        return 1


class FixedMapper(ChannelMapper):
    """Sends a single channel value to one or more targets equally."""

    def __init__(self, *targets: MixTarget) -> None:
        self.targets = targets

    def map_output(
        self, value: float, channel: "MixChannel", idle: bool = False
    ) -> None:
        for target in self.targets:
            target(value, accumulate=True, idle=idle)


class NoOpMapper(ChannelMapper):
    pass


class StutterMapper(ChannelMapper):
    """Mono channel mapper that distributes a single input across fixture groups
    with time-delayed stutter offsets.

    Each group in fixture_groups receives the same stutter delay. Groups are
    lists of MixTargets that should fire at the same time step (e.g. a
    left/right pair).
    """

    def __init__(
        self,
        fixture_groups: List[List[MixTarget]],
        stutter_period: int = 500,
    ) -> None:
        self.fixture_groups = fixture_groups
        self.stutter_period = stutter_period

    def required_history_ticks(self) -> int:
        n = len(self.fixture_groups)
        if n <= 1:
            return 1
        return int(MAX_STUTTER_MS * (n - 1) / TICK_MS) + 1

    def map_output(
        self, value: float, channel: "MixChannel", idle: bool = False
    ) -> None:
        max_timeslice = len(channel.history) - 1
        for i, group in enumerate(self.fixture_groups):
            stutter_index = int(
                constrain(self.stutter_period * i / TICK_MS, 0, max_timeslice)
            )
            val = int(constrain(channel.value(stutter_index), 0, 255))
            for target in group:
                target(val, accumulate=True, idle=idle)


class MixChannel:
    # Virtual channels are OSC facades (e.g. PantiltChannel) that proxy
    # their offset onto multiple real channels. They skip tick / map_output
    # and are excluded from signal_patchbay routing.
    is_virtual: bool = False

    def __init__(
        self,
        name: str,
        category: Category,
        index: int,
        *,
        impulse_generator: Optional[Generator] = None,
        mapper: Optional[ChannelMapper] = None,
    ) -> None:
        self.name = name
        self.category = category
        self.index = index
        self.mapper: ChannelMapper = mapper or NoOpMapper()
        history_size = self.mapper.required_history_ticks()
        self.history: deque = deque([0.0] * history_size, maxlen=history_size)
        self._offset_storage: float = 0.0
        self.impulse_generator = impulse_generator
        self.impulse_connected = impulse_generator is not None
        self.connected_generators: List[Generator] = []

    @property
    def offset(self) -> Any:
        return self._offset_storage

    @offset.setter
    def offset(self, value: Any) -> None:
        self._offset_storage = float(value)

    def tick(self, ts: float) -> None:
        """Compute current value and push into history (O(1) via deque)."""
        val = self.offset
        for gen in self.connected_generators:
            val += gen.value(ts)
        val *= self.category.master
        if self.impulse_connected and self.impulse_generator is not None:
            val += self.impulse_generator.value(ts)
        self.history.appendleft(val)

    def value(self, timeslice: int = 0) -> float:
        """Read value from history. timeslice=0 is current, 1 is 20ms ago, etc."""
        return self.history[timeslice]

    def is_idle(self) -> bool:
        """True when the channel cannot produce non-zero output.

        Uses a small threshold for floating-point comparisons since
        OSC fader values may not land exactly on zero.
        """
        threshold = 0.001
        if abs(self.offset) > threshold:
            return False
        if self.category.master < threshold:
            return True
        for gen in self.connected_generators:
            if abs(gen.amp) > threshold or abs(gen.offset) > threshold:
                return False
        return True

    def map_output(self) -> None:
        self.mapper.map_output(self.value(), self, idle=self.is_idle())

    def register_offset(
        self, osc: OSCManager, on_change: Optional[Callable[[], None]] = None
    ) -> OSCParam:
        """Bind /chan/{name}/offset to this channel's offset attribute."""
        return OSCParam.bind(
            osc,
            "/chan/{}/offset".format(self.name),
            self,
            "offset",
            on_change=on_change,
        )

    @property
    def stutter_period(self) -> int:
        if isinstance(self.mapper, StutterMapper):
            return self.mapper.stutter_period
        return 0

    @stutter_period.setter
    def stutter_period(self, value: int) -> None:
        if isinstance(self.mapper, StutterMapper):
            self.mapper.stutter_period = int(value)

    def register_stutter_period(self, osc: OSCManager) -> Optional[OSCParam]:
        """Bind /chan/{category.name}/stutter_period to this channel.

        No-op for non-stutter channels. When several channels in the same
        category register this address, pythonosc fans each incoming
        message to every handler, so one UI slider drives all mappers in
        the category without a central helper.
        """
        if not isinstance(self.mapper, StutterMapper):
            return None
        return OSCParam.bind(
            osc,
            "/chan/{}/stutter_period".format(self.category.name),
            self,
            "stutter_period",
        )


class PantiltChannel(MixChannel):
    """Virtual channel exposing a paired offset over a single OSC address.

    Binds `/chan/{name}/offset` to a 2-vec whose writes distribute to the
    two underlying pan and tilt MixChannels. Skipped from tick /
    map_output / signal_patchbay because it's a pure OSC facade.
    """

    is_virtual = True

    def __init__(
        self,
        name: str,
        category: Category,
        pan_channel: MixChannel,
        tilt_channel: MixChannel,
    ) -> None:
        super().__init__(name, category, index=-1)
        self.pan_channel = pan_channel
        self.tilt_channel = tilt_channel

    @property
    def offset(self) -> Any:
        return [self.pan_channel.offset, self.tilt_channel.offset]

    @offset.setter
    def offset(self, value: Any) -> None:
        self.pan_channel.offset = float(value[0])
        self.tilt_channel.offset = float(value[1])

    def tick(self, ts: float) -> None:
        pass

    def map_output(self) -> None:
        pass
