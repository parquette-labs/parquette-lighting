from typing import (
    Any,
    List,
    Tuple,
    cast,
    Dict,
    Optional,
)

import time
import math

from . import Generator
from .chanmap import (
    MixChannel,
    FixtureType,
    FixedMapper,
    RedsMapper,
    WashMapper,
)
from ..osc import OSCManager, OSCParam
from ..dmx import DMXManager
from ..fixtures import LightFixture, Spot


class Mixer(object):
    MASTER_ATTRS = (
        "reds_master",
        "plants_master",
        "booth_master",
        "washes_master",
        "spots_master",
    )

    @staticmethod
    def make_master_property(master_name: str, category: str) -> property:
        backing_field = master_name + "_val"

        def getter(self: "Mixer") -> float:
            return getattr(self, backing_field)

        def setter(self: "Mixer", value: float) -> None:
            setattr(self, backing_field, value)
            for ch in self.mix_channels:
                if ch.category == category:
                    ch.master_value = value

        return property(getter, setter)

    reds_master = make_master_property("reds_master", "reds")
    plants_master = make_master_property("plants_master", "plants")
    booth_master = make_master_property("booth_master", "booth")
    spots_master = make_master_property("spots_master", "spots_light")
    washes_master = make_master_property("washes_master", "washes")

    def save_current_masters(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {attr: getattr(self, attr) for attr in self.MASTER_ATTRS}

        # Sodium is technically a channel level (lives under "non-saved" in
        # the categorized_channel_names map) but we persist it alongside the
        # masters so the room comes back up with the same house-light state.
        data["sodium"] = self.getChannelLevel("sodium")
        return data

    def load_current_masters(self, data: Dict[str, Any]) -> None:
        for attr, value in data.items():
            if attr in self.MASTER_ATTRS:
                setattr(self, attr, value)
            elif attr == "sodium":
                self.setChannelLevel("sodium", value)

    def __init__(
        self,
        *,
        osc: OSCManager,
        dmx: DMXManager,
        generators: List[Generator],
        spots: List[Spot],
        washes: List[LightFixture],
        history_len: float,
    ) -> None:
        self.osc = osc
        self.dmx = dmx
        self.generators = generators

        self.history_ticks = math.ceil(history_len * 1000 / 20)
        impulse_gen = next(g for g in generators if g.name == "impulse")

        # Build DMX fixture groups
        self.dmx_mappings: Dict[str, List[FixtureType]] = {
            "left": [
                LightFixture(dmx, 4),
                LightFixture(dmx, 3),
                LightFixture(dmx, 2),
                LightFixture(dmx, 1),
            ],
            "right": [
                LightFixture(dmx, 5),
                LightFixture(dmx, 6),
                LightFixture(dmx, 7),
                LightFixture(dmx, 8),
            ],
            "front": [LightFixture(dmx, 12), LightFixture(dmx, 9)],
            "under": [LightFixture(dmx, 10), LightFixture(dmx, 11)],
            "spot": cast(list[FixtureType], [LightFixture(dmx, 13)] + spots),
            "wash": cast(list[FixtureType], washes),
            "sodium": [LightFixture(dmx, 20)],
            "ceil": [
                LightFixture(dmx, 18),
                LightFixture(dmx, 19),
                LightFixture(dmx, 17),
            ],
        }

        # Create group mappers (held on Mixer for mode/stutter changes via OSC)
        self.reds_mapper = RedsMapper(
            left=self.dmx_mappings["left"],
            right=self.dmx_mappings["right"],
            front=self.dmx_mappings["front"],
        )
        self.wash_mapper = WashMapper(fixtures=self.dmx_mappings["wash"])

        self.mix_channels: List[MixChannel] = [
            # reds
            MixChannel(
                "chan_1", "reds", 0, self.history_ticks, mapper=self.reds_mapper
            ),
            MixChannel(
                "chan_2", "reds", 1, self.history_ticks, mapper=self.reds_mapper
            ),
            MixChannel(
                "chan_3", "reds", 2, self.history_ticks, mapper=self.reds_mapper
            ),
            MixChannel(
                "chan_4", "reds", 3, self.history_ticks, mapper=self.reds_mapper
            ),
            MixChannel(
                "chan_5", "reds", 4, self.history_ticks, mapper=self.reds_mapper
            ),
            # plants
            MixChannel(
                "ceil_1",
                "plants",
                5,
                self.history_ticks,
                mapper=FixedMapper(self.dmx_mappings["ceil"][0]),
            ),
            MixChannel(
                "ceil_2",
                "plants",
                6,
                self.history_ticks,
                mapper=FixedMapper(self.dmx_mappings["ceil"][1]),
            ),
            MixChannel(
                "ceil_3",
                "plants",
                7,
                self.history_ticks,
                mapper=FixedMapper(self.dmx_mappings["ceil"][2]),
            ),
            # booth
            MixChannel(
                "under_1",
                "booth",
                8,
                self.history_ticks,
                mapper=FixedMapper(self.dmx_mappings["under"][0]),
            ),
            MixChannel(
                "under_2",
                "booth",
                9,
                self.history_ticks,
                mapper=FixedMapper(self.dmx_mappings["under"][1]),
            ),
            # spots
            MixChannel(
                "tung_spot",
                "spots_light",
                10,
                self.history_ticks,
                mapper=FixedMapper(self.dmx_mappings["spot"][0]),
            ),
            MixChannel(
                "spot_1",
                "spots_light",
                11,
                self.history_ticks,
                mapper=FixedMapper(self.dmx_mappings["spot"][1]),
            ),
            MixChannel(
                "spot_2",
                "spots_light",
                12,
                self.history_ticks,
                mapper=FixedMapper(self.dmx_mappings["spot"][2]),
            ),
            # washes (impulse connected)
            MixChannel(
                "wash_1",
                "washes",
                13,
                self.history_ticks,
                impulse_generator=impulse_gen,
                mapper=self.wash_mapper,
            ),
            MixChannel(
                "wash_2",
                "washes",
                14,
                self.history_ticks,
                impulse_generator=impulse_gen,
                mapper=self.wash_mapper,
            ),
            MixChannel(
                "wash_3",
                "washes",
                15,
                self.history_ticks,
                impulse_generator=impulse_gen,
                mapper=self.wash_mapper,
            ),
            MixChannel(
                "wash_4",
                "washes",
                16,
                self.history_ticks,
                impulse_generator=impulse_gen,
                mapper=self.wash_mapper,
            ),
            MixChannel(
                "wash_5",
                "washes",
                17,
                self.history_ticks,
                impulse_generator=impulse_gen,
                mapper=self.wash_mapper,
            ),
            MixChannel(
                "wash_6",
                "washes",
                18,
                self.history_ticks,
                impulse_generator=impulse_gen,
                mapper=self.wash_mapper,
            ),
            MixChannel(
                "wash_7",
                "washes",
                19,
                self.history_ticks,
                impulse_generator=impulse_gen,
                mapper=self.wash_mapper,
            ),
            MixChannel(
                "wash_8",
                "washes",
                20,
                self.history_ticks,
                impulse_generator=impulse_gen,
                mapper=self.wash_mapper,
            ),
            # non-saved
            MixChannel(
                "sodium",
                "non-saved",
                21,
                self.history_ticks,
                impulse_generator=impulse_gen,
                mapper=FixedMapper(self.dmx_mappings["sodium"][0]),
            ),
            MixChannel("synth_visualizer", "non-saved", 22, self.history_ticks),
        ]

        self.channel_lookup: Dict[str, MixChannel] = {
            ch.name: ch for ch in self.mix_channels
        }
        self.channel_names: List[str] = [ch.name for ch in self.mix_channels]

        # Setting masters after mix_channels are built propagates to channels
        # via the property setters
        self.reds_master = 1.0
        self.spots_master = 1.0
        self.washes_master = 1.0
        self.booth_master = 1.0
        self.plants_master = 1.0

        # History buffers for FFT generator outputs, sampled once per
        # runChannelMix tick. Only populated and broadcast while the fft_dmx
        # modal heartbeats /set_fft_viz, to avoid wasting compute otherwise.
        self.fft_history_len = 200
        self.fft_gen_history: Dict[str, List[float]] = {
            "fft_1": [0.0] * self.fft_history_len,
            "fft_2": [0.0] * self.fft_history_len,
        }
        self.fft_viz_until: float = 0.0
        self.synth_visualizer_until: float = 0.0

    @property
    def categorized_channel_names(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        for ch in self.mix_channels:
            result.setdefault(ch.category, []).append(ch.name)
        return result

    def set_fft_viz(self, enable: bool) -> None:
        # Heartbeat-driven: each /set_fft_viz with value=1 extends the window
        # by ~2s. "off" messages are ignored on purpose — multiple UI clients
        # may be connected, and one client sending 0 (because its active tab
        # isn't FFT/DMX) must not yank the gate closed for another client
        # that is on the FFT/DMX tab. The gate expires naturally ~2s after
        # the last "on" heartbeat from any client.
        if enable:
            self.fft_viz_until = time.time() + 2.0

    def fft_viz_active(self) -> bool:
        return time.time() < self.fft_viz_until

    def set_synth_visualizer(self, enable: bool) -> None:
        # Same multi-client semantics as set_fft_viz above.
        if enable:
            self.synth_visualizer_until = time.time() + 2.0

    def synth_visualizer_active(self) -> bool:
        return time.time() < self.synth_visualizer_until

    def setChannelLevel(self, chan_name: str, level: float) -> None:
        self.channel_lookup[chan_name].offset = level

    def getChannelLevel(self, chan_name: str) -> float:
        return self.channel_lookup[chan_name].offset

    def clearSignalMatrix(self, chan_name: Optional[str] = None) -> None:
        if chan_name is None:
            for ch in self.mix_channels:
                ch.connected_generators.clear()
        else:
            self.channel_lookup[chan_name].connected_generators.clear()

    def configureSignalPath(
        self, target_gen: str, target_chan: str, enable: bool
    ) -> None:
        ch = self.channel_lookup[target_chan]
        gen = next(g for g in self.generators if g.name == target_gen)
        if enable and gen not in ch.connected_generators:
            ch.connected_generators.append(gen)
        elif not enable and gen in ch.connected_generators:
            ch.connected_generators.remove(gen)

    def configureSignalMatrix(
        self, target_gen: str, target_chans: Tuple[str] | List[str]
    ) -> None:
        try:
            target_set = set(target_chans)
            for ch in self.mix_channels:
                self.configureSignalPath(target_gen, ch.name, ch.name in target_set)
        except (StopIteration, KeyError):
            print(
                "Couldn't parse signal mapping, gen {}, chans {}".format(
                    target_gen, target_chans
                ),
                flush=True,
            )

    def runChannelMix(self) -> None:
        ts = time.time() * 1000

        for ch in self.mix_channels:
            ch.tick(ts)

        # Sample fft generator outputs into the rolling history buffer when
        # the fft_dmx modal is open (heartbeat-driven). Skipped otherwise so
        # we don't pay the per-tick cost.
        if self.fft_viz_active():
            for name, hist in self.fft_gen_history.items():
                gen = next((g for g in self.generators if g.name == name), None)
                if gen is None:
                    continue
                hist[1:] = hist[0:-1]
                hist[0] = gen.value(ts)

    def runOutputMix(self) -> None:
        for ch in self.mix_channels:
            ch.map_output()

        # Virtual synth visualizer output: forward to frontend over OSC,
        # not bound to any DMX fixture.
        if self.synth_visualizer_active():
            sv_ch = self.channel_lookup["synth_visualizer"]
            sv_history = sv_ch.history[: min(200, len(sv_ch.history))]
            self.osc.send_osc("/synth_visualizer_history", sv_history)

        if self.fft_viz_active():
            self.osc.send_osc("/fftgen_1_history", list(self.fft_gen_history["fft_1"]))
            self.osc.send_osc("/fftgen_2_history", list(self.fft_gen_history["fft_2"]))

    def updateDMX(self) -> None:
        self.dmx.submit()


class SignalPatchParam(OSCParam):
    def __init__(
        self,
        osc: OSCManager,
        addr: str,
        chan_names: List[str],
        mixer: Mixer,
    ) -> None:
        super().__init__(osc, addr, self.value_builder, self.dispatch_patch)
        self.mixer = mixer
        self.chan_names = chan_names

    def value_builder(self) -> List[List[str]]:
        mappings: List[List[str]] = []
        for gen in self.mixer.generators:
            gen_mapping = [gen.name]
            for ch in self.mixer.mix_channels:
                if gen in ch.connected_generators:
                    gen_mapping.append(ch.name)
            mappings.append(gen_mapping)
        return mappings

    def load(self, addr: str, *args: List[str]) -> None:
        for chan_name in self.chan_names:
            self.mixer.clearSignalMatrix(chan_name)

        for conf in args:
            for chan_name in conf[1:]:
                if chan_name in self.chan_names:
                    self.mixer.configureSignalPath(conf[0], chan_name, True)

        self.sync()

    def dispatch_patch(self, _: str, *args):
        for chan_name in self.chan_names:
            self.mixer.configureSignalPath(args[0], chan_name, chan_name in args[1:])

    def sync(self) -> None:
        for gen in self.mixer.generators:
            output_val = [gen.name]
            output_val.append("")
            self.osc.send_osc(self.addr, output_val)

        for gen in self.mixer.generators:
            output_val = [gen.name]
            for ch in self.mixer.mix_channels:
                if gen in ch.connected_generators:
                    output_val.append(ch.name)
            self.osc.send_osc(self.addr, output_val)
