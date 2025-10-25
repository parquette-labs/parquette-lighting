from typing import List, Dict

import sys
import time

import click

from .fixtures import YRXY200Spot, YUER150Spot, RGBLight

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

    overhead_spot = YRXY200Spot(dmx, 21)
    overhead_spot.dimming(0)
    overhead_spot.strobe(False)
    overhead_spot.color(7)
    overhead_spot.no_pattern()
    overhead_spot.prisim(False)
    overhead_spot.colorful(False)
    overhead_spot.self_propelled(YRXY200Spot.YRXY200SelfPropelled.NONE)
    overhead_spot.light_strip_scene(YRXY200Spot.YRXY200RingScene.OFF)
    overhead_spot.scene_speed(0)
    overhead_spot.x(0)
    overhead_spot.y(127)

    sidespot_2 = YUER150Spot(dmx, 36)
    sidespot_2.x(0)
    sidespot_2.y(127)
    sidespot_2.dimming(0)
    sidespot_2.strobe(False)
    sidespot_2.color(1)
    sidespot_2.no_pattern()
    sidespot_2.prisim(False)
    sidespot_2.self_propelled(YUER150Spot.YUER150SelfPropelled.NONE)

    sidespot_1 = YUER150Spot(dmx, 48)
    sidespot_1.x(0)
    sidespot_1.y(127)
    sidespot_1.dimming(0)
    sidespot_1.strobe(False)
    sidespot_1.color(1)
    sidespot_1.no_pattern()
    sidespot_1.prisim(False)
    sidespot_1.self_propelled(YUER150Spot.YUER150SelfPropelled.NONE)

    spotlights = [overhead_spot, sidespot_1, sidespot_2]

    wash = RGBLight(dmx, 60)
    wash.rgb(0, 0, 0)

    washes = [wash]

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
        "reds": [],
        "plants": [],
        "booth": [],
        "spots_position": [],
        "washes": [],
        "spots_light": [],
        "non-saved": [],
    }

    exposed_params["audio"] = [
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
    exposed_params["reds"] = [
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
    ]
    exposed_params["strobes"] = [
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
    exposed_params["non-saved"] = [
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
            lambda _, args: OSCParam.obj_param_setter(args, "plants_master", [mixer]),
        ),
        OSCParam(
            osc,
            "/booth_master",
            lambda: mixer.booth_master,
            lambda _, args: OSCParam.obj_param_setter(args, "booth_master", [mixer]),
        ),
    ]

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

    for i, fixture in enumerate(spotlights):
        exposed_params["spots_position"].append(
            OSCParam(
                osc,
                "/spot_joystick_{}".format(i + 1),
                lambda fixture=fixture: [fixture.x_val[0], fixture.y_val[0]],
                lambda _, *args, fixture=fixture: fixture.xy(args[0], args[1]),
            )
        )

        exposed_params["spots_light"].append(
            OSCParam(
                osc,
                "/spot_dimming_{}".format(i + 1),
                lambda fixture=fixture: fixture.dimming_val,
                lambda _, args, fixture=fixture: fixture.dimming(args),
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
    presets = PresetManager(osc, exposed_params, presets_file, debug)

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
