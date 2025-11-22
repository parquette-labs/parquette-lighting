from typing import List, Dict

import sys
import time

import click

from .fixtures import RGBWLight, YRXY200Spot, Spot

from .generators import (
    FFTGenerator,
    WaveGenerator,
    ImpulseGenerator,
    NoiseGenerator,
    BPMGenerator,
    Mixer,
    SignalPatchParam,
)

from .audio_analysis import FFTManager, AudioCapture

from .osc import OSCManager, OSCParam
from .dmx import DMXManager
from .preset_manager import PresetManager


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
@click.option("--enable-save-clear", is_flag=True, default=False)
@click.option(
    "--entec-auto", default=None, type=str, help="entec port"
)  # /dev/tty.usbserial-EN264168
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
    enable_save_clear: bool,
    entec_auto: str,
    presets_file: str,
) -> None:
    print("Setup", flush=True)

    osc = OSCManager()
    osc.set_target(target_ip, target_port)
    osc.set_local(local_ip, local_port)
    osc.set_debug(debug)
    dmx = DMXManager(osc, art_net_ip)
    dmx.use_art_net = boot_art_net
    dmx.art_net_auto_send(art_net_auto)
    if not entec_auto is None:
        dmx.setup_dmx(entec_auto)

    overhead_spot = YRXY200Spot(dmx, addr=21)
    overhead_spot.dimming(255)
    overhead_spot.strobe(False)
    # overhead_spot.shutter(False)
    overhead_spot.color(0)
    overhead_spot.no_pattern()
    overhead_spot.prisim(False)
    overhead_spot.colorful(False)
    overhead_spot.self_propelled(YRXY200Spot.YRXY200SelfPropelled.NONE)
    overhead_spot.light_strip_scene(YRXY200Spot.YRXY200RingScene.OFF)
    overhead_spot.scene_speed(0)
    overhead_spot.x(0)
    overhead_spot.y(0)

    sidespot_1 = YRXY200Spot(dmx, addr=36)
    sidespot_1.dimming(255)
    sidespot_1.strobe(False)
    # sidespot_1.shutter(False)
    sidespot_1.color(0)
    sidespot_1.no_pattern()
    sidespot_1.prisim(False)
    sidespot_1.colorful(False)
    sidespot_1.self_propelled(YRXY200Spot.YRXY200SelfPropelled.NONE)
    sidespot_1.light_strip_scene(YRXY200Spot.YRXY200RingScene.OFF)
    sidespot_1.scene_speed(0)
    sidespot_1.x(0)
    sidespot_1.y(0)

    sidespot_2 = YRXY200Spot(dmx, addr=51)
    sidespot_2.dimming(255)
    sidespot_2.strobe(False)
    # sidespot_2.shutter(False)
    sidespot_2.color(0)
    sidespot_2.no_pattern()
    sidespot_2.prisim(False)
    sidespot_2.colorful(False)
    sidespot_2.self_propelled(YRXY200Spot.YRXY200SelfPropelled.NONE)
    sidespot_2.light_strip_scene(YRXY200Spot.YRXY200RingScene.OFF)
    sidespot_2.scene_speed(0)
    sidespot_2.x(0)
    sidespot_2.y(0)

    spotlights: List[Spot] = [overhead_spot, sidespot_1, sidespot_2]

    wash1 = RGBWLight(dmx, 66)
    wash1.rgbw(0, 0, 0, 0)

    wash2 = RGBWLight(dmx, 70)
    wash2.rgbw(0, 0, 0, 0)

    washes = [wash1, wash2]

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
        spots=spotlights,
        washes=washes,
        history_len=666 * 6,
    )

    def fft_dispatch_wedge(fft, args):
        if len(args) == 1:
            fft.set_bounds(args[0][0], args[0][2])
        else:
            fft.set_bounds(args[0], args[2])

    exposed_params: Dict[str, List[OSCParam]] = {
        "fft": [],
        "reds": [
            SignalPatchParam(
                osc,
                "/signal_patchbay/reds",
                ["chan_1", "chan_2", "chan_3", "chan_4", "chan_5"],
                mixer,
            )
        ],
        "plants": [
            SignalPatchParam(
                osc, "/signal_patchbay/plants", ["ceil_1", "ceil_2", "ceil_3"], mixer
            )
        ],
        "booth": [
            SignalPatchParam(
                osc, "/signal_patchbay/booth", ["under_1", "under_2"], mixer
            )
        ],
        "strobes": [],
        "washes": [
            SignalPatchParam(
                osc, "/signal_patchbay/washes", ["wash_1", "wash_2"], mixer
            )
        ],
        "spots_light": [
            SignalPatchParam(
                osc,
                "/signal_patchbay/spots_lights",
                ["tung_spot", "spot_1", "spot_2", "spot_3"],
                mixer,
            )
        ],
        "spots_position": [],
        "audio": [],
        "non-saved": [],
    }

    exposed_params["audio"].extend(
        [
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
            OSCParam(
                osc,
                "/manual_bpm_offset",
                lambda: bpm.manual_offset,
                lambda _, args: OSCParam.obj_param_setter(args, "manual_offset", [bpm]),
            ),
        ]
    )
    exposed_params["reds"].extend(
        [
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
                "/mode_switch",
                lambda: mixer.mode,
                lambda _, args: OSCParam.obj_param_setter(args, "mode", [mixer]),
            ),
            OSCParam(
                osc,
                "/stutter_period",
                lambda: mixer.stutter_period,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "stutter_period", [mixer]
                ),
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
        ]
    )

    exposed_params["strobes"].extend(
        [
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
        ]
    )
    exposed_params["non-saved"].extend(
        [
            OSCParam(
                osc,
                "/reds_master",
                lambda: mixer.reds_master,
                lambda _, args: OSCParam.obj_param_setter(args, "reds_master", [mixer]),
            ),
            OSCParam(
                osc,
                "/plants_master",
                lambda: mixer.plants_master,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "plants_master", [mixer]
                ),
            ),
            OSCParam(
                osc,
                "/booth_master",
                lambda: mixer.booth_master,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "booth_master", [mixer]
                ),
            ),
            OSCParam(
                osc,
                "/washes_master",
                lambda: mixer.washes_master,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "washes_master", [mixer]
                ),
            ),
            OSCParam(
                osc,
                "/spots_master",
                lambda: mixer.spots_master,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "spots_master", [mixer]
                ),
            ),
        ]
    )

    for category, chan_names in mixer.categorized_channel_names.items():
        for chan_name in chan_names:
            exposed_params[category].append(
                OSCParam(
                    osc,
                    "/chan_levels/{}".format(chan_name),
                    lambda chan=chan_name: mixer.getChannelLevel(chan),
                    lambda addr, args: mixer.setChannelLevel(addr.split("/")[2], args),
                )
            )

    def fix_xy_wedge(fixture, args):
        if len(args) == 1:
            fixture.xy(args[0][0], args[0][1])
        else:
            fixture.xy(args[0], args[1])

    for i, fixture in enumerate(spotlights):
        exposed_params["spots_position"].append(
            OSCParam(
                osc,
                "/spot_joystick_{}".format(i + 1),
                lambda fixture=fixture: [fixture._x, fixture._y],
                lambda _, *args, fixture=fixture: fix_xy_wedge(fixture, args),
            )
        )

        exposed_params["spots_light"].append(
            OSCParam(
                osc,
                "/spot_color_{}".format(i + 1),
                lambda fixture=fixture: fixture.color_index,
                lambda _, args, fixture=fixture: fixture.color(args),
            )
        )

        exposed_params["spots_light"].append(
            OSCParam(
                osc,
                "/spot_pattern_{}".format(i + 1),
                lambda fixture=fixture: fixture.pattern_index,
                lambda _, args, fixture=fixture: fixture.pattern(args),
            )
        )

        exposed_params["spots_light"].append(
            OSCParam(
                osc,
                "/spot_prisim_{}".format(i + 1),
                lambda fixture=fixture: fixture.prisim_enabled,
                lambda _, args, fixture=fixture: fixture.prisim(
                    args, fixture.prisim_rotation
                ),
            )
        )

        exposed_params["spots_light"].append(
            OSCParam(
                osc,
                "/spot_prisim_rotation_{}".format(i + 1),
                lambda fixture=fixture: fixture.prisim_rotation,
                lambda _, args, fixture=fixture: fixture.prisim(
                    fixture.prisim_enabled, args
                ),
            )
        )
    presets = PresetManager(
        osc,
        exposed_params,
        presets_file,
        enable_save_clear=enable_save_clear,
        debug=debug,
    )

    osc.dispatcher.map("/reload", lambda addr, args: presets.sync())

    def all_black():
        presets.select("reds", "Off")
        presets.select("plants", "Off")
        presets.select("booth", "Off")
        presets.select("washes", "Off")
        presets.select("spots_light", "Off")
        # mixer.reds_master = 0
        # mixer.spots_master = 0
        # mixer.washes_master = 0
        # mixer.booth_master = 0
        # mixer.plants_master = 0
        mixer.setChannelLevel("sodium", 0)

    def house_lights():
        presets.select("reds", "Static")
        presets.select("plants", "Static")
        presets.select("booth", "Static")
        presets.select("washes", "Static")
        presets.select("spots_light", "Off")
        mixer.reds_master = 1
        mixer.spots_master = 1
        mixer.washes_master = 1
        mixer.booth_master = 1
        mixer.plants_master = 1
        mixer.setChannelLevel("sodium", 255)

    osc.dispatcher.map("/all_black", lambda addr, args: all_black())
    osc.dispatcher.map("/house_lights", lambda addr, args: house_lights())
    osc.dispatcher.map("/reload", lambda addr, args: presets.sync())
    osc.dispatcher.map(
        "/impulse_punch",
        lambda addr, *args: impulse.punch(),
    )

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
