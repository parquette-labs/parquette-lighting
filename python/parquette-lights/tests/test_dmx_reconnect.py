"""Unit tests for DMXManager device ownership and Enttec auto-reconnect.

These exercise the single-thread device lifecycle (request_port /
tick_device) and the comport-gated backoff reconnect using a fake Enttec
controller and a controllable port list -- no real hardware.
"""

from __future__ import annotations

import time
from typing import Any, List, Tuple, cast

import pytest
from serial import SerialException

from parquette.lights import dmx as dmx_mod
from parquette.lights.dmx import DMXManager
from parquette.lights.osc import OSCManager

PORT = "/dev/tty.usbserial-TEST"


class FakeDispatcher:
    def map(self, *args: Any, **kwargs: Any) -> None:
        pass


class FakeOSC:
    def __init__(self) -> None:
        self.dispatcher = FakeDispatcher()
        self.sent: List[Tuple[str, Any]] = []

    def send_osc(self, addr: str, args: Any) -> None:
        self.sent.append((addr, args))


class FakeController:
    """Stand-in for the DMXEnttecPro Controller.

    open_should_fail simulates an absent/busy device on construction;
    fail_on_write simulates a mid-run disconnect from set_channel().
    """

    open_should_fail = False

    def __init__(self, port: str, auto_submit: bool = False, dmx_size: int = 512):
        if FakeController.open_should_fail:
            raise SerialException("simulated open failure")
        self.port = port
        self.closed = False
        self.fail_on_write = False
        self.fail_on_read = False
        self.channels = [0] * dmx_size

    def set_channel(self, chan: int, val: int) -> None:
        if self.fail_on_write:
            raise SerialException("simulated write fault")
        self.channels[chan - 1] = val

    def get_channel(self, chan: int) -> int:
        if self.fail_on_read:
            raise SerialException("simulated read fault")
        return self.channels[chan - 1]

    def submit(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def set_ports(monkeypatch: pytest.MonkeyPatch, ports: List[str]) -> None:
    """Make DMXManager.list_dmx_ports report the given ports as present."""
    monkeypatch.setattr(
        DMXManager, "list_dmx_ports", classmethod(lambda cls: list(ports))
    )


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> DMXManager:
    monkeypatch.setattr(dmx_mod, "EnttecProController", FakeController)
    FakeController.open_should_fail = False
    set_ports(monkeypatch, [PORT, DMXManager.ART_NET_PORT])
    return DMXManager(cast(OSCManager, FakeOSC()), art_net_ip="127.0.0.1")


def test_request_port_defers_open_to_compute_thread(manager: DMXManager) -> None:
    """OSC handlers only record intent; the device opens on tick_device."""
    manager.request_port(PORT)
    assert manager.device_dirty is True
    assert manager.enttec_pro_controller is None  # not opened by the OSC path

    manager.tick_device()
    assert manager.device_dirty is False
    assert isinstance(manager.enttec_pro_controller, FakeController)
    assert manager.active_port == PORT


def test_serial_fault_drops_controller_but_keeps_target(manager: DMXManager) -> None:
    """A write fault tears the controller down but retains desired_port so
    reconnect can fire."""
    manager.request_port(PORT)
    manager.tick_device()
    manager.enttec_pro_controller.fail_on_write = True

    manager.submit()

    assert manager.enttec_pro_controller is None
    assert manager.active_port is None
    assert manager.desired_port == PORT


def test_reconnect_gated_on_port_reappearing(
    manager: DMXManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager.request_port(PORT)
    manager.tick_device()
    manager.handle_device_fault()
    assert manager.enttec_pro_controller is None

    # Device absent -> tick must not reopen.
    set_ports(monkeypatch, [DMXManager.ART_NET_PORT])
    manager.next_reconnect_at = 0.0
    manager.tick_device()
    assert manager.enttec_pro_controller is None

    # Device reappears -> tick reopens and re-syncs the UI selector.
    set_ports(monkeypatch, [PORT, DMXManager.ART_NET_PORT])
    manager.next_reconnect_at = 0.0
    manager.tick_device()
    assert isinstance(manager.enttec_pro_controller, FakeController)
    assert manager.active_port == PORT
    assert ("/dmx/port_name", [PORT]) in cast(FakeOSC, manager.osc).sent


def test_backoff_grows_and_caps_at_max(
    manager: DMXManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager.request_port(PORT)
    manager.tick_device()
    manager.handle_device_fault()
    set_ports(monkeypatch, [DMXManager.ART_NET_PORT])  # stays absent

    seen = []
    for _ in range(6):
        seen.append(manager.reconnect_backoff)
        manager.next_reconnect_at = 0.0
        manager.tick_device()

    assert seen[0] == 1.0
    assert seen[:4] == [1.0, 2.0, 4.0, DMXManager.RECONNECT_BACKOFF_MAX]
    assert manager.reconnect_backoff == DMXManager.RECONNECT_BACKOFF_MAX
    assert max(seen) <= DMXManager.RECONNECT_BACKOFF_MAX


def test_auto_reconnect_flag_off_disables_reconnect(manager: DMXManager) -> None:
    manager.auto_reconnect = False
    manager.request_port(PORT)
    manager.tick_device()
    manager.handle_device_fault()

    manager.next_reconnect_at = 0.0
    manager.tick_device()  # port present, but reconnect disabled
    assert manager.enttec_pro_controller is None


def test_manual_disconnect_stops_reconnect(manager: DMXManager) -> None:
    manager.request_port(PORT)
    manager.tick_device()

    manager.request_port(None)  # user hits disconnect
    manager.tick_device()
    assert manager.enttec_pro_controller is None
    assert manager.desired_port is None

    manager.next_reconnect_at = 0.0
    manager.tick_device()  # desired is None -> no reconnect
    assert manager.enttec_pro_controller is None


def test_art_net_selection_does_not_reconnect_enttec(manager: DMXManager) -> None:
    manager.request_port(DMXManager.ART_NET_PORT)
    manager.tick_device()
    assert manager.use_art_net is True
    assert manager.enttec_pro_controller is None

    manager.next_reconnect_at = 0.0
    manager.tick_device()  # art-net is not an enttec port -> no reconnect attempt
    assert manager.enttec_pro_controller is None


def test_art_net_without_ip_target_stays_off(manager: DMXManager) -> None:
    """Selecting art-net with no art_net_ip target must not enable art-net;
    it falls back to no-device and deselects the UI."""
    manager.art_net_ip = ""
    manager.request_port(DMXManager.ART_NET_PORT)
    manager.tick_device()
    assert manager.use_art_net is False
    assert manager.active_port is None
    assert ("/dmx/port_name", [None]) in cast(FakeOSC, manager.osc).sent


def test_reselecting_active_port_does_not_reopen(manager: DMXManager) -> None:
    """Re-requesting the already-active port must leave the live controller
    untouched -- no leaked handle, no mid-show device re-init (H1)."""
    manager.request_port(PORT)
    manager.tick_device()
    ctrl = manager.enttec_pro_controller
    assert ctrl is not None

    manager.request_port(PORT)  # same port again
    manager.tick_device()
    assert manager.enttec_pro_controller is ctrl  # not reopened


def test_read_input_fault_drops_controller(manager: DMXManager) -> None:
    manager.request_port(PORT)
    manager.tick_device()
    manager.enttec_pro_controller.fail_on_read = True

    manager.read_input_universe()

    assert manager.enttec_pro_controller is None
    assert manager.desired_port == PORT  # kept for reconnect


def test_reconnect_respects_backoff_timer(manager: DMXManager) -> None:
    manager.request_port(PORT)
    manager.tick_device()
    manager.handle_device_fault()

    manager.next_reconnect_at = time.monotonic() + 999  # gate closed
    before = manager.reconnect_backoff
    manager.tick_device()

    assert manager.enttec_pro_controller is None  # no attempt made
    assert manager.reconnect_backoff == before  # backoff not advanced


def test_failed_open_then_recovers(manager: DMXManager) -> None:
    FakeController.open_should_fail = True
    manager.request_port(PORT)
    manager.tick_device()  # open fails
    assert manager.enttec_pro_controller is None
    assert manager.desired_port == PORT

    FakeController.open_should_fail = False
    manager.next_reconnect_at = 0.0
    manager.tick_device()  # reconnect succeeds
    assert isinstance(manager.enttec_pro_controller, FakeController)


def test_enttec_to_art_net_transition(manager: DMXManager) -> None:
    manager.request_port(PORT)
    manager.tick_device()
    ctrl = manager.enttec_pro_controller
    assert ctrl is not None

    manager.request_port(DMXManager.ART_NET_PORT)
    manager.tick_device()

    assert manager.use_art_net is True
    assert manager.enttec_pro_controller is None
    assert ctrl.closed is True  # teardown closed the old controller
    assert manager.active_port == DMXManager.ART_NET_PORT


def test_open_survives_os_error(
    manager: DMXManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-SerialException open failure (e.g. OSError) must be caught by
    open_enttec, not propagate to the compute loop (H2)."""

    class BadController:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise OSError("device busy")

    monkeypatch.setattr(dmx_mod, "EnttecProController", BadController)
    manager.request_port(PORT)
    manager.tick_device()  # must not raise

    assert manager.enttec_pro_controller is None
    assert manager.desired_port == PORT


def test_tick_device_survives_unexpected_error(
    manager: DMXManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exception open_enttec does not catch must still be swallowed by the
    tick_device guard so the compute loop never dies (H2 backstop)."""

    class ExplodingController:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("unexpected")

    monkeypatch.setattr(dmx_mod, "EnttecProController", ExplodingController)
    manager.request_port(PORT)
    manager.tick_device()  # must not raise

    assert manager.enttec_pro_controller is None


def test_list_dmx_ports_survives_comports_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom() -> None:
        raise OSError("iokit enumeration failed")

    monkeypatch.setattr(dmx_mod.slp, "comports", boom)
    assert DMXManager.list_dmx_ports() == [DMXManager.ART_NET_PORT]
