from typing import List, Optional

from . import Generator
from ..fixtures.basics import MixTarget
from ..osc import OSCManager
from ..util.math import constrain


class ChannelMapper:
    def map_output(self, value: float, channel: "MixChannel") -> None:
        pass


class FixedMapper(ChannelMapper):
    """Sends a single channel value to one or more targets equally."""

    def __init__(self, *targets: MixTarget) -> None:
        self.targets = targets

    def map_output(self, value: float, channel: "MixChannel") -> None:
        for target in self.targets:
            target(value, accumulate=True)


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

    def map_output(self, value: float, channel: "MixChannel") -> None:
        max_timeslice = len(channel.history) - 1
        for i, group in enumerate(self.fixture_groups):
            stutter_index = int(
                constrain(self.stutter_period * i / 10, 0, max_timeslice)
            )
            val = int(constrain(channel.value(stutter_index), 0, 255))
            for target in group:
                target(val, accumulate=True)


class MixChannel:
    def __init__(
        self,
        name: str,
        category: str,
        index: int,
        history_ticks: int,
        *,
        osc: OSCManager,
        impulse_generator: Optional[Generator] = None,
        mapper: Optional[ChannelMapper] = None,
    ) -> None:
        self.name = name
        self.category = category
        self.index = index
        self.history: List[float] = [0.0] * history_ticks
        self.offset: float = 0.0
        self.impulse_generator = impulse_generator
        self.impulse_connected = impulse_generator is not None
        self.master_value: float = 1.0
        self.connected_generators: List[Generator] = []
        self.mapper: ChannelMapper = mapper or NoOpMapper()

        osc.dispatcher.map(
            "/{}_master".format(category),
            lambda addr, *args: setattr(self, "master_value", float(args[0])),
        )

    def tick(self, ts: float) -> None:
        """Compute current value and push into history."""
        val = self.offset
        for gen in self.connected_generators:
            val += gen.value(ts)
        val *= self.master_value
        if self.impulse_connected and self.impulse_generator is not None:
            val += self.impulse_generator.value(ts)
        self.history[1:] = self.history[0:-1]
        self.history[0] = val

    def value(self, timeslice: int = 0) -> float:
        """Read value from history. timeslice=0 is current, 1 is 20ms ago, etc."""
        return self.history[timeslice]

    def map_output(self) -> None:
        self.mapper.map_output(self.value(), self)
