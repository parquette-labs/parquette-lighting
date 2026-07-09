import time
from typing import List, Union, Optional

from DMXEnttecPro import Controller as EnttecProController  # type: ignore[import-untyped]
from stupidArtnet import StupidArtnet, StupidArtnetServer  # type: ignore[import-untyped]

from serial import SerialException
import serial.tools.list_ports as slp

from .osc import OSCManager, OSCParam
from .util.math import constrain, value_map

DMXValue = Union[int, float]
DMXListOrValue = Union[List[DMXValue], DMXValue]


class DMXControlRange(object):
    def __init__(self, name: str, start_val: int, end_val: Optional[int] = None):
        if start_val > 255 or start_val < 0:
            raise ValueError(
                "DMX control range start_val must be a valid DMX value between 0-255, value passed was {}".format(
                    start_val
                )
            )

        if not end_val is None:
            if end_val > 255 or end_val < 0:
                raise ValueError(
                    "DMX control range end_val must be a valid DMX value between 0-255, value passed was {}".format(
                        end_val
                    )
                )

        self.start_val = start_val
        self.end_val = end_val
        self.name = name

    def map(self, val: DMXValue = 0) -> DMXValue:
        if self.end_val is None:
            return self.start_val

        return value_map(val, 0, 255, self.start_val, self.end_val, True)


class DMXControlChannel(object):
    def __init__(
        self,
        name: str,
        offset: int,
        ranges: Optional[List[DMXControlRange]] = None,
    ):
        self.offset = offset
        self.name = name
        self.ranges = ranges

    def range_names(self) -> List[str]:
        if self.ranges is None:
            return []
        else:
            return [r.name for r in self.ranges]

    def get_range(
        self, *, range_index: Optional[int] = None, range_name: Optional[str] = None
    ):
        if not range_name is None and range_index is None:
            range_index = self.range_names().index(range_name)
        if range_index is None or self.ranges is None:
            return None
        else:
            return self.ranges[range_index]

    def map(
        self,
        val: DMXValue = 0,
        *,
        range_index: Optional[int] = None,
        range_name: Optional[str] = None,
    ) -> DMXValue:
        dmx_range = self.get_range(range_index=range_index, range_name=range_name)

        if dmx_range is None:
            return constrain(val, 0, 255)
        else:
            return dmx_range.map(val)


class DMXManager(object):
    enttec_pro_controller: EnttecProController = None
    art_net_controller: StupidArtnet = None
    art_net_server: Optional[StupidArtnetServer] = None
    art_net_listener_id: Optional[int] = None
    use_art_net: bool = False
    passthrough: bool = False

    ART_NET_PORT = "art-net-node-1"
    RECONNECT_BACKOFF_START = 1.0
    RECONNECT_BACKOFF_MAX = 5.0

    def __init__(
        self, osc: OSCManager, art_net_ip: str, universe_size: int = 512
    ) -> None:
        self.osc = osc
        self.universe_size = universe_size
        self.chans: List[int] = [0 for i in range(universe_size)]

        self.art_net_ip = art_net_ip
        self.art_net_controller = StupidArtnet(self.art_net_ip)
        self.art_net_controller.set_simplified(False)
        self.art_net_controller.set_universe(0)
        self.art_net_controller.set_subnet(0)
        self.art_net_controller.set_net(0)

        # Device ownership: OSC handler threads only record the desired port
        # via request_port(); the real device (enttec controller / art-net
        # server) is opened, closed, and used exclusively on the compute-loop
        # thread (tick_device / submit / read_input_universe). This keeps the
        # device lifecycle single-threaded so it never races with the
        # concurrent OSC handler threads. active_port tracks what is open.
        self.desired_port: Optional[str] = None
        self.active_port: Optional[str] = None
        self.device_dirty: bool = False

        # Auto-reconnect: retry reopening a dropped enttec port, comport-gated
        # with exponential backoff. Toggled by --dmx-auto-reconnect.
        self.auto_reconnect: bool = True
        self.reconnect_backoff: float = self.RECONNECT_BACKOFF_START
        self.next_reconnect_at: float = 0.0

        self.osc.dispatcher.map(
            "/dmx/port_refresh", lambda addr, args: self.dmx_port_refresh()
        )
        self.osc.dispatcher.map(
            "/dmx/port_disconnect", lambda addr, args: self.request_port(None)
        )
        self.osc.dispatcher.map(
            "/dmx/port_name", lambda addr, args: self.request_port(args)
        )

    def passthrough_param(self) -> OSCParam:
        """Bind /dmx/passthrough to DMXManager.passthrough."""
        return OSCParam.bind(self.osc, "/dmx/passthrough", self, "passthrough")

    @classmethod
    def list_dmx_ports(cls) -> List[str]:
        device = [
            l.device for l in slp.comports() if l.manufacturer in ("FTDI", "ENTTEC")
        ]
        device.append("art-net-node-1")
        return device

    def dmx_port_refresh(self) -> None:
        ports_dict = {port: port for port in DMXManager.list_dmx_ports()}
        self.osc.send_osc("/dmx/port_name/values", [str(ports_dict)])

    def request_port(self, port: Optional[str]) -> None:
        """Record the desired DMX port. Safe to call from any thread (OSC
        handlers). The change is applied on the compute-loop thread by
        tick_device(); passing None disconnects."""
        self.desired_port = port
        self.device_dirty = True

    def tick_device(self) -> None:
        """Reconcile the DMX device once per compute tick. Compute thread."""
        self.apply_pending()
        if (
            self.auto_reconnect
            and self.enttec_pro_controller is None
            and self.desired_port not in (None, self.ART_NET_PORT)
        ):
            self.try_reconnect()

    def try_reconnect(self) -> None:
        """Retry opening a dropped enttec port. Compute thread. Gated on the
        port reappearing in the OS device list, with exponential backoff up
        to RECONNECT_BACKOFF_MAX between attempts."""
        now = time.monotonic()
        if now < self.next_reconnect_at:
            return
        port = self.desired_port
        if port is None or port not in self.list_dmx_ports():
            # Device not present yet -- wait and back off rather than churning
            # through failed open() calls on a missing port.
            self.next_reconnect_at = now + self.reconnect_backoff
            self.bump_reconnect_backoff()
            return
        if self.open_enttec(port):
            print("DMX reconnected on {}".format(port), flush=True)
            self.reconnect_backoff = self.RECONNECT_BACKOFF_START
            self.next_reconnect_at = 0.0
        else:
            self.next_reconnect_at = now + self.reconnect_backoff
            self.bump_reconnect_backoff()

    def bump_reconnect_backoff(self) -> None:
        self.reconnect_backoff = min(
            self.reconnect_backoff * 2, self.RECONNECT_BACKOFF_MAX
        )

    def apply_pending(self) -> None:
        """Apply a pending desired-port change. Compute thread only."""
        if self.device_dirty:
            self.device_dirty = False
            self.apply_desired()

    def apply_desired(self) -> None:
        """Bring the open device in line with desired_port. Compute thread."""
        port = self.desired_port
        if port == self.ART_NET_PORT:
            self.teardown_enttec()
            self.use_art_net = True
            self.active_port = port
        elif port is None:
            self.teardown_enttec()
            self.teardown_artnet_server()
            self.use_art_net = False
            self.active_port = None
            self.osc.send_osc("/dmx/port_name", [None])
        else:
            self.use_art_net = False
            self.teardown_artnet_server()
            if self.active_port != port:
                self.teardown_enttec()
            self.open_enttec(port)

    def open_enttec(self, port: str) -> bool:
        """Open the enttec controller for port. Compute thread. True on ok."""
        try:
            self.enttec_pro_controller = EnttecProController(
                port, auto_submit=False, dmx_size=self.universe_size
            )
            self.active_port = port
            self.osc.send_osc("/dmx/port_name", [port])
            return True
        except SerialException as e:
            print("DMX open failed on {}: {}".format(port, e), flush=True)
            self.enttec_pro_controller = None
            self.active_port = None
            return False

    def teardown_enttec(self) -> None:
        if self.enttec_pro_controller is not None:
            try:
                self.enttec_pro_controller.close()
            except:  # bare: best-effort close during teardown
                pass
            self.enttec_pro_controller = None

    def teardown_artnet_server(self) -> None:
        if self.art_net_server is not None:
            del self.art_net_server
            self.art_net_server = None
            self.art_net_listener_id = None

    def handle_device_fault(self) -> None:
        """A serial read/write raised. Drop the controller (compute thread)
        so the loop stops using it; desired_port is kept for reconnect."""
        self.teardown_enttec()
        self.active_port = None

    def ensure_art_net_server(self) -> None:
        if self.art_net_server is None:
            self.art_net_server = StupidArtnetServer()
            self.art_net_listener_id = self.art_net_server.register_listener(
                universe=0, sub=0, net=0, callback_function=None
            )

    def read_input_universe(self) -> List[int]:
        if self.use_art_net:
            self.ensure_art_net_server()
            if self.art_net_server is not None:
                buf = self.art_net_server.get_buffer(self.art_net_listener_id)
                if buf is None or len(buf) == 0:
                    return [0] * self.universe_size
                out = list(buf[: self.universe_size])
                if len(out) < self.universe_size:
                    out.extend([0] * (self.universe_size - len(out)))
                return out
        if self.enttec_pro_controller is not None:
            try:
                return [
                    int(self.enttec_pro_controller.get_channel(i + 1))
                    for i in range(self.universe_size)
                ]
            except (SerialException, AttributeError) as e:
                print("DMX input read failed:", e, flush=True)
                self.handle_device_fault()

        return [0] * self.universe_size

    def submit_passthrough(self) -> None:
        self.chans = self.read_input_universe()
        self.submit()

    def art_net_auto_send(self, auto):
        if auto:
            self.art_net_controller.start()
        else:
            self.art_net_controller.stop()

    def set_channel(self, chan: int, val: DMXListOrValue) -> None:
        if not isinstance(val, list):
            val = [val]

        for i, v in enumerate(val):
            v = int(constrain(v, 0, 255))

            self.chans[chan + i - 1] = v

    def submit(self) -> None:
        if self.use_art_net:
            for i, v in enumerate(self.chans):
                self.art_net_controller.set_single_value(i + 1, v)
            self.art_net_controller.show()
            return

        if self.enttec_pro_controller is None:
            return

        try:
            for i, v in enumerate(self.chans):
                self.enttec_pro_controller.set_channel(i + 1, v)
            self.enttec_pro_controller.submit()
        except SerialException as e:
            print("DMX write failed, dropping device:", e, flush=True)
            self.handle_device_fault()

    def close(self, deselect: bool = True) -> None:
        """Full teardown for shutdown. Clears the desired port so any
        auto-reconnect stops. Compute-thread / shutdown only."""
        self.use_art_net = False
        self.desired_port = None
        self.active_port = None
        self.device_dirty = False
        self.teardown_artnet_server()
        self.teardown_enttec()
        if deselect:
            self.osc.send_osc("/dmx/port_name", [None])
