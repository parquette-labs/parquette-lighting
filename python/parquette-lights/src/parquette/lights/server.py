# pylint: disable=too-many-lines
from typing import List, Dict

import sys
import time

import click

from .fixtures import RGBWLight, RGBLight, YRXY200Spot, Spot
from .fixtures.hazers import RadianceHazer

from .generators import (
    FFTGenerator,
    WaveGenerator,
    ImpulseGenerator,
    BPMGenerator,
    Mixer,
    SignalPatchParam,
)

from .audio_analysis import FFTManager, AudioCapture

from .osc import OSCManager, OSCParam
from .dmx import DMXManager
from .preset_manager import PresetManager
from .util.client_tracker import ClientTracker


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
    default=5.0,
    type=float,
    help="Audio tracking audio window length in seconds (used for BPM)",
)
@click.option(
    "--rms-window",
    default=0.5,
    type=float,
    help="Window length in seconds used for RMS energy gating of BPM",
)
@click.option(
    "--spot-color-fade",
    default=-1.0,
    type=float,
    help="Seconds for moving-head color change fade out/in (negative disables)",
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
    spot_color_fade: float,
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
    front_spot.pan(0)
    front_spot.tilt(0)

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
    back_spot.pan(0)
    back_spot.tilt(0)

    spotlights: List[Spot] = [front_spot, back_spot]

    for spot in spotlights:
        spot.color_swap_fade_time = spot_color_fade

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

    hazer = RadianceHazer(dmx, addr=250)
    hazer.output = 0
    hazer.fan = 0

    audio_capture = AudioCapture(osc, audio_window_secs=audio_window)
    audio_capture.dmx = dmx
    fft_manager = FFTManager(
        osc,
        audio_capture,
        dmx,
        energy_threshold=100.0,
        tempo_alpha=0.25,
        rms_window_secs=rms_window,
        debug=debug,
        onset_envelope_floor=2.0,
        min_business=0.5,
        min_regularity=0.4,
    )

    initialAmp: float = 200
    initialPeriod: int = 3500

    sin_reds = WaveGenerator(
        name="sin_red",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.SIN,
    )
    sin_plants = WaveGenerator(
        name="sin_plants",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.SIN,
    )
    sin_booth = WaveGenerator(
        name="sin_booth",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.SIN,
    )
    sin_wash = WaveGenerator(
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
        duty=0.5,
    )

    sq2 = WaveGenerator(
        name="sq_2",
        amp=initialAmp,
        period=initialPeriod,
        phase=476,
        offset=0,
        shape=WaveGenerator.Shape.SQUARE,
        duty=0.5,
    )

    sq3 = WaveGenerator(
        name="sq_3",
        amp=initialAmp,
        period=initialPeriod,
        phase=335,
        offset=0,
        shape=WaveGenerator.Shape.SQUARE,
        duty=0.5,
    )

    impulse = ImpulseGenerator(
        name="impulse",
        amp=255,
        offset=0,
        duty=100,
    )

    fft1 = FFTGenerator(name="fft_1", amp=1, offset=0, subdivisions=1, memory_length=20)
    fft2 = FFTGenerator(name="fft_2", amp=1, offset=0, subdivisions=1, memory_length=20)

    bpm_red = BPMGenerator(name="bpm_red", amp=255, offset=0, duty=100)
    bpm_wash = BPMGenerator(name="bpm_wash", amp=255, offset=0, duty=100)

    generators = [
        sin_reds,
        sin_plants,
        sin_booth,
        sin_wash,
        sq1,
        sq2,
        sq3,
        impulse,
        fft1,
        fft2,
        bpm_red,
        bpm_wash,
    ]

    fft_manager.downstream = [fft1, fft2]
    # FFTManager fans audio-driven tempo updates out to all bpms; per-gen
    # user knobs (duty/amp/mult/manual_offset/lpf_alpha) stay independent.
    fft_manager.bpms = [bpm_red, bpm_wash]

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

    _all_washes = [washfl, washfr, washml, washmr, washbl, washbr, washceilf, washceilr]

    def _dispatch_wash_color(_addr, *args):
        # Reuses the existing set_dimming_target on each fixture, which
        # accepts None for any channel to leave it unchanged — `w` is
        # omitted so the white target is preserved.
        #
        # Handles two invocation shapes:
        #   pythonosc dispatcher → (addr, r, g, b) so args == (r, g, b)
        #   PresetManager.load   → (addr, [r, g, b]) so args == ([r,g,b],)
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            rgb = args[0]
        else:
            rgb = args
        if len(rgb) < 3:
            return
        for fixture in _all_washes:
            fixture.set_dimming_target(r=rgb[0], g=rgb[1], b=rgb[2])

    exposed_params: Dict[str, List[OSCParam]] = {
        "fft": [],
        "reds": [
            SignalPatchParam(
                osc,
                "/signal_patchbay/reds",
                ["chan_1", "chan_2", "chan_3", "chan_4", "chan_5", "viz"],
                mixer,
            )
        ],
        "plants": [
            SignalPatchParam(
                osc,
                "/signal_patchbay/plants",
                ["ceil_1", "ceil_2", "ceil_3", "viz"],
                mixer,
            )
        ],
        "booth": [
            SignalPatchParam(
                osc, "/signal_patchbay/booth", ["under_1", "under_2", "viz"], mixer
            )
        ],
        "strobes": [],
        "washes_color": [
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
            # Combined RGB target for the wash color picker. Stored in
            # presets so the picker round-trips through save/load and sync.
            # Reuses set_dimming_target on each fixture (which accepts None
            # to leave a channel unchanged) — `w` is omitted so the white
            # target stays put.
            OSCParam(
                osc,
                "/wash_color",
                lambda: [
                    washceilf.r_target,
                    washceilf.g_target,
                    washceilf.b_target,
                ],
                _dispatch_wash_color,
            ),
        ],
        "washes": [
            OSCParam(
                osc,
                "/amp_wash",
                lambda: sin_wash.amp,
                lambda _, args: OSCParam.obj_param_setter(args, "amp", [sin_wash]),
            ),
            OSCParam(
                osc,
                "/period_wash",
                lambda: sin_wash.period,
                lambda _, args: OSCParam.obj_param_setter(args, "period", [sin_wash]),
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
                    "viz",
                ],
                mixer,
            ),
        ],
        "spots_light": [
            SignalPatchParam(
                osc,
                "/signal_patchbay/spots_lights",
                ["tung_spot", "spot_1", "spot_2", "viz"],
                mixer,
            )
        ],
        "spots_position": [],
        "audio": [],
        "hazer": [
            OSCParam(
                osc,
                "/hazer_output",
                lambda: hazer.output,
                lambda _, args: OSCParam.obj_param_setter(args, "output", [hazer]),
            ),
            OSCParam(
                osc,
                "/hazer_fan",
                lambda: hazer.fan,
                lambda _, args: OSCParam.obj_param_setter(args, "fan", [hazer]),
            ),
        ],
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
                "/fft_lpf_alpha",
                lambda: fft1.lpf_alpha,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "lpf_alpha", [fft1, fft2]
                ),
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
                "/bpm_energy_threshold",
                lambda: fft_manager.energy_threshold,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "energy_threshold", [fft_manager]
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
            OSCParam(
                osc,
                "/onset_envelope_floor",
                lambda: fft_manager.onset_envelope_floor,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "onset_envelope_floor", [fft_manager]
                ),
            ),
            OSCParam(
                osc,
                "/bpm_business_min",
                lambda: fft_manager.min_business,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "min_business", [fft_manager]
                ),
            ),
            OSCParam(
                osc,
                "/bpm_regularity_min",
                lambda: fft_manager.min_regularity,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "min_regularity", [fft_manager]
                ),
            ),
        ]
    )

    exposed_params["non-saved"].extend(
        [
            OSCParam(
                osc,
                "/dmx_passthrough",
                lambda: dmx.passthrough,
                lambda _, args: set_dmx_passthrough(args),
            ),
        ]
    )

    def make_snap_handler(gens, period_addr, bpm_gen):
        def handler():
            if bpm_gen.bpm > 0 and bpm_gen.bpm_mult > 0:
                period = bpm_gen.current_period()
                for gen in gens:
                    gen.period = period
                osc.send_osc(period_addr, period)

        return handler

    exposed_params["reds"].extend(
        [
            OSCParam(
                osc,
                "/sin_red_amp",
                lambda: sin_reds.amp,
                lambda _, args: OSCParam.obj_param_setter(args, "amp", [sin_reds]),
            ),
            OSCParam(
                osc,
                "/sin_red_period",
                lambda: sin_reds.period,
                lambda _, args: OSCParam.obj_param_setter(args, "period", [sin_reds]),
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
                "/bpm_red_mult",
                lambda: bpm_red.bpm_mult,
                lambda _, args: OSCParam.obj_param_setter(args, "bpm_mult", [bpm_red]),
            ),
            OSCParam(
                osc,
                "/bpm_red_duty",
                lambda: bpm_red.duty,
                lambda _, args: OSCParam.obj_param_setter(args, "duty", [bpm_red]),
            ),
            OSCParam(
                osc,
                "/bpm_red_lpf_alpha",
                lambda: bpm_red.lpf_alpha,
                lambda _, args: OSCParam.obj_param_setter(args, "lpf_alpha", [bpm_red]),
            ),
            OSCParam(
                osc,
                "/bpm_red_amp",
                lambda: bpm_red.amp,
                lambda _, args: OSCParam.obj_param_setter(args, "amp", [bpm_red]),
            ),
            OSCParam(
                osc,
                "/bpm_red_manual_offset",
                lambda: bpm_red.manual_offset,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "manual_offset", [bpm_red]
                ),
            ),
        ]
    )

    exposed_params["plants"].extend(
        [
            OSCParam(
                osc,
                "/sin_plants_amp",
                lambda: sin_plants.amp,
                lambda _, args: OSCParam.obj_param_setter(args, "amp", [sin_plants]),
            ),
            OSCParam(
                osc,
                "/sin_plants_period",
                lambda: sin_plants.period,
                lambda _, args: OSCParam.obj_param_setter(args, "period", [sin_plants]),
            ),
            OSCParam(
                osc,
                "/sq_amp",
                lambda: sq1.amp,
                lambda _, args: OSCParam.obj_param_setter(args, "amp", [sq1, sq2, sq3]),
            ),
            OSCParam(
                osc,
                "/sq_period",
                lambda: sq1.period,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "period", [sq1, sq2, sq3]
                ),
            ),
        ]
    )

    exposed_params["booth"].extend(
        [
            OSCParam(
                osc,
                "/sin_booth_amp",
                lambda: sin_booth.amp,
                lambda _, args: OSCParam.obj_param_setter(args, "amp", [sin_booth]),
            ),
            OSCParam(
                osc,
                "/sin_booth_period",
                lambda: sin_booth.period,
                lambda _, args: OSCParam.obj_param_setter(args, "period", [sin_booth]),
            ),
        ]
    )

    exposed_params["washes"].extend(
        [
            OSCParam(
                osc,
                "/bpm_wash_amp",
                lambda: bpm_wash.amp,
                lambda _, args: OSCParam.obj_param_setter(args, "amp", [bpm_wash]),
            ),
            OSCParam(
                osc,
                "/bpm_wash_duty",
                lambda: bpm_wash.duty,
                lambda _, args: OSCParam.obj_param_setter(args, "duty", [bpm_wash]),
            ),
            OSCParam(
                osc,
                "/bpm_wash_lpf_alpha",
                lambda: bpm_wash.lpf_alpha,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "lpf_alpha", [bpm_wash]
                ),
            ),
            OSCParam(
                osc,
                "/bpm_wash_mult",
                lambda: bpm_wash.bpm_mult,
                lambda _, args: OSCParam.obj_param_setter(args, "bpm_mult", [bpm_wash]),
            ),
            OSCParam(
                osc,
                "/bpm_wash_manual_offset",
                lambda: bpm_wash.manual_offset,
                lambda _, args: OSCParam.obj_param_setter(
                    args, "manual_offset", [bpm_wash]
                ),
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

    def fix_pantilt_wedge(fixture, args, fine=False):
        # needed because of weirdness with arduino osc
        if fine:
            if len(args) == 1:
                fixture.pantilt_fine(args[0][0], args[0][1])
            else:
                fixture.pantilt_fine(args[0], args[1])
        else:
            if len(args) == 1:
                fixture.pantilt(args[0][0], args[0][1])
            else:
                fixture.pantilt(args[0], args[1])

    # pylint: disable=protected-access
    for i, fixture in enumerate(spotlights):

        def _echo_position(fixture=fixture, i=i):
            # After any position change (from any of the three handles),
            # push the canonical pan/tilt and the derived xy back out so all
            # UI widgets — and all connected clients — track the new aim.
            # Coarse joystick gets MSBs, fine joystick gets LSBs, xy gets
            # the unit-sphere projection from get_aim().
            osc.send_osc(
                "/spot_joystick_{}".format(i + 1),
                [fixture._pan, fixture._tilt],
            )
            osc.send_osc(
                "/spot_joystick_fine_{}".format(i + 1),
                [fixture._pan_fine, fixture._tilt_fine],
            )
            osc.send_osc(
                "/spot_joystick_xy_{}".format(i + 1),
                list(fixture.get_aim()[0:2]),
            )

        def _make_coarse_dispatch(fixture, i):
            def _dispatch(_addr, *args):
                fix_pantilt_wedge(fixture, args, False)
                _echo_position(fixture, i)

            return _dispatch

        def _make_fine_dispatch(fixture, i):
            def _dispatch(_addr, *args):
                fix_pantilt_wedge(fixture, args, True)
                _echo_position(fixture, i)

            return _dispatch

        def _make_xy_dispatch(fixture, i):
            def _dispatch(_addr, *args):
                # pythonosc → (addr, x, y) → args == (x, y)
                # PresetManager.load → (addr, [x, y]) → args == ([x, y],)
                if len(args) == 1 and isinstance(args[0], (list, tuple)):
                    xy = args[0]
                else:
                    xy = args
                if len(xy) < 2:
                    return
                fixture.aim_at(xy[0], xy[1], 10)
                _echo_position(fixture, i)

            return _dispatch

        exposed_params["spots_position"].append(
            OSCParam(
                osc,
                "/spot_joystick_{}".format(i + 1),
                lambda fixture=fixture: [fixture._pan, fixture._tilt],
                _make_coarse_dispatch(fixture, i),
            )
        )

        exposed_params["spots_position"].append(
            OSCParam(
                osc,
                "/spot_joystick_fine_{}".format(i + 1),
                lambda fixture=fixture: [fixture._pan_fine, fixture._tilt_fine],
                _make_fine_dispatch(fixture, i),
            )
        )

        # xy lives in `non-saved` so it's never written into preset pickles
        # (pan/tilt is the only canonical position state). It's still
        # iterated by presets.sync(), so the UI joystick refreshes on
        # /reload and after select_all via the value_lambda below.
        exposed_params["non-saved"].append(
            OSCParam(
                osc,
                "/spot_joystick_xy_{}".format(i + 1),
                lambda fixture=fixture: list(fixture.get_aim()[0:2]),
                _make_xy_dispatch(fixture, i),
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
        mixer.setChannelLevel("sodium", 0)

        presets.select_all("Off")

    def set_dmx_passthrough(value) -> None:
        if isinstance(value, (list, tuple)):
            value = value[0] if value else 0
        enabled = bool(value)
        dmx.passthrough = enabled
        if not enabled:
            # Safety: ensure capture/FFT threads are running after we leave passthrough.
            if audio_capture.audio_thread is None or not audio_capture.audio_running:
                audio_capture.start_audio()
            if fft_manager.fft_thread is None or not fft_manager.fft_running:
                fft_manager.start_fft()

    def house_lights():
        if dmx.passthrough:
            set_dmx_passthrough(False)

        mixer.reds_master = 1
        mixer.spots_master = 0
        mixer.washes_master = 1
        mixer.booth_master = 1
        mixer.plants_master = 1

        mixer.setChannelLevel("sodium", 255)

        presets.select_all("Static")

    def class_lights():
        mixer.reds_master = 0.8
        mixer.spots_master = 0.3
        mixer.washes_master = 0.25
        mixer.booth_master = 0
        mixer.plants_master = 0.5

        mixer.setChannelLevel("sodium", 0)

        if dmx.passthrough:
            set_dmx_passthrough(False)

        presets.select_all("Class")

    osc.dispatcher.map(
        "/set_fft_viz", lambda addr, *args: mixer.set_fft_viz(bool(args[0]))
    )
    osc.dispatcher.map(
        "/set_viz_output", lambda addr, *args: mixer.set_viz_output(bool(args[0]))
    )
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

    # Snap-to-BPM action buttons. These are momentary actions, not state, so
    # they're registered directly on the dispatcher (not as OSCParams) and
    # therefore are never written into preset pickles. Previously they lived
    # as OSCParams inside saved categories, which meant preset save captured
    # `/snap_*_to_bpm = 0` and preset load re-fired the snap, clobbering the
    # restored period of the corresponding sine generator.
    osc.dispatcher.map(
        "/snap_sin_red_to_bpm",
        lambda addr, *args: make_snap_handler([sin_reds], "/sin_red_period", bpm_red)(),
    )
    osc.dispatcher.map(
        "/snap_sin_plants_to_bpm",
        lambda addr, *args: make_snap_handler(
            [sin_plants], "/sin_plants_period", bpm_red
        )(),
    )
    osc.dispatcher.map(
        "/snap_sq_to_bpm",
        lambda addr, *args: make_snap_handler([sq1, sq2, sq3], "/sq_period", bpm_red)(),
    )
    osc.dispatcher.map(
        "/snap_sin_booth_to_bpm",
        lambda addr, *args: make_snap_handler(
            [sin_booth], "/sin_booth_period", bpm_red
        )(),
    )
    osc.dispatcher.map(
        "/snap_sin_wash_to_bpm",
        lambda addr, *args: make_snap_handler([sin_wash], "/period_wash", bpm_wash)(),
    )

    client_tracker = ClientTracker(osc)
    client_tracker.start()

    print("Start OSC server", flush=True)
    osc.serve(threaded=True)

    print("Sync front end", flush=True)
    presets.sync()

    print("Start compute loop", flush=True)
    try:
        while True:
            if dmx.passthrough:
                dmx.submit_passthrough()
            else:
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
