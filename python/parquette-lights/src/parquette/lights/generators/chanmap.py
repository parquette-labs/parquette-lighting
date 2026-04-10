from typing import List, Optional

from . import Generator
from ..fixtures import LightFixture, Spot, RGBWLight
from ..util.math import constrain

FixtureType = Spot | RGBWLight | LightFixture


class ChannelMapper:
    def map_output(self, value: float, channel: "MixChannel") -> None:
        pass


class FixedMapper(ChannelMapper):
    def __init__(self, fixture: FixtureType) -> None:
        self.fixture = fixture

    def map_output(self, value: float, channel: "MixChannel") -> None:
        self.fixture.dimming(value)


class NoOpMapper(ChannelMapper):
    pass


class RedsMapper(ChannelMapper):
    def __init__(
        self,
        left: List[FixtureType],
        right: List[FixtureType],
        front: List[FixtureType],
    ) -> None:
        self.left = left
        self.right = right
        self.front = front
        self.mode = "MONO"
        self.stutter_period = 500

    def map_output(self, value: float, channel: "MixChannel") -> None:
        if self.mode == "MONO":
            self.map_mono(value, channel)
        elif self.mode == "PENTA":
            self.map_penta(value, channel)
        elif self.mode in ("FWD", "BACK"):
            self.map_fwd_back(value, channel)
        elif self.mode == "ZIG":
            self.map_zig(value, channel)

    def map_mono(self, value: float, channel: "MixChannel") -> None:
        if channel.name == "chan_1":
            for fixture in self.left + self.right + self.front:
                fixture.dimming(value)

    def map_penta(self, value: float, channel: "MixChannel") -> None:
        if channel.name == "chan_1":
            for fixture in self.front:
                fixture.dimming(value)
        elif channel.name in ("chan_2", "chan_3", "chan_4", "chan_5"):
            pair_index = int(channel.name.split("_")[1]) - 2
            if 0 <= pair_index < len(self.left):
                self.left[pair_index].dimming(value)
                self.right[pair_index].dimming(value)

    # pylint: disable-next=unused-argument
    def map_fwd_back(self, value: float, channel: "MixChannel") -> None:
        if channel.name not in ("chan_1", "chan_2"):
            return
        pairs = list(
            zip(
                self.front[0:1] + self.left,
                self.front[1:2] + self.right,
            )
        )
        if self.mode == "BACK":
            pairs = list(reversed(pairs))
        max_timeslice = len(channel.history) - 1
        for i, (fixture_l, fixture_r) in enumerate(pairs):
            stutter_index = int(
                constrain(self.stutter_period * i / 10, 0, max_timeslice)
            )
            if channel.name == "chan_1":
                fixture_l.dimming(int(constrain(channel.value(stutter_index), 0, 255)))
            else:
                fixture_r.dimming(int(constrain(channel.value(stutter_index), 0, 255)))

    # pylint: disable-next=unused-argument
    def map_zig(self, value: float, channel: "MixChannel") -> None:
        if channel.name != "chan_1":
            return
        interleaved = [
            val
            for tup in zip(
                self.front[0:1] + self.left,
                self.front[1:2] + self.right,
            )
            for val in tup
        ]
        max_timeslice = len(channel.history) - 1
        for i, fixture in enumerate(interleaved):
            stutter_index = int(
                constrain(self.stutter_period * i / 10, 0, max_timeslice)
            )
            fixture.dimming(int(constrain(channel.value(stutter_index), 0, 255)))


class WashMapper(ChannelMapper):
    def __init__(self, fixtures: List[FixtureType]) -> None:
        self.fixtures = fixtures
        self.mode = "MONO"
        self.stutter_period = 500

    def map_output(self, value: float, channel: "MixChannel") -> None:
        if self.mode == "MONO":
            self.map_mono(value, channel)
        elif self.mode == "UNIQUE":
            self.map_unique(value, channel)
        elif self.mode in ("FWD", "BACK"):
            self.map_fwd_back(value, channel)

    def map_mono(self, value: float, channel: "MixChannel") -> None:
        if channel.name == "wash_1":
            for i in range(6):
                self.fixtures[i].dimming(value)
        elif channel.name == "wash_7":
            self.fixtures[6].dimming(value)
        elif channel.name == "wash_8":
            self.fixtures[7].dimming(value)

    def map_unique(self, value: float, channel: "MixChannel") -> None:
        fixture_index = int(channel.name.split("_")[1]) - 1
        self.fixtures[fixture_index].dimming(value)

    def map_fwd_back(self, value: float, channel: "MixChannel") -> None:
        if channel.name in ("wash_7", "wash_8"):
            fixture_index = int(channel.name.split("_")[1]) - 1
            self.fixtures[fixture_index].dimming(value)
            return
        if channel.name not in ("wash_1", "wash_2"):
            return
        pairs = list(
            zip(
                (self.fixtures[0], self.fixtures[2], self.fixtures[4]),
                (self.fixtures[1], self.fixtures[3], self.fixtures[5]),
            )
        )
        if self.mode == "BACK":
            pairs = list(reversed(pairs))
        max_timeslice = len(channel.history) - 1
        for i, (fixture_l, fixture_r) in enumerate(pairs):
            stutter_index = int(
                constrain(self.stutter_period * i / 10, 0, max_timeslice)
            )
            if channel.name == "wash_1":
                fixture_l.dimming(int(constrain(channel.value(stutter_index), 0, 255)))
            else:
                fixture_r.dimming(int(constrain(channel.value(stutter_index), 0, 255)))


class MixChannel:
    def __init__(
        self,
        name: str,
        category: str,
        index: int,
        history_ticks: int,
        *,
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
