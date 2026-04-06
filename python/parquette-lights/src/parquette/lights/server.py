from typing import List, Dict

import sys
import time

import click

from .fixtures import RGBWLight, RGBLight, YRXY200Spot, Spot

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
@click.option(
    "--local-ip",
    default="127.0.0.1",
    type=str,
    help="The local IP address to bind to, typically you should use 0.0.0.0 to have it be accessible on the LAN, default is 127.0.0.1",
)
@click.option(
    "--local-port",
    default=5005,
    type=int,
    help="The local port to listen for OSC commands on, default is 5005",
)
@click.option(
    "--target-ip",
    default="127.0.0.1",
    type=str,
    help="IP address of the open stage control instance, default is 127.0.0.1",
)
@click.option(
    "--target-port",
    default=5006,
    type=int,
    help="The port the open stage control instance is listening for OSC on",
)
@click.option(
    "--art-net-ip",
    default="192.168.88.111",
    type=str,
    help="The IP address for artnet node / device to send to",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Print debut information excluding OSC traffic monitoring",
)
@click.option(
    "--debug-osc-in", is_flag=True, default=False, help="Print inbound OSC messages"
)
@click.option(
    "--debug-osc-out", is_flag=True, default=False, help="Print outbound OSC messages"
)
@click.option(
    "--boot-art-net",
    is_flag=True,
    default=False,
    help="Automatically launch the art-net connection on boot",
)
@click.option(
    "--art-net-auto",
    is_flag=True,
    default=False,
    help="Enable auto persisting data to the art net at 30hz, likely not needed",
)
@click.option(
    "--enable-save-clear",
    is_flag=True,
    default=False,
    help="Allow saving and clearing presets on boot",
)
@click.option(
    "--entec-auto",
    default=None,
    type=str,
    help="Auto connect to a given entec port on boot",
)  # /dev/tty.usbserial-EN264168
@click.option(
    "--presets-file",
    default="params.pickle",
    type=str,
    help="File to store and load presets from",
)
@click.option(
    "--audio-window",
    default=10.0,
    type=float,
    help="Audio tracking audio window length in seconds (used for BPM)",
)
@click.option(
    "--rms-window",
    default=0.5,
    type=float,
    help="Window length in seconds used for RMS energy gating of BPM",
)
# pylint: disable-next=too-many-positional-arguments
def run(
    local_ip: str,
    local_port: int,
    target_ip: str,
    target_port: int,
    art_net_ip: str,
    debug: bool,
    debug_osc_in: bool,
    debug_osc_out: bool,
    boot_art_net: bool,
    art_net_auto: bool,
    enable_save_clear: bool,
    entec_auto: str,
    presets_file: str,
    audio_window: float,
    rms_window: float,
) -> None:
    print("Setup", flush=True)

    osc = OSCManager()
    osc.set_target(target_ip, target_port)
    osc.set_local(local_ip, local_port)
    osc.set_debug(debug_osc_in, debug_osc_out)
    dmx = DMXManager(osc, art_net_ip)
    dmx.use_art_net = boot_art_net
    dmx.art_net_auto_send(art_net_auto)
    if not entec_auto is None:
        dmx.setup_dmx(entec_auto)

    front_spot = YRXY200Spot(dmx, addr=21)
    front_spot.dimming(255)
    front_spot.strobe(False)
    # front_spot.shutter(False)
    front_spot.color(0)
    front_spot.no_pattern()
    front_spot.prisim(False)
    front_spot.colorful(False)
    front_spot.self_propelled(YRXY200Spot.YRXY200SelfPropelled.NONE)
    front_spot.light_strip_scene(YRXY200Spot.YRXY200RingScene.OFF)
    front_spot.scene_speed(0)
    front_spot.x(0)
    front_spot.y(0)

    back_spot = YRXY200Spot(dmx, addr=200)
    back_spot.dimming(255)
    back_spot.strobe(False)
    # back_spot.shutter(False)
    back_spot.color(0)
    back_spot.no_pattern()
    back_spot.prisim(False)
    back_spot.colorful(False)
    back_spot.self_propelled(YRXY200Spot.YRXY200SelfPropelled.NONE)
    back_spot.light_strip_scene(YRXY200Spot.YRXY200RingScene.OFF)
    back_spot.scene_speed(0)
    back_spot.x(0)
    back_spot.y(0)

    spotlights: List[Spot] = [front_spot, back_spot]

    washfl = RGBLight(dmx, 104)
    washfl.rgb(0, 0, 0)

    washfr = RGBLight(dmx, 107)
    washfr.rgb(0, 0, 0)

    washml = RGBLight(dmx, 110)
    washml.rgb(0, 0, 0)

    washmr = RGBLight(dmx, 113)
    washmr.rgb(0, 0, 0)

    washbl = RGBLight(dmx, 120)
    washbl.rgb(0, 0, 0)

    washbr = RGBLight(dmx, 123)
    washbr.rgb(0, 0, 0)

    washceilf = RGBWLight(dmx, 100)
    washceilf.rgbw(0, 0, 0, 0)

    washceilr = RGBWLight(dmx, 116)
    washceilr.rgbw(0, 0, 0, 0)

    washes = [washfl, washfr, washml, washmr, washbl, washbr, washceilf, washceilr]

    audio_capture = AudioCapture(osc, audio_window_secs=audio_window)
    fft_manager = FFTManager(
        osc,
        audio_capture,
        energy_threshold=100.0,
        confidence_threshold=0.5,
        tempo_alpha=0.25,
        rms_window_secs=rms_window,
    )

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
    wave4 = WaveGenerator(
        name="sin_wash",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.SIN,
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

    impulse_eye = ImpulseGenerator(
        name="impulse_eye",
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
        wave4,
        sq1,
        sq2,
        sq3,
        impulse,
        impulse_eye,
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
        "washes_color": [
            OSCParam(
                osc,
                "/wash_r",
                lambda: washceilf.r_target,
                lambda _, args: OSCParam.obj_param_setter(
                    args,
                    "r_target",
                    [
                        washfl,
                        washfr,
                        washml,
                        washmr,
                        washbl,
                        washbr,
                        washceilf,
                        washceilr,
                    ],
                ),
            ),
            OSCParam(
                osc,
                "/wash_g",
                lambda: washceilf.g_target,
                lambda _, args: OSCParam.obj_param_setter(
                    args,
                    "g_target",
                    [
                        washfl,
                        washfr,
                        washml,
                        washmr,
                        washbl,
                        washbr,
                        washceilf,
                        washceilr,
                    ],
                ),
            ),
            OSCParam(
                osc,
                "/wash_b",
                lambda: washceilf.b_target,
                lambda _, args: OSCParam.obj_param_setter(
                    args,
                    "b_target",
                    [
                        washfl,
                        washfr,
                        washml,
                        washmr,
                        washbl,
                        washbr,
                        washceilf,
                        washceilr,
                    ],
                ),
            ),
            OSCParam(
                osc,
                "/wash_w",
                lambda: washceilf.w_target,
                lambda _, args: OSCParam.obj_param_setter(
                    args,
                    "w_target",
                    [
                        washceilf,
                        washceilr,
                    ],
                ),
            ),
        ],
        "washes": [
            OSCParam(
                osc,
                "/amp_wash",
                lambda: wave4.amp,
                lambda _, args: OSCParam.obj_param_setter(args, "amp", [wave4]),
            ),
            OSCParam(
                osc,
                "/period_wash",
                lambda: wave4.period,
                lambda _, args: OSCParam.obj_param_setter(args, "period", [wave4]),
            ),
            OSCParam(
                osc,
                "/stutter_period_wash",
                lambda: mixer.stutter_period_wash,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "stutter_period_wash", [mixer]
                ),
            ),
            OSCParam(
                osc,
                "/wash_mode_switch",
                lambda: mixer.wash_mode,
                lambda _, args: OSCParam.obj_param_setter(args, "wash_mode", [mixer]),
            ),
            SignalPatchParam(
                osc,
                "/signal_patchbay/washes",
                [
                    "wash_1",
                    "wash_2",
                    "wash_3",
                    "wash_4",
                    "wash_5",
                    "wash_6",
                    "wash_7",
                    "wash_8",
                ],
                mixer,
            ),
        ],
        "spots_light": [
            SignalPatchParam(
                osc,
                "/signal_patchbay/spots_lights",
                ["tung_spot", "spot_1", "spot_2"],
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
            OSCParam(
                osc,
                "/bpm_energy_threshold",
                lambda: fft_manager.energy_threshold,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "energy_threshold", [fft_manager]
                ),
            ),
            OSCParam(
                osc,
                "/bpm_confidence_threshold",
                lambda: fft_manager.confidence_threshold,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "confidence_threshold", [fft_manager]
                ),
            ),
            OSCParam(
                osc,
                "/bpm_tempo_alpha",
                lambda: fft_manager.tempo_alpha,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "tempo_alpha", [fft_manager]
                ),
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
            OSCParam(
                osc,
                "/impulse_amp_eye",
                lambda: impulse_eye.amp,
                lambda _, args: OSCParam.obj_param_setter(args, "amp", [impulse_eye]),
            ),
            OSCParam(
                osc,
                "/impulse_period_eye",
                lambda: impulse_eye.period,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "period", [impulse_eye]
                ),
            ),
            OSCParam(
                osc,
                "/impulse_duty_eye",
                lambda: impulse_eye.duty,
                lambda _, args: OSCParam.obj_param_setter(args, "duty", [impulse_eye]),
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

    def fix_xy_wedge(fixture, args, fine=False):
        if fine:
            if len(args) == 1:
                fixture.xy_fine(args[0][0], args[0][1])
            else:
                fixture.xy_fine(args[0], args[1])
        else:
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
                lambda _, *args, fixture=fixture: fix_xy_wedge(fixture, args, False),
            )
        )

        exposed_params["spots_position"].append(
            OSCParam(
                osc,
                "/spot_joystick_fine_{}".format(i + 1),
                lambda fixture=fixture: [fixture._x, fixture._y],
                lambda _, *args, fixture=fixture: fix_xy_wedge(fixture, args, True),
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
    osc.dispatcher.map(
        "/enable_save", lambda _, args: presets.set_enable_save_clear(args)
    )

    def all_black():
        presets.all_black()
        mixer.setChannelLevel("sodium", 0)

    # def restore_lights():
    #     presets.restore_lights()
    #     mixer.setChannelLevel("sodium", 0)

    def house_lights():
        presets.house_lights()

        mixer.reds_master = 1
        mixer.spots_master = 0
        mixer.washes_master = 1
        mixer.booth_master = 1
        mixer.plants_master = 1

        mixer.setChannelLevel("sodium", 255)

    def class_lights():
        presets.select_all("Class")

        mixer.reds_master = 0.8
        mixer.spots_master = 0.3
        mixer.washes_master = 0.25
        mixer.booth_master = 0
        mixer.plants_master = 0.5

        mixer.setChannelLevel("sodium", 0)

    osc.dispatcher.map("/all_black", lambda addr, args: all_black())
    osc.dispatcher.map("/house_lights", lambda addr, args: house_lights())
    osc.dispatcher.map("/class", lambda addr, args: class_lights())
    osc.dispatcher.map("/reload", lambda addr, args: presets.sync())
    osc.dispatcher.map(
        "/impulse_punch",
        lambda addr, *args: impulse.punch(),
    )

    def reset_spots(reset: bool) -> None:
        for spot in spotlights:
            spot.reset(reset)

    osc.dispatcher.map("/reset_spots", lambda addr, args: reset_spots(args))

    osc.dispatcher.map(
        "/eye_punch",
        lambda addr, *args: impulse_eye.punch(),
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
