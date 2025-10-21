# pylint: disable=too-many-lines

from typing import List, Dict, Any, cast, Callable, Tuple
import sys
import time
from copy import copy
import math

import pickle
import pprint

import click

from .fixtures import YRXY200Spot, YUER150Spot, RGBWash

from .generators import (
    FFTGenerator,
    WaveGenerator,
    ImpulseGenerator,
    NoiseGenerator,
    BPMGenerator,
    Generator,
)

from .audio_analysis import FFTManager, AudioCapture

from .osc import OSCManager
from .dmx import DMXManager

from .util.math import constrain


class Mixer(object):
    def __init__(
        self,
        *,
        osc: OSCManager,
        dmx: DMXManager,
        generators: List[Generator],
        history_len: float,
    ) -> None:
        self.mode = "MONO"
        self.osc = osc
        self.dmx = dmx
        self.generators = generators
        self.channel_names: List[str] = [
            "chan_1",
            "chan_2",
            "chan_3",
            "chan_4",
            "chan_5",
            "chan_6",
            "chan_7",
            "chan_8",
            "chan_9",
            "chan_10",
            "under_1",
            "under_2",
            "chan_spot",
            "sodium",
            "ceil_1",
            "ceil_2",
            "ceil_3",
        ]
        self.num_channels = len(self.channel_names)

        self.dmx_mappings = {
            "left": [4, 3, 2, 1],
            "right": [5, 6, 7, 8],
            "front": [12, 9],
            "under": [10, 11],
            "spot": [13],
            "sodium": [20],
            "ceil": [18, 19, 17],
        }

        # TODO control the matrix sizing in open sound control with this var?
        # TODO this could be initialized / resetup in a subfn that can be reused if the live setup changes
        # This is an array of the output values at different time slices, the design is that each timeslice is 20ms back in time, so self.channels[timeslice][chan]
        self.channels = [
            [0.0] * self.num_channels for _ in range(math.ceil(history_len * 1000 / 20))
        ]
        # This is the default base value of each chan
        self.channel_offsets = [0.0] * self.num_channels
        # This is a matrix from the patch bay of what signals go to what chans of shape signal_matrix[num_gen][num_chan]
        self.signal_matrix = [
            [0.0] * self.num_channels for _ in range(len(self.generators))
        ]

        self.stutter_period = 500
        self.master_amp = 1
        self.wash_master = 1

    def setChannelLevel(self, chan_name: str, level: float):
        self.channel_offsets[self.channel_names.index(chan_name)] = level

    def getChannelLevel(self, chan_name: str) -> float:
        return self.channel_offsets[self.channel_names.index(chan_name)]

    def clearSignalMatrix(self) -> None:
        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.signal_matrix)):
            for chan_ix in range(len(self.signal_matrix[gen_ix])):
                self.signal_matrix[gen_ix][chan_ix] = 0

    def configureSignalMatrix(
        self, target_gen: str, target_chans: Tuple[str] | List[str]
    ) -> None:
        try:
            gen_ix = list(map(lambda gen: gen.name, self.generators)).index(target_gen)
            destinations = [
                self.channel_names.index(chan_name) for chan_name in target_chans
            ]
            for i in range(len(self.signal_matrix[gen_ix])):
                if i in destinations:
                    self.signal_matrix[gen_ix][i] = 1
                else:
                    self.signal_matrix[gen_ix][i] = 0

        except ValueError:
            print(
                "Couldn't parse signal mapping, gen {}, chans {}".format(
                    target_gen, target_chans
                ),
                flush=True,
            )

    def runChannelMix(self) -> None:
        # slide the channel history back one timestep
        self.channels[1:] = self.channels[0:-1]

        # setup current times
        self.channels[0] = copy(self.channel_offsets)

        ts = time.time() * 1000
        for gen_idx, gen_connected_chans in enumerate(self.signal_matrix):
            for chan_idx, chan_connected in enumerate(gen_connected_chans):
                self.channels[0][chan_idx] += (
                    self.generators[gen_idx].value(ts) * chan_connected
                )

        for i, val in enumerate(self.channels[0]):
            if not self.channel_names[i] in (
                "chan_spot",
                "under_1",
                "under_2",
                "sodium",
                "ceil_1",
                "ceil_2",
                "ceil_3",
            ):
                self.channels[0][i] = val * self.master_amp

        for i, val in enumerate(self.channels[0]):
            if self.channel_names[i] in (
                "under_1",
                "under_2",
                "ceil_1",
                "ceil_2",
                "ceil_3",
            ):
                self.channels[0][i] = val * self.wash_master

    def runOutputMix(self) -> None:
        self.dmx.set_channel(
            self.dmx_mappings["spot"][0],
            self.channels[0][self.channel_names.index("chan_spot")],
        )

        self.dmx.set_channel(
            self.dmx_mappings["under"][0],
            self.channels[0][self.channel_names.index("under_1")],
        )
        self.dmx.set_channel(
            self.dmx_mappings["under"][1],
            self.channels[0][self.channel_names.index("under_2")],
        )

        self.dmx.set_channel(
            self.dmx_mappings["sodium"][0],
            self.channels[0][self.channel_names.index("sodium")],
        )
        self.dmx.set_channel(
            self.dmx_mappings["ceil"][0],
            self.channels[0][self.channel_names.index("ceil_1")],
        )

        self.dmx.set_channel(
            self.dmx_mappings["ceil"][1],
            self.channels[0][self.channel_names.index("ceil_2")],
        )
        self.dmx.set_channel(
            self.dmx_mappings["ceil"][2],
            self.channels[0][self.channel_names.index("ceil_3")],
        )

        if self.mode == "MONO":
            for group, chans in self.dmx_mappings.items():
                if not group in ("spot", "under", "ceil", "sodium"):
                    for chan in chans:
                        self.dmx.set_channel(chan, self.channels[0][0])

        elif self.mode == "PENTA":
            for i, (chan_l, chan_r) in enumerate(
                zip(self.dmx_mappings["left"], self.dmx_mappings["right"])
            ):
                self.dmx.set_channel(chan_l, self.channels[0][i + 1])
                self.dmx.set_channel(chan_r, self.channels[0][i + 1])

            self.dmx.set_channel(self.dmx_mappings["front"][0], self.channels[0][0])
            self.dmx.set_channel(self.dmx_mappings["front"][1], self.channels[0][0])
        elif self.mode == "DECA":
            for i, chan in enumerate(
                self.dmx_mappings["left"]
                + self.dmx_mappings["right"]
                + self.dmx_mappings["front"]
            ):
                self.dmx.set_channel(chan, self.channels[0][i])
        elif self.mode in ("FWD", "BACK"):
            chan_zip = list(
                zip(
                    self.dmx_mappings["front"][0:1] + self.dmx_mappings["left"],
                    self.dmx_mappings["front"][1:2] + self.dmx_mappings["right"],
                )
            )
            if self.mode == "BACK":
                chan_zip = list(reversed(chan_zip))
            for i, (chan_l, chan_r) in enumerate(chan_zip):
                stutter_index = int(
                    constrain(
                        self.stutter_period * i / 10,
                        0,
                        len(self.channels) - 1,
                    )
                )
                self.dmx.set_channel(
                    chan_l,
                    int(
                        constrain(
                            self.channels[stutter_index][0],
                            0,
                            255,
                        )
                    ),
                )
                self.dmx.set_channel(
                    chan_r,
                    int(
                        constrain(
                            self.channels[stutter_index][1],
                            0,
                            255,
                        )
                    ),
                )
        elif self.mode == "ZIG":
            interleaved_chans = [
                val
                for tup in zip(
                    self.dmx_mappings["front"][0:1] + self.dmx_mappings["left"],
                    self.dmx_mappings["front"][1:2] + self.dmx_mappings["right"],
                )
                for val in tup
            ]

            for i, chan in enumerate(interleaved_chans):
                stutter_index = int(
                    constrain(
                        self.stutter_period * i / 10,
                        0,
                        len(self.channels) - 1,
                    )
                )
                self.dmx.set_channel(
                    chan,
                    int(
                        constrain(
                            self.channels[stutter_index][0],
                            0,
                            255,
                        )
                    ),
                )

    def updateDMX(self) -> None:
        self.dmx.submit()


class OSCParam(object):
    # pylint: disable-next=too-many-positional-arguments
    def __init__(
        self,
        osc: OSCManager,
        addr: str,
        value_lambda: Callable,
        dispatch_lambda: Callable,
    ) -> None:
        self.osc = osc
        self.addr = addr
        self.value_lambda = value_lambda
        self.dispatch_lambda = dispatch_lambda

        osc.dispatcher.map(addr, dispatch_lambda)

    def load(self, addr: str, args: Any) -> None:
        self.dispatch_lambda(addr, args)
        self.sync()

    def sync(self) -> None:
        self.osc.send_osc(self.addr, self.value_lambda())

    @classmethod
    def obj_param_setter(cls, value: Any, field: str, objs: List[Any]) -> None:
        for obj in objs:
            # TODO I assume this is hacky and can be nicer
            try:
                _field = getattr(obj.__class__, field)
                # this is some trash surely the pylint is a warning I'm doing garbage, but fix later
                # pylint: disable-next=unnecessary-dunder-call
                _field.__set__(obj, value)

            except AttributeError:
                obj.__dict__[field] = value


class PresetManager(object):
    def __init__(
        self,
        osc: OSCManager,
        exposed_params: List[OSCParam],
        filename: str,
        debug: bool = False,
    ) -> None:
        self.osc = osc
        self.exposed_params = exposed_params
        self.filename = filename
        self.stored_presets: Dict[str, List[Tuple[str, Any]]] = {}
        self.current_preset = "default"
        self.debug = debug

        osc.dispatcher.map("/save_preset", lambda addr, args: self.save())
        osc.dispatcher.map("/clear_preset", lambda addr, args: self.clear())
        osc.dispatcher.map("/preset_selector", lambda _, args: self.select(args))

    def load(self):
        try:
            with open(self.filename, "rb") as f:
                self.stored_presets = pickle.load(f)
        # pylint: disable=broad-exception-caught
        except Exception as e:
            print("Pickle load failed, bad or missing pickle", e, flush=True)

    def clear(self) -> None:
        del self.stored_presets[self.current_preset]

        with open("./params.pickle", "wb") as f:  # type: ignore
            pickle.dump(self.stored_presets, f)

    def save(self) -> None:
        self.stored_presets[self.current_preset] = []
        for param in self.exposed_params:
            self.stored_presets[self.current_preset].append(
                (param.addr, param.value_lambda())
            )
        if self.debug:
            pprint.pp(self.stored_presets)

        with open("./params.pickle", "wb") as f:  # type: ignore
            pickle.dump(self.stored_presets, f)

    def sync(self):
        for param in self.exposed_params:
            param.sync()
        self.osc.send_osc("/preset_selector", self.current_preset)

    def select(self, preset_name: str) -> None:
        self.current_preset = preset_name
        if self.current_preset not in self.stored_presets.keys():
            return

        for param_preset in self.stored_presets[self.current_preset]:
            addr, value = param_preset[0], param_preset[1]
            for param in self.exposed_params:
                if param.addr == addr:
                    param.load(addr, value)


class SignalPatchParam(OSCParam):
    def __init__(
        self,
        osc: OSCManager,
        addr: str,
        mixer: Mixer,
    ) -> None:
        super().__init__(osc, addr, self.value_builder, self.dispatch_patch)
        self.mixer = mixer

    def value_builder(self) -> List[List[str]]:
        mappings: List[List[str]] = []
        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.mixer.signal_matrix)):
            gen_mapping = [self.mixer.generators[gen_ix].name]
            for chan_ix in range(len(self.mixer.signal_matrix[gen_ix])):
                if self.mixer.signal_matrix[gen_ix][chan_ix]:
                    gen_mapping.append(self.mixer.channel_names[chan_ix])
            mappings.append(gen_mapping)
        return mappings

    def load(self, addr: str, args: List[List[str]]) -> None:
        self.mixer.clearSignalMatrix()

        for conf in args:
            self.mixer.configureSignalMatrix(conf[0], cast(List[str], conf[1:]))

        self.sync()

    def dispatch_patch(self, _: str, *args):
        self.mixer.configureSignalMatrix(args[0], args[1:])

    def sync(self) -> None:
        for gen_ix in range(len(self.mixer.signal_matrix)):
            output_val = [self.mixer.generators[gen_ix].name]
            self.osc.send_osc("/signal_patchbay", output_val)

        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.mixer.signal_matrix)):
            output_val = [self.mixer.generators[gen_ix].name]
            for chan_ix in range(len(self.mixer.signal_matrix[gen_ix])):
                if self.mixer.signal_matrix[gen_ix][chan_ix]:
                    output_val.append(self.mixer.channel_names[chan_ix])

            self.osc.send_osc("/signal_patchbay", output_val)


@click.command()
@click.option("--local-ip", default="127.0.0.1", type=str, help="IP address")
@click.option("--local-port", default=5005, type=int, help="port")
@click.option("--target-ip", default="127.0.0.1", type=str, help="IP address")
@click.option("--target-port", default=5006, type=int, help="port")
@click.option(
    "--art-net-ip", default="192.168.88.111", type=str, help="port for artnet node"
)
@click.option("--debug", is_flag=True, default=False)
@click.option("--boot-art-net", is_flag=True, default=False)
@click.option("--art-net-auto", is_flag=True, default=False)
@click.option(
    "--presets-file",
    default="params.pickle",
    type=str,
    help="file to store and load presets from",
)
# pylint: disable-next=too-many-positional-arguments
def run(
    local_ip: str,
    local_port: int,
    target_ip: str,
    target_port: int,
    art_net_ip: str,
    debug: bool,
    boot_art_net: bool,
    art_net_auto: bool,
    presets_file: str,
) -> None:
    print("Setup", flush=True)

    osc = OSCManager()
    osc.set_target(target_ip, target_port)
    osc.set_local(local_ip, local_port)
    osc.set_debug(debug)
    dmx = DMXManager(osc, art_net_ip)
    dmx.art_net_auto_send(art_net_auto)
    dmx.use_art_net = boot_art_net

    yp = YRXY200Spot(dmx, 33)
    yp.dimming(0)
    yp.strobe(YRXY200Spot.YRXY200Strobe.OPEN)
    yp.color(YRXY200Spot.YRXY200Color.WHITE)
    yp.pattern(YRXY200Spot.YRXY200Pattern.CIRCULAR_WHITE)
    yp.prisim(YRXY200Spot.YRXY200Prisim.NONE)
    yp.colorful(YRXY200Spot.YRXY200Colorful.COLORFUL_OPEN)
    yp.self_propelled(YRXY200Spot.YRXY200SelfPropelled.NONE)
    yp.light_strip_scene(YRXY200Spot.YRXY200RingScene.OFF)
    yp.scene_speed(0)
    yp.x(0)
    yp.y(127)

    sp = YUER150Spot(dmx, 21)
    sp.x(0)
    sp.y(127)
    sp.dimming(0)
    sp.strobe(YUER150Spot.YUER150Strobe.NO_STROBE)
    sp.color(YUER150Spot.YUER150Color.WHITE)
    sp.pattern(YUER150Spot.YUER150Pattern.CIRCULAR_WHITE)
    sp.prisim(YUER150Spot.YUER150Prisim.NONE)
    sp.self_propelled(YUER150Spot.YUER150SelfPropelled.NONE)

    w = RGBWash(dmx, 48)
    w.rgb(0, 0, 0)

    audio_capture = AudioCapture(osc)
    fft_manager = FFTManager(osc, audio_capture)

    initialAmp: float = 200
    initialPeriod: int = 3500

    noise1 = NoiseGenerator(
        name="noise_1", amp=initialAmp, offset=0, period=initialPeriod
    )
    noise2 = NoiseGenerator(
        name="noise_2", amp=initialAmp, offset=0, period=initialPeriod
    )
    wave1 = WaveGenerator(
        name="sin",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.SIN,
    )
    wave2 = WaveGenerator(
        name="square",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.SQUARE,
    )

    sq1 = WaveGenerator(
        name="sq_1",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.SQUARE,
        duty=150,
    )

    sq2 = WaveGenerator(
        name="sq_2",
        amp=initialAmp,
        period=initialPeriod,
        phase=476,
        offset=0,
        shape=WaveGenerator.Shape.SQUARE,
        duty=150,
    )

    sq3 = WaveGenerator(
        name="sq_3",
        amp=initialAmp,
        period=initialPeriod,
        phase=335,
        offset=0,
        shape=WaveGenerator.Shape.SQUARE,
        duty=150,
    )

    wave3 = WaveGenerator(
        name="triangle",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.TRIANGLE,
    )
    impulse = ImpulseGenerator(
        name="impulse",
        amp=255,
        offset=0,
        period=150,
        echo=1,
        echo_decay=1,
        duty=100,
    )

    fft1 = FFTGenerator(name="fft_1", amp=1, offset=0, subdivisions=1, memory_length=20)
    fft2 = FFTGenerator(name="fft_2", amp=1, offset=0, subdivisions=1, memory_length=20)

    bpm = BPMGenerator(name="bpm", amp=255, offset=0, duty=100)

    generators = [
        noise1,
        noise2,
        wave1,
        wave2,
        wave3,
        sq1,
        sq2,
        sq3,
        impulse,
        fft1,
        fft2,
        bpm,
    ]

    fft_manager.downstream = [fft1, fft2]
    fft_manager.bpm = bpm

    mixer = Mixer(
        osc=osc,
        dmx=dmx,
        generators=generators,
        history_len=666 * 6,
    )

    def fft_dispatch_wedge(fft, args):
        if len(args) == 1:
            fft.set_bounds(args[0][0], args[0][2])
        else:
            fft.set_bounds(args[0], args[2])

    exposed_params = [
        OSCParam(
            osc,
            "/amp",
            lambda: noise1.amp,
            lambda _, args: OSCParam.obj_param_setter(
                args, "amp", [noise1, noise2, wave1, wave2, wave3, sq1, sq2, sq3]
            ),
        ),
        OSCParam(
            osc,
            "/period",
            lambda: noise1.period,
            lambda _, args: OSCParam.obj_param_setter(
                args, "period", [noise1, noise2, wave1, wave2, wave3, sq1, sq2, sq3]
            ),
        ),
        OSCParam(
            osc,
            "/fft1_amp",
            lambda: fft1.amp,
            lambda _, args: OSCParam.obj_param_setter(args, "amp", [fft1]),
        ),
        OSCParam(
            osc,
            "/fft2_amp",
            lambda: fft2.amp,
            lambda _, args: OSCParam.obj_param_setter(args, "amp", [fft2]),
        ),
        OSCParam(
            osc,
            "/impulse_amp",
            lambda: impulse.amp,
            lambda _, args: OSCParam.obj_param_setter(args, "amp", [impulse]),
        ),
        OSCParam(
            osc,
            "/impulse_period",
            lambda: impulse.period,
            lambda _, args: OSCParam.obj_param_setter(args, "period", [impulse]),
        ),
        OSCParam(
            osc,
            "/impulse_duty",
            lambda: impulse.duty,
            lambda _, args: OSCParam.obj_param_setter(args, "duty", [impulse]),
        ),
        OSCParam(
            osc,
            "/impulse_echo",
            lambda: impulse.echo,
            lambda _, args: OSCParam.obj_param_setter(args, "echo", [impulse]),
        ),
        OSCParam(
            osc,
            "/impulse_decay",
            lambda: impulse.echo_decay,
            lambda _, args: OSCParam.obj_param_setter(args, "echo_decay", [impulse]),
        ),
        OSCParam(
            osc,
            "/stutter_period",
            lambda: mixer.stutter_period,
            lambda _, args: OSCParam.obj_param_setter(args, "stutter_period", [mixer]),
        ),
        OSCParam(
            osc,
            "/master_fader",
            lambda: mixer.master_amp,
            lambda _, args: OSCParam.obj_param_setter(args, "master_amp", [mixer]),
        ),
        OSCParam(
            osc,
            "/wash_master",
            lambda: mixer.wash_master,
            lambda _, args: OSCParam.obj_param_setter(args, "wash_master", [mixer]),
        ),
        OSCParam(
            osc,
            "/mode_switch",
            lambda: mixer.mode,
            lambda _, args: OSCParam.obj_param_setter(args, "mode", [mixer]),
        ),
        OSCParam(
            osc,
            "/fft_threshold_1",
            lambda: fft1.thres,
            lambda _, args: OSCParam.obj_param_setter(args, "thres", [fft1]),
        ),
        OSCParam(
            osc,
            "/fft_threshold_2",
            lambda: fft2.thres,
            lambda _, args: OSCParam.obj_param_setter(args, "thres", [fft2]),
        ),
        OSCParam(
            osc,
            "/manual_bpm_offset",
            lambda: bpm.manual_offset,
            lambda _, args: OSCParam.obj_param_setter(args, "manual_offset", [bpm]),
        ),
        OSCParam(
            osc,
            "/bpm_mult",
            lambda: bpm.bpm_mult,
            lambda _, args: OSCParam.obj_param_setter(args, "bpm_mult", [bpm]),
        ),
        OSCParam(
            osc,
            "/bpm_duty",
            lambda: bpm.duty,
            lambda _, args: OSCParam.obj_param_setter(args, "duty", [bpm]),
        ),
        OSCParam(
            osc,
            "/bpm_amp",
            lambda: bpm.amp,
            lambda _, args: OSCParam.obj_param_setter(args, "amp", [bpm]),
        ),
        SignalPatchParam(osc, "/signal_patchbay", mixer),
        OSCParam(
            osc,
            "/fft_bounds_1",
            lambda: (fft1.fft_bounds[0], 0, fft1.fft_bounds[1], 0),
            lambda addr, *args: fft_dispatch_wedge(fft1, args),
        ),
        OSCParam(
            osc,
            "/fft_bounds_2",
            lambda: (fft2.fft_bounds[0], 0, fft2.fft_bounds[1], 0),
            lambda addr, *args: fft_dispatch_wedge(fft2, args),
        ),
    ]

    for chan_name in mixer.channel_names:
        exposed_params.append(
            OSCParam(
                osc,
                "/chan_levels/{}".format(chan_name),
                lambda chan=chan_name: mixer.getChannelLevel(chan),
                lambda addr, args: mixer.setChannelLevel(addr.split("/")[2], args),
            )
        )

    presets = PresetManager(osc, exposed_params, presets_file, debug)
    presets.load()
    presets.select("default")

    osc.dispatcher.map("/reload", lambda addr, args: presets.sync())
    osc.dispatcher.map(
        "/impulse_punch",
        lambda addr, *args: impulse.punch(),
    )

    def receive_joystick_x(_, *args):
        incr = (args[0] - (1024 / 2)) / 300
        sp.x(sp.x_val[0] + incr)
        yp.x(yp.x_val[0] + incr)

    def receive_joystick_y(_, *args):
        incr = (args[0] - (1024 / 2)) / 300
        sp.y(sp.y_val[0] - incr)
        yp.y(yp.y_val[0] - incr)

    osc.dispatcher.map("/joystick_x", receive_joystick_x)
    osc.dispatcher.map("/joystick_y", receive_joystick_y)

    print("Start OSC server", flush=True)
    osc.serve(threaded=True)

    print("Sync front end", flush=True)
    presets.sync()

    print("Start compute loop", flush=True)
    try:
        while True:
            mixer.runChannelMix()
            mixer.runOutputMix()
            mixer.updateDMX()
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nShutdown FFT", flush=True)
        fft_manager.stop_fft()
        print("Shutdown audio capture and pyaudio", flush=True)
        audio_capture.terminate()
        print("Close OSC server", flush=True)
        osc.close()
        print("Close DMX port", flush=True)
        dmx.close()

        sys.exit(0)
