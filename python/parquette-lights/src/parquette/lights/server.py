from typing import Any, Callable, Optional

import sys
import time

import click

from .generators import LoopGenerator, Mixer
from .audio_analysis import FFTManager, AudioCapture

from .osc import OSCManager
from .dmx import DMXManager
from .patching import create_builders
from .patching.fixtures import create_fixtures
from .patching.audio import AudioBuilder
from .patching.booth import BoothBuilder
from .patching.plants import PlantsBuilder
from .patching.reds import RedsBuilder
from .patching.spots import SpotsBuilder
from .patching.strobes import StrobesBuilder
from .patching.washes import WashesBuilder
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
@click.option(
    "--loop-max-samples",
    default=500,
    show_default=True,
    type=int,
    help="Maximum samples per loop recording (500 = 10s at 50Hz).",
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
    loop_max_samples: int,
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

    all_fixtures = create_fixtures(
        dmx=dmx,
        osc=osc,
        spot_color_fade=spot_color_fade,
        spot_mechanical_time=spot_mechanical_time,
        debug_hazer=debug_hazer,
    )

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

    session = SessionStore(session_file)

    # Create all patching builders — generators are instantiated in constructors
    builders = create_builders(
        all_fixtures=all_fixtures,
        fft_manager=fft_manager,
        dmx=dmx,
        session=session,
        loop_max_samples=loop_max_samples,
    )

    # Keep typed refs for snap handlers, fft wiring, etc.
    reds_b: RedsBuilder = next(b for b in builders if isinstance(b, RedsBuilder))
    plants_b: PlantsBuilder = next(b for b in builders if isinstance(b, PlantsBuilder))
    booth_b: BoothBuilder = next(b for b in builders if isinstance(b, BoothBuilder))
    washes_b: WashesBuilder = next(b for b in builders if isinstance(b, WashesBuilder))
    spots_b: SpotsBuilder = next(b for b in builders if isinstance(b, SpotsBuilder))
    audio_b: AudioBuilder = next(b for b in builders if isinstance(b, AudioBuilder))
    strobes_b: StrobesBuilder = next(
        b for b in builders if isinstance(b, StrobesBuilder)
    )

    # Collect all generators for mixer
    generators = []
    for b in builders:
        generators.extend(b.generators())

    # Wire FFT manager to its downstream generators
    fft_manager.downstream = [audio_b.fft1, audio_b.fft2]
    fft_manager.bpms = [reds_b.bpm_red, washes_b.bpm_wash]

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
        audio_b.fft1.debug = True
        audio_b.fft2.debug = True

    mixer = Mixer(
        osc=osc,
        dmx=dmx,
        generators=generators,
        fixtures=all_fixtures,
        history_len=666 * 6,
        debug=debug,
    )

    # Build all params from builders
    exposed_params: dict[str, list] = {}
    for b in builders:
        for category, params in b.build_params(osc, mixer).items():
            exposed_params.setdefault(category, []).extend(params)

    def make_snap_handler(gens, period_addrs, bpm_gen):
        if isinstance(period_addrs, str):
            period_addrs = [period_addrs]

        def handler():
            if bpm_gen.bpm > 0 and bpm_gen.bpm_mult > 0:
                period = bpm_gen.current_period()
                for gen in gens:
                    gen.period = period
                for addr in period_addrs:
                    osc.send_osc(addr, period)

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
        mixer.channel_lookup["sodium.dimming"].offset = 0

        presets.select_all("Off")

    def house_lights():
        if dmx.passthrough:
            dmx.passthrough = False

        mixer.reds_master = 1
        mixer.spots_master = 0
        mixer.washes_master = 1
        mixer.booth_master = 1
        mixer.plants_master = 1

        mixer.channel_lookup["sodium.dimming"].offset = 255

        presets.select_all("Static")

    def class_lights():
        mixer.reds_master = 0.8
        mixer.spots_master = 0.3
        mixer.washes_master = 0.25
        mixer.booth_master = 0
        mixer.plants_master = 0.5

        mixer.channel_lookup["sodium.dimming"].offset = 0

        if dmx.passthrough:
            dmx.passthrough = False

        presets.select_all("Class")

    osc.dispatcher.map(
        "/set_fft_viz", lambda addr, *args: mixer.set_fft_viz(bool(args[0]))
    )
    osc.dispatcher.map(
        "/set_synth_visualizer",
        lambda addr, *args: mixer.set_synth_visualizer(bool(args[0])),
    )
    osc.dispatcher.map(
        "/set_fixture_visualizer",
        lambda addr, *args: mixer.set_fixture_visualizer(bool(args[0])),
    )
    osc.dispatcher.map("/all_black", lambda addr, args: all_black())
    osc.dispatcher.map("/house_lights", lambda addr, args: house_lights())
    osc.dispatcher.map("/class", lambda addr, args: class_lights())
    osc.dispatcher.map(
        "/impulse_punch",
        lambda addr, *args: strobes_b.impulse.punch(),
    )

    # Snap-to-BPM action buttons. These are momentary actions, not state, so
    # they're registered directly on the dispatcher (not as OSCParams) and
    # therefore are never written into preset pickles. Previously they lived
    # as OSCParams inside saved categories, which meant preset save captured
    # `/snap_*_to_bpm = 0` and preset load re-fired the snap, clobbering the
    # restored period of the corresponding sine generator.
    osc.dispatcher.map(
        "/snap_sin_red_to_bpm",
        lambda addr, *args: make_snap_handler(
            [reds_b.sin_reds], "/sin_red_period", reds_b.bpm_red
        )(),
    )
    osc.dispatcher.map(
        "/snap_sin_plants_to_bpm",
        lambda addr, *args: make_snap_handler(
            [plants_b.sin_plants], "/sin_plants_period", reds_b.bpm_red
        )(),
    )
    osc.dispatcher.map(
        "/snap_sq_to_bpm",
        lambda addr, *args: make_snap_handler(
            [plants_b.sq1, plants_b.sq2, plants_b.sq3],
            "/sq_period",
            reds_b.bpm_red,
        )(),
    )
    osc.dispatcher.map(
        "/snap_sin_booth_to_bpm",
        lambda addr, *args: make_snap_handler(
            [booth_b.sin_booth], "/sin_booth_period", reds_b.bpm_red
        )(),
    )
    osc.dispatcher.map(
        "/snap_sin_wash_to_bpm",
        lambda addr, *args: make_snap_handler(
            [washes_b.sin_wash], "/period_wash", washes_b.bpm_wash
        )(),
    )
    osc.dispatcher.map(
        "/snap_sin_spot_to_bpm",
        lambda addr, *args: make_snap_handler(
            [spots_b.sin_spot], "/sin_spot_period", reds_b.bpm_red
        )(),
    )
    osc.dispatcher.map(
        "/snap_sin_spot_pos_to_bpm",
        lambda addr, *args: make_snap_handler(
            [
                spots_b.sin_spot_pos_1,
                spots_b.sin_spot_pos_2,
                spots_b.sin_spot_pos_3,
                spots_b.sin_spot_pos_4,
            ],
            [
                "/sin_spot_pos_1_period",
                "/sin_spot_pos_2_period",
                "/sin_spot_pos_3_period",
                "/sin_spot_pos_4_period",
            ],
            reds_b.bpm_red,
        )(),
    )

    # Loop generator record triggers (momentary actions, not preset state)
    osc.dispatcher.map(
        "/loop_reds_record",
        lambda addr, *args: reds_b.loop_reds.set_recording(bool(args[0])),
    )

    for i, (lx, ly) in enumerate(
        [
            (spots_b.loop_spot_pos_1_x, spots_b.loop_spot_pos_1_y),
            (spots_b.loop_spot_pos_2_x, spots_b.loop_spot_pos_2_y),
        ],
        start=1,
    ):

        def make_record_handler(gx: LoopGenerator, gy: LoopGenerator) -> Callable:
            # pylint: disable-next=unused-argument
            def handler(addr: str, *args: Any) -> None:
                ts = time.time() * 1000
                gx.set_recording(bool(args[0]), ts)
                gy.set_recording(bool(args[0]), ts)

            return handler

        osc.dispatcher.map(
            "/loop_spot_pos_{}_record".format(i),
            make_record_handler(lx, ly),
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

    runnable_fixtures = [f for f in all_fixtures if f.runnable]

    print("Start compute loop", flush=True)
    try:
        while True:
            if dmx.passthrough:
                dmx.submit_passthrough()
            else:
                mixer.runChannelMix()
                mixer.runOutputMix()
                for f in runnable_fixtures:
                    f.run()
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
