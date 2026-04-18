from typing import Dict, List, Optional

import sys
import time

import click

from .generators import Mixer
from .audio_analysis import FFTManager, AudioCapture

from .category import Category
from .osc import OSCManager, OSCParam
from .dmx import DMXManager
from .patching import Categories, create_builders
from .preset_manager import PresetManager
from .scene import Scene
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
    default=1000,
    show_default=True,
    type=int,
    help="Maximum samples per loop recording (1000 = 20s at 50Hz).",
)
@click.option(
    "--tick-ms",
    default=20,
    show_default=True,
    type=int,
    help="Mixer tick interval in milliseconds. Controls history resolution, stutter timing, and loop sample rate.",
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
    tick_ms: int,
) -> None:
    print("Setup", flush=True)

    # Set the global tick rate before anything reads it
    # pylint: disable=import-outside-toplevel
    import parquette.lights.generators.chanmap as chanmap_module

    chanmap_module.TICK_MS = tick_ms

    osc = OSCManager()
    osc.set_target(target_ip, target_port)
    osc.set_local(local_ip, local_port)
    osc.set_debug(debug_osc_in, debug_osc_out)
    dmx = DMXManager(osc, art_net_ip)
    dmx.use_art_net = boot_art_net
    dmx.art_net_auto_send(art_net_auto)
    if entec_auto is not None:
        dmx.setup_dmx(entec_auto)

    session = SessionStore(session_file)
    categories = Categories(osc, session)

    audio_capture = AudioCapture(osc, audio_window_secs=audio_window, debug=debug)
    audio_capture.dmx = dmx
    fft_manager = FFTManager(
        osc,
        audio_capture,
        dmx,
        rms_window_secs=rms_window,
        debug=debug,
    )

    # Create all patching builders — fixtures and generators are instantiated
    # in their constructors.
    builders = create_builders(
        osc=osc,
        dmx=dmx,
        categories=categories,
        fft_manager=fft_manager,
        session=session,
        loop_max_samples=loop_max_samples,
        spot_color_fade=spot_color_fade,
        spot_mechanical_time=spot_mechanical_time,
        debug=debug,
        debug_hazer=debug_hazer,
    )

    all_fixtures = []
    generators = []
    for b in builders:
        all_fixtures.extend(b.fixtures())
        generators.extend(b.generators())

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

    mixer = Mixer(
        osc=osc,
        dmx=dmx,
        generators=generators,
        fixtures=all_fixtures,
        categories=categories,
        debug=debug,
    )

    # Build all params from builders
    exposed_params: Dict[Category, List[OSCParam]] = {}
    for b in builders:
        for category, params in b.build_params(mixer).items():
            exposed_params.setdefault(category, []).extend(params)

    presets = PresetManager(
        osc,
        exposed_params,
        categories,
        presets_file,
        enable_save_clear=enable_save_clear,
        debug=debug,
        session=session,
    )

    def session_snapshot():
        masters = categories.save_masters()
        masters["sodium"] = mixer.channel_lookup["sodium/dimming"].offset
        return {
            "current_presets": presets.save_current_selection(),
            "masters": masters,
        }

    session.bind(session_snapshot)

    sodium_ch = mixer.channel_lookup["sodium/dimming"]

    Scene(
        name="all_black",
        osc=osc,
        dmx=dmx,
        presets=presets,
        masters={
            categories.reds: 0,
            categories.spots_light: 0,
            categories.washes: 0,
            categories.booth: 0,
            categories.plants: 0,
        },
        preset_group="Off",
        channel_offsets={sodium_ch: 0},
    )
    Scene(
        name="house_lights",
        osc=osc,
        dmx=dmx,
        presets=presets,
        masters={
            categories.reds: 1,
            categories.spots_light: 0,
            categories.washes: 1,
            categories.booth: 1,
            categories.plants: 1,
        },
        preset_group="Static",
        channel_offsets={sodium_ch: 255},
        disable_passthrough=True,
    )
    Scene(
        name="class_lights",
        osc=osc,
        dmx=dmx,
        presets=presets,
        masters={
            categories.reds: 0.8,
            categories.spots_light: 0.3,
            categories.washes: 0.25,
            categories.booth: 0,
            categories.plants: 0.5,
        },
        preset_group="Class",
        channel_offsets={sodium_ch: 0},
        disable_passthrough=True,
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
        masters = restored.get("masters") or {}
        categories.load_masters(masters)
        if "sodium" in masters:
            mixer.channel_lookup["sodium/dimming"].offset = masters["sodium"]

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

    tick_s = tick_ms / 1000
    print(
        "Start compute loop (tick_ms={}, {:.0f}Hz)".format(tick_ms, 1000 / tick_ms),
        flush=True,
    )
    try:
        next_tick = time.monotonic() + tick_s
        tick_count = 0
        debug_interval_start = time.monotonic()
        while True:
            if dmx.passthrough:
                dmx.submit_passthrough()
            else:
                mixer.runChannelMix()
                mixer.runOutputMix()
                for f in runnable_fixtures:
                    f.run()
                mixer.updateDMX()

            tick_count += 1
            if debug and tick_count % 500 == 0:
                now = time.monotonic()
                elapsed = now - debug_interval_start
                avg_ms = elapsed / 500 * 1000
                print(
                    "DEBUG tick: avg {:.1f}ms target {}ms ({:.0f}Hz actual)".format(
                        avg_ms, tick_ms, 1000 / avg_ms if avg_ms > 0 else 0
                    ),
                    flush=True,
                )
                debug_interval_start = now

            now = time.monotonic()
            sleep_time = next_tick - now
            if sleep_time > 0:
                time.sleep(sleep_time)
            next_tick += tick_s

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
