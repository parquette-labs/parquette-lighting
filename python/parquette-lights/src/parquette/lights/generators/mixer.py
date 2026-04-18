from typing import (
    Any,
    List,
    Tuple,
    Dict,
    Optional,
)

import time

from . import Generator
from .chanmap import (
    MixChannel,
    MixTarget,
    FixedMapper,
    PantiltChannel,
    StutterMapper,
)
from ..osc import OSCManager, OSCParam
from ..dmx import DMXManager
from ..fixtures.basics import Fixture
from ..category import Categories, Category


class Mixer(object):
    @property
    def channel_lookup(self) -> Dict[str, MixChannel]:
        return {ch.name: ch for ch in self.mix_channels}

    def __init__(
        self,
        *,
        osc: OSCManager,
        dmx: DMXManager,
        generators: List[Generator],
        fixtures: List[Fixture],
        categories: Categories,
        debug: bool = False,
    ) -> None:
        self.osc = osc
        self.dmx = dmx
        self.generators = generators
        self.all_fixtures = fixtures
        self.categories = categories
        self.debug = debug

        impulse_gen = next(g for g in generators if g.name == "impulse")

        # Auto-generate a FixedMapper channel for every mix_target on every
        # fixture. Categories that receive impulse get it connected.
        impulse_categories = {categories.non_saved}
        self.fixture_targets: Dict[str, List[MixTarget]] = {}
        self.mix_channels: List[MixChannel] = []

        index = 0
        for fixture in self.all_fixtures:
            targets: List[MixTarget] = []
            for target in fixture.mix_targets():
                targets.append(target)

                chan_name = "{}/{}".format(fixture.name, target.name)
                impulse = (
                    impulse_gen if fixture.category in impulse_categories else None
                )
                ch = MixChannel(
                    chan_name,
                    target.category,
                    index,
                    impulse_generator=impulse,
                    mapper=FixedMapper(target),
                )
                self.mix_channels.append(ch)
                index += 1
            self.fixture_targets[fixture.name] = targets

        # Stutter channels for reds — paired groups front-to-back
        reds_fwd_groups: List[List[MixTarget]] = [
            [
                self.mix_target_for_fixture("front_1"),
                self.mix_target_for_fixture("front_2"),
            ],
            [
                self.mix_target_for_fixture("left_1"),
                self.mix_target_for_fixture("right_1"),
            ],
            [
                self.mix_target_for_fixture("left_2"),
                self.mix_target_for_fixture("right_2"),
            ],
            [
                self.mix_target_for_fixture("left_3"),
                self.mix_target_for_fixture("right_3"),
            ],
            [
                self.mix_target_for_fixture("left_4"),
                self.mix_target_for_fixture("right_4"),
            ],
        ]
        reds_zig_groups: List[List[MixTarget]] = [
            [self.mix_target_for_fixture("front_1")],
            [self.mix_target_for_fixture("front_2")],
            [self.mix_target_for_fixture("left_1")],
            [self.mix_target_for_fixture("right_1")],
            [self.mix_target_for_fixture("left_2")],
            [self.mix_target_for_fixture("right_2")],
            [self.mix_target_for_fixture("left_3")],
            [self.mix_target_for_fixture("right_3")],
            [self.mix_target_for_fixture("left_4")],
            [self.mix_target_for_fixture("right_4")],
        ]

        self.reds_fwd_mapper = StutterMapper(reds_fwd_groups)
        self.reds_back_mapper = StutterMapper(list(reversed(reds_fwd_groups)))
        self.reds_zig_mapper = StutterMapper(reds_zig_groups)

        # Stutter channels for washes — wall washes only, ceiling excluded
        washes_fwd_groups: List[List[MixTarget]] = [
            [
                self.mix_target_for_fixture("wash_fl"),
                self.mix_target_for_fixture("wash_fr"),
            ],
            [
                self.mix_target_for_fixture("wash_ml"),
                self.mix_target_for_fixture("wash_mr"),
            ],
            [
                self.mix_target_for_fixture("wash_bl"),
                self.mix_target_for_fixture("wash_br"),
            ],
        ]

        self.washes_fwd_mapper = StutterMapper(washes_fwd_groups)
        self.washes_back_mapper = StutterMapper(list(reversed(washes_fwd_groups)))

        # Mono channels — single input drives all targets in a group equally
        all_reds_targets = [
            self.mix_target_for_fixture(n)
            for n in [
                "front_1",
                "front_2",
                "left_1",
                "left_2",
                "left_3",
                "left_4",
                "right_1",
                "right_2",
                "right_3",
                "right_4",
            ]
        ]
        all_wall_wash_targets = [
            self.mix_target_for_fixture(n)
            for n in ["wash_fl", "wash_fr", "wash_ml", "wash_mr", "wash_bl", "wash_br"]
        ]

        special_channels: List[MixChannel] = [
            MixChannel(
                "reds_fwd",
                categories.reds,
                index,
                mapper=self.reds_fwd_mapper,
            ),
            MixChannel(
                "reds_back",
                categories.reds,
                index + 1,
                mapper=self.reds_back_mapper,
            ),
            MixChannel(
                "reds_zig",
                categories.reds,
                index + 2,
                mapper=self.reds_zig_mapper,
            ),
            MixChannel(
                "washes_fwd",
                categories.washes,
                index + 3,
                mapper=self.washes_fwd_mapper,
            ),
            MixChannel(
                "washes_back",
                categories.washes,
                index + 4,
                mapper=self.washes_back_mapper,
            ),
            # Mono channels
            MixChannel(
                "reds_mono",
                categories.reds,
                index + 5,
                mapper=FixedMapper(*all_reds_targets),
            ),
            MixChannel(
                "washes_mono",
                categories.washes,
                index + 6,
                impulse_generator=impulse_gen,
                mapper=FixedMapper(*all_wall_wash_targets),
            ),
        ]
        self.mix_channels.extend(special_channels)

        # Virtual pantilt channels — expose /chan/{spot}.pantilt/offset as a
        # single 2-vec that fans into the underlying pan and tilt channels.
        # Same for pan_fine / tilt_fine. Added to mix_channels so the
        # ChannelLevelsBuilder picks them up for /chan/.../offset bindings;
        # patchbay_param filters them out because they're OSC facades, not
        # routable mixer outputs.
        lookup = {ch.name: ch for ch in self.mix_channels}
        for spot_name in ("spot_1", "spot_2"):
            pan_ch = lookup.get("{}/pan".format(spot_name))
            tilt_ch = lookup.get("{}/tilt".format(spot_name))
            if pan_ch and tilt_ch:
                pan_ch.offset = 32767
                tilt_ch.offset = 32767
                self.mix_channels.append(
                    PantiltChannel(
                        "{}/pantilt".format(spot_name),
                        pan_ch.category,
                        pan_ch,
                        tilt_ch,
                    )
                )

        # Each stutter channel re-registers /chan/{category.name}/stutter_period
        # on the OSC dispatcher. pythonosc fans incoming messages to every
        # handler, so one slider drives every mapper in a category. The
        # returned OSCParams are grouped by category for the preset manager.
        self.stutter_period_params_by_category: Dict[Category, List[OSCParam]] = {}
        for ch in self.mix_channels:
            param = ch.register_stutter_period(self.osc)
            if param is not None:
                self.stutter_period_params_by_category.setdefault(
                    ch.category, []
                ).append(param)

        # History buffers for FFT generator outputs, sampled once per
        # runChannelMix tick. Only populated and broadcast while the fft_dmx
        # modal heartbeats /visualizer/enable_fft_gen_timeseries, to avoid wasting compute
        # otherwise.
        self.fft_history_len = 200
        self.fft_gen_history: Dict[str, List[float]] = {
            "fft_1": [0.0] * self.fft_history_len,
            "fft_2": [0.0] * self.fft_history_len,
        }
        self.fft_viz_until: float = 0.0
        self.synth_visualizer_until: float = 0.0
        self.fixture_visualizer_until: float = 0.0

        # Synth visualizer mirrors the history of a selected source channel.
        # Set via /visualizer/synth_source OSC param. Empty string means off.
        self.synth_visualizer_source: str = ""
        self.debug_tick: int = 0

        # Heartbeat dispatchers for visualizer gates — self-registered so
        # builders and server.py don't have to know about them.
        osc.dispatcher.map(
            "/visualizer/enable_fft_gen_timeseries",
            lambda _a, *args: self.set_fft_viz(bool(args[0])),
        )
        osc.dispatcher.map(
            "/visualizer/enable_synth",
            lambda _a, *args: self.set_synth_visualizer(bool(args[0])),
        )
        osc.dispatcher.map(
            "/visualizer/enable_fixture",
            lambda _a, *args: self.set_fixture_visualizer(bool(args[0])),
        )

    def set_fft_viz(self, enable: bool) -> None:
        # Heartbeat-driven: each /visualizer/enable_fft_gen_timeseries with value=1 extends the window
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

    def set_fixture_visualizer(self, enable: bool) -> None:
        if enable:
            self.fixture_visualizer_until = time.time() + 2.0

    def fixture_visualizer_active(self) -> bool:
        return time.time() < self.fixture_visualizer_until

    def mix_target_for_fixture(self, fixture_name: str, index: int = 0) -> MixTarget:
        return self.fixture_targets[fixture_name][index]

    def all_mix_targets(self) -> List[MixTarget]:
        return [mt for targets in self.fixture_targets.values() for mt in targets]

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
            if self.debug:
                print(
                    "DEBUG configureSignalPath: connected {} -> {}".format(
                        target_gen, target_chan
                    ),
                    flush=True,
                )
        elif not enable and gen in ch.connected_generators:
            ch.connected_generators.remove(gen)
            if self.debug:
                print(
                    "DEBUG configureSignalPath: disconnected {} -> {}".format(
                        target_gen, target_chan
                    ),
                    flush=True,
                )

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

        if self.debug:
            self.debug_tick += 1
            if self.debug_tick % 500 == 1:
                nonzero = [
                    "{} = {:.2f} (gens: {})".format(
                        ch.name,
                        ch.value(),
                        ", ".join(g.name for g in ch.connected_generators),
                    )
                    for ch in self.mix_channels
                    if ch.value() != 0.0
                ]
                print(
                    "DEBUG runChannelMix tick {}: {} nonzero channels{}".format(
                        self.debug_tick,
                        len(nonzero),
                        ": " + "; ".join(nonzero) if nonzero else "",
                    ),
                    flush=True,
                )

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
                if self.debug and self.debug_tick % 500 == 1:
                    print(
                        "DEBUG fft_gen_history: {} = {:.4f}".format(name, hist[0]),
                        flush=True,
                    )

    def runOutputMix(self) -> None:
        # Clear all accumulators and zero all fixtures
        for mt in self.all_mix_targets():
            mt(0)
        # Each channel contributes via accumulation
        for ch in self.mix_channels:
            ch.map_output()
        # After all channels mapped, fixtures hold their final accumulated totals

        # Virtual synth visualizer output: forward selected source channel's
        # history to frontend over OSC, not bound to any DMX fixture.
        if self.synth_visualizer_active() and self.synth_visualizer_source:
            source = self.channel_lookup.get(self.synth_visualizer_source)
            if source is not None:
                sv_history = list(source.history)[: min(200, len(source.history))]
                self.osc.send_osc("/visualizer/synth_history", sv_history)

        if self.fft_viz_active():
            self.osc.send_osc(
                "/visualizer/fftgen_1_history", list(self.fft_gen_history["fft_1"])
            )
            self.osc.send_osc(
                "/visualizer/fftgen_2_history", list(self.fft_gen_history["fft_2"])
            )

        if self.fixture_visualizer_active():
            for fixture in self.all_fixtures:
                fixture.send_visualizer()

    def updateDMX(self) -> None:
        self.dmx.submit()

    def patchbay_param(self, category: Category) -> "SignalPatchParam":
        """Build a SignalPatchParam for every channel in `category`.

        Address is derived from category.name so builders don't have to
        hardcode `/signal_patchbay/<name>` in every build_params method.
        """
        chan_names = [
            ch.name
            for ch in self.mix_channels
            if ch.category is category and not ch.is_virtual
        ]
        return SignalPatchParam(
            self.osc,
            "/signal_patchbay/{}".format(category.name),
            chan_names,
            self,
        )

    def stutter_period_params(self, category: Category) -> List[OSCParam]:
        """Return the stutter_period OSCParams registered by channels in `category`.

        Builders splat these into their build_params output so the preset
        manager tracks the values. Empty list for categories without
        stutter channels.
        """
        return self.stutter_period_params_by_category.get(category, [])

    def synth_source_param(self, osc: OSCManager) -> OSCParam:
        """Bind /visualizer/synth_source to the mixer's synth_visualizer_source."""
        return OSCParam.bind(
            osc, "/visualizer/synth_source", self, "synth_visualizer_source"
        )


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

    def load(self, addr: str, *args: Any, sync: bool = True) -> None:
        for chan_name in self.chan_names:
            self.mixer.clearSignalMatrix(chan_name)

        for conf in args:
            for chan_name in conf[1:]:
                if chan_name in self.chan_names:
                    self.mixer.configureSignalPath(conf[0], chan_name, True)

        if sync:
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
