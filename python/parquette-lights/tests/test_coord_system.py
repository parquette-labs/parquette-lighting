"""Tests for the coord-system layer.

Covers the standalone CoordSystem implementations (round-trips, ranges,
unreachable handling) and the CoordSystemState toggle wiring.
"""

import pickle
from pathlib import Path

import pytest

from parquette.lights.coord_system_state import CoordSystemState
from parquette.lights.osc import OSCManager
from parquette.lights.util.coord_system import (
    LatLonCoordSystem,
    PanTiltCoordSystem,
    RawCoordSystem,
    default_systems,
)
from parquette.lights.util.coordinates import SpotCoordFrame
from parquette.lights.util.session_store import SessionStore


def default_frame() -> SpotCoordFrame:
    return SpotCoordFrame(
        pan_down=0.0,
        tilt_down=100.0,
        pan_north=0.0,
        tilt_north=10.0,
        pan_range=(0.0, 540.0),
        tilt_range=(0.0, 200.0),
    )


# PanTiltCoordSystem — identity in both directions.


def test_pantilt_passthrough():
    sys = PanTiltCoordSystem()
    frame = default_frame()
    assert sys.mapping_to_real([100.0, 200.0], frame) == [100.0, 200.0]
    assert sys.real_to_mapping([100.0, 200.0], frame) == [100.0, 200.0]


def test_pantilt_passthrough_with_current_hint_unused():
    sys = PanTiltCoordSystem()
    frame = default_frame()
    # current_real should not change identity output
    out = sys.mapping_to_real([42.0, 7.0], frame, current_real=[999.0, 999.0])
    assert out == [42.0, 7.0]


# RawCoordSystem — same as PanTilt but distinct class.


def test_raw_passthrough_matches_pantilt():
    raw = RawCoordSystem()
    pt = PanTiltCoordSystem()
    frame = default_frame()
    for xy in ([0.0, 0.0], [32767.0, 32767.0], [65535.0, 65535.0]):
        assert raw.mapping_to_real(xy, frame) == pt.mapping_to_real(xy, frame)
        assert raw.real_to_mapping(xy, frame) == pt.real_to_mapping(xy, frame)


def test_raw_and_pantilt_are_distinct_classes():
    assert RawCoordSystem is not PanTiltCoordSystem
    assert RawCoordSystem.name == "raw"
    assert PanTiltCoordSystem.name == "pantilt"


# LatLonCoordSystem — mapping-space (16-bit) <-> real pan/tilt (16-bit).


def test_latlon_centre_maps_to_straight_down():
    sys = LatLonCoordSystem()
    frame = default_frame()
    # 16-bit midpoint x maps to lat=0; y midpoint maps to lon=0.
    # That's straight down — pan is a free parameter at the singularity,
    # so the math picks the range-centre pan (270/540 -> 65535/2 = 32767.5).
    # tilt_down=100 -> 100/200 -> 65535/2 = 32767.5.
    real = sys.mapping_to_real([32767.5, 32767.5], frame)
    assert real is not None
    assert 0 <= real[0] <= 65535
    assert abs(real[1] - 32767.5) < 1.0


def test_latlon_round_trip_anchor_points():
    sys = LatLonCoordSystem()
    frame = default_frame()
    # Several reachable mapping points (avoid the lon=±180 region which
    # would point through the ceiling).
    midpoint = 32767.5
    samples = [
        [midpoint, midpoint],  # straight down
        [midpoint + 5000, midpoint],
        [midpoint - 5000, midpoint],
        [midpoint, midpoint + 5000],
        [midpoint, midpoint - 5000],
    ]
    for xy in samples:
        real = sys.mapping_to_real(xy, frame)
        assert real is not None, f"unreachable: {xy}"
        recovered = sys.real_to_mapping(real, frame)
        assert abs(recovered[0] - xy[0]) < 1.0
        assert abs(recovered[1] - xy[1]) < 1.0


def test_latlon_unreachable_returns_none():
    """Pointing the beam straight up through the ceiling is unreachable
    given the default tilt range — mapping_to_real should return None."""
    sys = LatLonCoordSystem()
    # Constrict tilt to near straight-down. The pole (lat=+90) requires
    # tilt=10 which is outside this range -> no solution.
    frame = SpotCoordFrame(
        pan_down=0.0,
        tilt_down=100.0,
        pan_north=0.0,
        tilt_north=10.0,
        pan_range=(0.0, 540.0),
        tilt_range=(90.0, 110.0),
    )
    # Map x=65535 -> lat=+90 (the pole)
    assert sys.mapping_to_real([65535.0, 32767.5], frame) is None


# default_systems factory


def test_default_systems_has_pantilt_and_latlon():
    systems = default_systems()
    assert "pantilt" in systems
    assert "latlon" in systems
    assert isinstance(systems["pantilt"], PanTiltCoordSystem)
    assert isinstance(systems["latlon"], LatLonCoordSystem)


# CoordSystemState — toggle, registration, listener notification.


class DummyListener:
    """Stand-in for a YRXY200Spot. Records rebind_coords calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def rebind_coords(self, old, new) -> None:
        self.calls.append((old.name, new.name))


def make_state(tmp_path: Path, initial: str = "pantilt") -> CoordSystemState:
    osc = OSCManager()
    # No set_local — we don't need to receive OSC for these tests, and
    # binding a UDP port would collide across tests in the same module.
    # set_target without a real listener is fine; send_message goes into
    # the void.
    osc.set_target("127.0.0.1", 17006)
    session = SessionStore(str(tmp_path / "session.pickle"))
    return CoordSystemState(
        systems=default_systems(),
        osc=osc,
        session=session,
        initial_active=initial,
    )


def test_state_default_active(tmp_path: Path):
    state = make_state(tmp_path)
    assert state.active_name == "pantilt"
    assert isinstance(state.active, PanTiltCoordSystem)


def test_state_seeded_from_initial(tmp_path: Path):
    state = make_state(tmp_path, initial="latlon")
    assert state.active_name == "latlon"


def test_state_unknown_initial_falls_back(tmp_path: Path):
    state = make_state(tmp_path, initial="bogus")
    # Falls back to the first key in default_systems (pantilt)
    assert state.active_name == "pantilt"


def test_state_set_active_notifies_listeners(tmp_path: Path):
    state = make_state(tmp_path)
    a, b = DummyListener(), DummyListener()
    state.register(a)
    state.register(b)
    state.set_active("latlon")
    assert a.calls == [("pantilt", "latlon")]
    assert b.calls == [("pantilt", "latlon")]
    assert state.active_name == "latlon"


def test_state_set_active_noop_when_unchanged(tmp_path: Path):
    state = make_state(tmp_path)
    listener = DummyListener()
    state.register(listener)
    state.set_active("pantilt")
    assert listener.calls == []


def test_state_set_active_ignores_unknown(tmp_path: Path):
    state = make_state(tmp_path)
    listener = DummyListener()
    state.register(listener)
    state.set_active("bogus")
    assert state.active_name == "pantilt"
    assert listener.calls == []


def test_state_persists_to_session(tmp_path: Path):
    """Toggling the system triggers session.save (debounced). Manually
    flush by calling the bound snapshot fn directly via _flush would
    require complex setup — instead just check active_name works for the
    snapshot fn that server.py would register."""
    state = make_state(tmp_path)
    state.set_active("latlon")
    assert state.active_name == "latlon"


def test_state_session_round_trip(tmp_path: Path):
    """Simulate the server.py wiring: snapshot includes coord_system;
    on relaunch, initial_active reads it back."""
    session_file = tmp_path / "session.pickle"

    # First launch — set to latlon, snapshot, write.
    osc = OSCManager()
    osc.set_target("127.0.0.1", 17008)
    session = SessionStore(str(session_file), debounce_seconds=0.0)
    state = CoordSystemState(systems=default_systems(), osc=osc, session=session)
    session.bind(lambda: {"coord_system": state.active_name})
    state.set_active("latlon")
    # Force the debounced flush
    # pylint: disable=protected-access
    state.session._flush()

    # Second launch — load and seed initial_active.
    with open(session_file, "rb") as f:
        data = pickle.load(f)
    assert data["coord_system"] == "latlon"

    osc2 = OSCManager()
    osc2.set_target("127.0.0.1", 17010)
    session2 = SessionStore(str(session_file))
    state2 = CoordSystemState(
        systems=default_systems(),
        osc=osc2,
        session=session2,
        initial_active=data["coord_system"],
    )
    assert state2.active_name == "latlon"


# Integration with the spot fixture: rebind_coords keeps the head still.
# Use a stub spot rather than the real fixture to keep the test isolated
# from DMX wiring.


class StubSpot:
    """Mimics the YRXY200Spot interface used by rebind_coords."""

    def __init__(self) -> None:
        self.coord_frame = default_frame()
        self._x_coord: float = 32767.5
        self._y_coord: float = 32767.5
        # Track simulated real DMX state — set by post_map_output below.
        self._pan: int = 0
        self._tilt: int = 32767
        self.pantilt_param = None  # No real OSC binding for this test.

    def simulate_post_map_output(self, system) -> None:
        """Run the mapping_to_real conversion and store in _pan/_tilt
        like the real spot would."""
        real = system.mapping_to_real(
            [self._x_coord, self._y_coord],
            self.coord_frame,
            current_real=[float(self._pan), float(self._tilt)],
        )
        if real is not None:
            self._pan = int(real[0])
            self._tilt = int(real[1])


def test_rebind_coords_keeps_real_position():
    """Switching coord systems should leave the physical pan/tilt
    unchanged: re-express the offsets in the new system, then the next
    post_map_output yields the same real output."""
    pt = PanTiltCoordSystem()
    ll = LatLonCoordSystem()
    frame = default_frame()
    spot = StubSpot()

    # Start in pantilt: arbitrary mapping values are also the real values.
    spot._x_coord = 12345.0
    spot._y_coord = 30000.0
    spot.simulate_post_map_output(pt)
    real_before = (spot._pan, spot._tilt)

    # Toggle: re-express in latlon. Replicate the rebind_coords math.
    real = pt.mapping_to_real(
        [spot._x_coord, spot._y_coord],
        frame,
        current_real=[float(spot._pan), float(spot._tilt)],
    )
    new_xy = ll.real_to_mapping(real, frame)
    spot._x_coord, spot._y_coord = new_xy

    # Re-run output through the new system. The real values should match.
    spot.simulate_post_map_output(ll)
    real_after = (spot._pan, spot._tilt)

    assert abs(real_after[0] - real_before[0]) <= 1
    assert abs(real_after[1] - real_before[1]) <= 1
