from typing import Any, List, Optional

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
)

from .audio_analysis import FFTManager, AudioCapture

from .osc import OSCManager
from .dmx import DMXManager
from .params import ParamDeps, build_exposed_params
from .preset_manager import PresetManager
from .util.client_tracker import ClientTracker
from .util.session_store import SessionStore


@click.command()
@click.option(
    "--local-ip",
    default="127.0.0.1",
    show_default=True,
    type=str,
    help="The local IP address to bind to. Use 0.0.0.0 to be accessible on the LAN.",
)
@click.option(
    "--local-port",
    default=5005,
    show_default=True,
    type=int,
    help="The local port to listen for OSC commands on.",
)
@click.option(
    "--target-ip",
    default="127.0.0.1",
    show_default=True,
    type=str,
    help="IP address of the open stage control instance.",
)
@click.option(
    "--target-port",
    default=5006,
    show_default=True,
    type=int,
    help="The port the open stage control instance is listening for OSC on.",
)
@click.option(
    "--art-net-ip",
    default="192.168.88.111",
    show_default=True,
    type=str,
    help="The IP address for art-net node / device to send to.",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    show_default=True,
    help="Print debug information (excluding OSC traffic monitoring).",
)
@click.option(
    "--debug-osc-in",
    is_flag=True,
    default=False,
    show_default=True,
    help="Print inbound OSC messages.",
)
@click.option(
    "--debug-osc-out",
    is_flag=True,
    default=False,
    show_default=True,
    help="Print outbound OSC messages.",
)
@click.option(
    "--debug-hazer",
    is_flag=True,
    default=False,
    show_default=True,
    help="Print the hazer's DMX channel state on every tick.",
)
@click.option(
    "--boot-art-net",
    is_flag=True,
    default=False,
    show_default=True,
    help="Automatically launch the art-net connection on boot.",
)
@click.option(
    "--art-net-auto",
    is_flag=True,
    default=False,
    show_default=True,
    help="Enable auto persisting data to the art-net at 30hz (likely not needed).",
)
@click.option(
    "--enable-save-clear",
    is_flag=True,
    default=False,
    show_default=True,
    help="Allow saving and clearing presets on boot.",
)
@click.option(
    "--entec-auto",
    default=None,
    show_default=True,
    type=str,
    help="Auto-connect to a given Enttec port on boot (e.g. /dev/tty.usbserial-EN264168).",
)
@click.option(
    "--presets-file",
    default="params.pickle",
    show_default=True,
    type=str,
    help="File to store and load presets from.",
)
@click.option(
    "--audio-window",
    default=5.0,
    show_default=True,
    type=float,
    help="Audio tracking window length in seconds (used for BPM).",
)
@click.option(
    "--rms-window",
    default=0.5,
    show_default=True,
    type=float,
    help="Window length in seconds used for RMS energy gating of BPM.",
)
@click.option(
    "--spot-color-fade",
    default=0.1,
    show_default=True,
    type=float,
    help="Seconds for moving-head color change fade out/in (negative disables).",
)
@click.option(
    "--spot-mechanical-time",
    default=0.45,
    show_default=True,
    type=float,
    help="Seconds to hold dark while the moving-head color wheel mechanically settles.",
)
@click.option(
    "--session-file",
    default="session.pickle",
    show_default=True,
    type=str,
    help="File to store and load session state (active presets, master faders) from.",
)
@click.option(
    "--audio-interface",
    default=None,
    show_default=True,
    type=str,
    help="Auto-connect to an audio input device by name (substring, case-insensitive) and start audio + FFT analysis on boot.",
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
    debug_hazer: bool,
    boot_art_net: bool,
    art_net_auto: bool,
    enable_save_clear: bool,
    entec_auto: str,
    presets_file: str,
    audio_window: float,
    rms_window: float,
    spot_color_fade: float,
    spot_mechanical_time: float,
    session_file: str,
    audio_interface: Optional[str],
) -> None:
    print("Setup", flush=True)

    osc = OSCManager()
    osc.set_target(target_ip, target_port)
    osc.set_local(local_ip, local_port)
    osc.set_debug(debug_osc_in, debug_osc_out)
    dmx = DMXManager(osc, art_net_ip)
    dmx.use_art_net = boot_art_net
    dmx.art_net_auto_send(art_net_auto)
    if entec_auto is not None:
        dmx.setup_dmx(entec_auto)

    front_spot = YRXY200Spot(name="spot_1", dmx=dmx, addr=21, category="spots_light")
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

    back_spot = YRXY200Spot(name="spot_2", dmx=dmx, addr=200, category="spots_light")
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
        spot.color_swap_mechanical_time = spot_mechanical_time

    washfl = RGBLight(name="wash_1", dmx=dmx, addr=104, category="washes")
    washfl.rgb(0, 0, 0)

    washfr = RGBLight(name="wash_2", dmx=dmx, addr=107, category="washes")
    washfr.rgb(0, 0, 0)

    washml = RGBLight(name="wash_3", dmx=dmx, addr=110, category="washes")
    washml.rgb(0, 0, 0)

    washmr = RGBLight(name="wash_4", dmx=dmx, addr=113, category="washes")
    washmr.rgb(0, 0, 0)

    washbl = RGBLight(name="wash_5", dmx=dmx, addr=120, category="washes")
    washbl.rgb(0, 0, 0)

    washbr = RGBLight(name="wash_6", dmx=dmx, addr=123, category="washes")
    washbr.rgb(0, 0, 0)

    washceilf = RGBWLight(name="wash_7", dmx=dmx, addr=100, category="washes")
    washceilf.rgbw(0, 0, 0, 0)

    washceilr = RGBWLight(name="wash_8", dmx=dmx, addr=116, category="washes")
    washceilr.rgbw(0, 0, 0, 0)

    washes = [washfl, washfr, washml, washmr, washbl, washbr, washceilf, washceilr]

    hazer = RadianceHazer(dmx, addr=250, debug=debug_hazer)

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

    if audio_interface is not None:
        needle = audio_interface.lower()
        match_idx: Optional[int] = None
        match_name: Optional[str] = None
        for i, port in enumerate(audio_capture.list_audio_ports()):
            if int(port["maxInputChannels"]) <= 0:
                continue
            name = str(port["name"])
            if needle in name.lower():
                match_idx = i
                match_name = name
                break
        if match_idx is None:
            print(
                "No audio input device matched '{}'".format(audio_interface),
                flush=True,
            )
        else:
            print(
                "Auto-connecting audio interface '{}' (index {})".format(
                    match_name, match_idx
                ),
                flush=True,
            )
            audio_capture.setup_audio(match_idx)
            audio_capture.start_audio()
            fft_manager.start_fft()

    if debug:
        fft1.debug = True
        fft2.debug = True

    mixer = Mixer(
        osc=osc,
        dmx=dmx,
        generators=generators,
        spots=spotlights,
        washes=washes,
        history_len=666 * 6,
        debug=debug,
    )

    session = SessionStore(session_file)

    def set_dmx_passthrough(value: Any) -> None:
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

    deps = ParamDeps(
        osc=osc,
        dmx=dmx,
        mixer=mixer,
        session=session,
        fft_manager=fft_manager,
        fft1=fft1,
        fft2=fft2,
        sin_reds=sin_reds,
        sin_plants=sin_plants,
        sin_booth=sin_booth,
        sin_wash=sin_wash,
        sq1=sq1,
        sq2=sq2,
        sq3=sq3,
        impulse=impulse,
        bpm_red=bpm_red,
        bpm_wash=bpm_wash,
        hazer=hazer,
        washceilf=washceilf,
        washceilr=washceilr,
        all_washes=[
            washfl,
            washfr,
            washml,
            washmr,
            washbl,
            washbr,
            washceilf,
            washceilr,
        ],
        spotlights=spotlights,
        set_dmx_passthrough=set_dmx_passthrough,
    )

    exposed_params = build_exposed_params(deps)

    def make_snap_handler(gens, period_addr, bpm_gen):
        def handler():
            if bpm_gen.bpm > 0 and bpm_gen.bpm_mult > 0:
                period = bpm_gen.current_period()
                for gen in gens:
                    gen.period = period
                osc.send_osc(period_addr, period)

        return handler

    presets = PresetManager(
        osc,
        exposed_params,
        presets_file,
        enable_save_clear=enable_save_clear,
        debug=debug,
        session=session,
    )

    def _session_snapshot():
        return {
            "current_presets": presets.save_current_selection(),
            "masters": mixer.save_current_masters(),
        }

    session.bind(_session_snapshot)

    osc.dispatcher.map("/reload", lambda addr, args: presets.sync())
    osc.dispatcher.map(
        "/enable_save", lambda _, args: presets.set_enable_save_clear(args)
    )

    def all_black():
        mixer.setChannelLevel("sodium", 0)

        presets.select_all("Off")

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
        "/set_synth_visualizer",
        lambda addr, *args: mixer.set_synth_visualizer(bool(args[0])),
    )
    osc.dispatcher.map("/all_black", lambda addr, args: all_black())
    osc.dispatcher.map("/house_lights", lambda addr, args: house_lights())
    osc.dispatcher.map("/class", lambda addr, args: class_lights())
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

    # Restore persisted session state (active presets, master fader values)
    # before the initial sync, so the front end is pushed the restored
    # values rather than defaults.
    restored = session.load()
    if restored is not None:
        print("Restoring session state", flush=True)
        presets.load_current_selection(restored.get("current_presets") or {})
        mixer.load_current_masters(restored.get("masters") or {})

    if debug:
        print("DEBUG channel generator connections after restore:", flush=True)
        for ch in mixer.mix_channels:
            if ch.connected_generators:
                print(
                    "  {}: [{}]".format(
                        ch.name, ", ".join(g.name for g in ch.connected_generators)
                    ),
                    flush=True,
                )

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
                hazer.tick()
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
