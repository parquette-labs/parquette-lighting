"""Shared fixtures for the UI regression test suite.

`layout_json` / `layout_widgets` are session-scoped static parses of
`open-stage-control/layout-config.json`. `server_instance` boots the real
server wiring in-process (no audio device, no DMX hardware) on a non-default
OSC port so tests can drive it via a `python_osc` client end-to-end.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

import pytest
from pythonosc.udp_client import SimpleUDPClient

from parquette.lights.audio_analysis import AudioCapture, FFTManager
from parquette.lights.category import Categories
from parquette.lights.dmx import DMXManager
from parquette.lights.generators import Mixer
from parquette.lights.osc import OSCManager, OSCParam
from parquette.lights.patching import create_builders
from parquette.lights.preset_manager import PresetManager
from parquette.lights.scene import Scene
from parquette.lights.util.session_store import SessionStore


REPO_ROOT = Path(__file__).resolve().parents[3]
LAYOUT_PATH = REPO_ROOT / "open-stage-control" / "layout-config.json"

# Non-default ports so a live server on 5005/5006 doesn't collide.
TEST_LOCAL_PORT = 15005
TEST_TARGET_PORT = 15006

# Widget types that carry a user-driven value and therefore need a matching
# server-side handler. Layout-only widgets (containers, labels, plots, etc.)
# are excluded from the UI↔server address diff.
VALUE_BEARING_WIDGET_TYPES = {
    "fader",
    "button",
    "switch",
    "rgb",
    "xy",
    "multixy",
    "dropdown",
    "patchbay",
}


@dataclass
class Widget:
    """Flattened view of a single widget from layout-config.json."""

    id: str
    type: str
    address: Optional[str]
    top: Any
    left: Any
    width: Any
    height: Any
    parent_id: Optional[str]
    depth: int
    raw: Dict[str, Any] = field(repr=False)

    @property
    def resolved_address(self) -> Optional[str]:
        """Concrete OSC address for this widget.

        `address: "auto"` resolves to `/` + id (Open Stage Control's default).
        A literal address is used verbatim. No address → None.
        """
        if self.address is None:
            return None
        if self.address == "auto":
            if self.id is None:
                return None
            return self.id if self.id.startswith("/") else "/" + self.id
        return self.address


def _walk_widgets(
    node: Any,
    parent_id: Optional[str],
    depth: int,
    out: List[Widget],
) -> None:
    if isinstance(node, dict):
        widget_type = node.get("type")
        widget_id = node.get("id")
        if widget_type and widget_type not in ("session", "root"):
            out.append(
                Widget(
                    id=widget_id or "",
                    type=widget_type,
                    address=node.get("address"),
                    top=node.get("top"),
                    left=node.get("left"),
                    width=node.get("width"),
                    height=node.get("height"),
                    parent_id=parent_id,
                    depth=depth,
                    raw=node,
                )
            )
        next_parent = widget_id if widget_id is not None else parent_id
        next_depth = depth + 1 if widget_type else depth
        for value in node.values():
            if isinstance(value, (list, dict)):
                _walk_widgets(value, next_parent, next_depth, out)
    elif isinstance(node, list):
        for child in node:
            _walk_widgets(child, parent_id, depth, out)


@pytest.fixture(scope="session")
def layout_json() -> Dict[str, Any]:
    with open(LAYOUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def layout_widgets(layout_json: Dict[str, Any]) -> List[Widget]:
    out: List[Widget] = []
    _walk_widgets(layout_json, None, 0, out)
    return out


@dataclass
class ServerContext:
    osc: OSCManager
    dmx: DMXManager
    categories: Categories
    mixer: Mixer
    presets: PresetManager
    exposed_params: Dict[Any, List[OSCParam]]
    all_fixtures: List[Any]
    generators: List[Any]
    runnable_fixtures: List[Any]
    tick: Callable[[], None]
    audio_capture: AudioCapture
    session: SessionStore


@pytest.fixture(scope="session")
def server_instance(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[ServerContext]:
    """Boot the full server stack in-process without audio or DMX hardware.

    Mirrors the wiring in `server.py:run()` but stops before the compute loop.
    Tests drive the server via OSC and call `ctx.tick()` to advance one frame.
    """
    tmp_dir = tmp_path_factory.mktemp("server")
    session_file = str(tmp_dir / "session.pickle")
    presets_file = str(tmp_dir / "params.pickle")

    osc = OSCManager()
    osc.set_target("127.0.0.1", TEST_TARGET_PORT)
    osc.set_local("127.0.0.1", TEST_LOCAL_PORT)

    dmx = DMXManager(osc, art_net_ip="127.0.0.1")

    session = SessionStore(session_file)
    categories = Categories(osc, session)

    audio_capture = AudioCapture(osc, audio_window_secs=5.0)
    audio_capture.dmx = dmx
    fft_manager = FFTManager(
        osc,
        audio_capture,
        dmx,
        rms_window_secs=0.5,
        debug=False,
    )

    builders = create_builders(
        osc=osc,
        dmx=dmx,
        categories=categories,
        fft_manager=fft_manager,
        session=session,
        loop_max_samples=500,
        spot_color_fade=0.1,
        spot_mechanical_time=0.45,
        debug=False,
        debug_hazer=False,
    )

    all_fixtures: List[Any] = []
    generators: List[Any] = []
    for b in builders:
        all_fixtures.extend(b.fixtures())
        generators.extend(b.generators())

    mixer = Mixer(
        osc=osc,
        dmx=dmx,
        generators=generators,
        fixtures=all_fixtures,
        categories=categories,
        history_len=666 * 6,
        debug=False,
    )

    exposed_params: Dict[Any, List[OSCParam]] = {}
    for b in builders:
        for category, params in b.build_params(mixer).items():
            exposed_params.setdefault(category, []).extend(params)

    presets = PresetManager(
        osc,
        exposed_params,
        categories,
        presets_file,
        enable_save_clear=True,
        debug=False,
        session=session,
    )

    runnable_fixtures = [f for f in all_fixtures if f.runnable]

    def tick() -> None:
        if dmx.passthrough:
            dmx.submit_passthrough()
            return
        mixer.runChannelMix()
        mixer.runOutputMix()
        for f in runnable_fixtures:
            f.run()
        mixer.updateDMX()

    # Register the same top-level handlers that server.py adds outside
    # the builder chain. These are needed so the UI→server address diff
    # test does not false-positive on them.
    osc.dispatcher.map(
        "/visualizer/enable_fft",
        lambda addr, *args: mixer.set_fft_viz(bool(args[0])),
    )
    osc.dispatcher.map(
        "/visualizer/enable_synth",
        lambda addr, *args: mixer.set_synth_visualizer(bool(args[0])),
    )
    osc.dispatcher.map(
        "/visualizer/enable_fixture",
        lambda addr, *args: mixer.set_fixture_visualizer(bool(args[0])),
    )
    osc.dispatcher.map("/reload", lambda addr, args: presets.sync())
    osc.dispatcher.map(
        "/enable_save", lambda _, args: presets.set_enable_save_clear(args)
    )

    # Scene self-registers at /scene/<name>; instantiate the same set of
    # scenes that server.py registers so the UI→server address diff test
    # sees them.
    for scene_name, preset_group in (
        ("all_black", "Off"),
        ("house_lights", "Static"),
        ("class_lights", "Class"),
    ):
        Scene(
            name=scene_name,
            osc=osc,
            dmx=dmx,
            presets=presets,
            masters={},
            preset_group=preset_group,
        )

    osc.serve(threaded=True)

    ctx = ServerContext(
        osc=osc,
        dmx=dmx,
        categories=categories,
        mixer=mixer,
        presets=presets,
        exposed_params=exposed_params,
        all_fixtures=all_fixtures,
        generators=generators,
        runnable_fixtures=runnable_fixtures,
        tick=tick,
        audio_capture=audio_capture,
        session=session,
    )

    try:
        yield ctx
    finally:
        osc.close()
        try:
            audio_capture.terminate()
        # pylint: disable-next=broad-exception-caught
        except Exception:
            pass
        dmx.close()


@pytest.fixture(scope="session")
def osc_client() -> SimpleUDPClient:
    return SimpleUDPClient("127.0.0.1", TEST_LOCAL_PORT)


@pytest.fixture
def flush() -> Callable[[], None]:
    """Wait for asynchronous UDP dispatch to settle before asserting."""

    def do_flush(duration: float = 0.08) -> None:
        time.sleep(duration)

    return do_flush
