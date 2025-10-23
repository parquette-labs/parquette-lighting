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

    yp = YRXY200Spot(dmx, 21)
    yp.dimming(0)
    yp.shutter(False)
    yp.color(YRXY200Spot.YRXY200Color.WHITE)
    yp.pattern(YRXY200Spot.YRXY200Pattern.CIRCULAR_WHITE)
    yp.prisim(False)
    yp.colorful(YRXY200Spot.YRXY200Colorful.COLORFUL_OPEN)
    yp.self_propelled(YRXY200Spot.YRXY200SelfPropelled.NONE)
    yp.light_strip_scene(YRXY200Spot.YRXY200RingScene.OFF)
    yp.scene_speed(0)
    yp.x(0)
    yp.y(127)

    sp = YUER150Spot(dmx, 36)
    sp.x(0)
    sp.y(127)
    sp.dimming(0)
    sp.strobe(False)
    sp.color(YUER150Spot.YUER150Color.WHITE)
    sp.pattern(YUER150Spot.YUER150Pattern.CIRCULAR_WHITE)
    sp.prisim(False)
    sp.self_propelled(YUER150Spot.YUER150SelfPropelled.NONE)

    sp = YUER150Spot(dmx, 48)
    sp.x(0)
    sp.y(127)
    sp.dimming(0)
    sp.strobe(False)
    sp.color(YUER150Spot.YUER150Color.WHITE)
    sp.pattern(YUER150Spot.YUER150Pattern.CIRCULAR_WHITE)
    sp.prisim(False)
    sp.self_propelled(YUER150Spot.YUER150SelfPropelled.NONE)

    w = RGBLight(dmx, 60)
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

    exposed_params: Dict[str, List[OSCParam]] = {
        "fft": [],
        "reds": [],
        "plants": [],
        "washes": [],
        "spots": [],
        "non-saved": [],
        "booth": [],
    }

    exposed_params["fft"] = [
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

    presets = PresetManager(osc, exposed_params, presets_file, debug)

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
