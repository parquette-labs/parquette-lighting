from typing import Optional, List, Any, Callable, Sequence

from threading import Thread

from pythonosc.dispatcher import Dispatcher, Handler
from pythonosc import osc_server
from pythonosc.udp_client import SimpleUDPClient


class OSCManager(object):
    server: osc_server.ThreadingOSCUDPServer
    server_thread: Optional[Thread] = None

    def __init__(self) -> None:
        self.dispatcher = Dispatcher()

        self.debug_osc_in = False
        self.debug_osc_out = False
        self._debug_handler: Optional[Handler] = None

    def set_debug(self, debug_osc_in: bool, debug_osc_out: bool) -> None:
        self.debug_osc_in = debug_osc_in
        self.debug_osc_out = debug_osc_out

        if debug_osc_in:
            self._debug_handler = self.dispatcher.map(
                "*", lambda addr, *args: self.print_osc(" in", addr, *args)
            )
        elif self._debug_handler is not None:
            self.dispatcher.unmap("*", self._debug_handler)

    def set_local(self, local_ip: str, local_port: int) -> None:
        self.server = osc_server.ThreadingOSCUDPServer(
            (local_ip, local_port), self.dispatcher
        )

    def set_target(self, target_ip: str, target_port: int) -> None:
        self.client = SimpleUDPClient(target_ip, target_port)

    def print_osc(self, label: str, address: str, *osc_arguments: List[Any]) -> None:
        print(label, address, osc_arguments, flush=True)

    def send_osc(self, address: str, args: Any) -> None:
        if self.debug_osc_out:
            if self.client is None:
                print("No UDP target, not sending", flush=True)
            else:
                self.print_osc("out", address, args)

        if self.client is not None:
            self.client.send_message(address, args)

    def serve(self, threaded: bool = False) -> None:
        if self.server is None:
            return

        if threaded:
            self.server_thread = Thread(target=self.server.serve_forever)
            self.server_thread.start()
        else:
            self.server.serve_forever()

    def close(self) -> None:
        if self.server is not None:
            self.server.shutdown()


class UIDebugFrame(dict):
    def __init__(self, osc: OSCManager, target_addr: str) -> None:
        self.osc = osc
        self.target_addr = target_addr

    def update_ui(self) -> None:
        self.osc.send_osc(self.target_addr, [str(self)])

    def __str__(self) -> str:
        result = ""
        for key, val in self.items():
            result += "{}: {}\n".format(key, val)
        return str(result)


class OSCParam(object):
    # pylint: disable-next=too-many-positional-arguments
    def __init__(
        self,
        osc: OSCManager,
        addr: str,
        value_lambda: Callable,
        dispatch_lambda: Callable,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        self.osc = osc
        self.addr = addr
        self.value_lambda = value_lambda
        self.on_change = on_change

        def handler(a: str, *osc_args: Any) -> None:
            dispatch_lambda(a, *osc_args)
            if self.on_change is not None:
                self.on_change()

        self.dispatch_lambda = handler
        osc.dispatcher.map(addr, handler)

    def load(self, addr: str, *osc_args: Any) -> None:
        self.dispatch_lambda(addr, *osc_args)
        self.sync()

    def sync(self) -> None:
        self.osc.send_osc(self.addr, self.value_lambda())

    @classmethod
    def bind(
        cls,
        osc: OSCManager,
        addr: str,
        target: Any,
        field: str,
        *,
        extra: Sequence[Any] = (),
        on_change: Optional[Callable[[], None]] = None,
    ) -> "OSCParam":
        """Bind an OSC address to an attribute on one or more target objects.

        Captures `target.field` for the value getter and uses
        `obj_param_setter` to write incoming values back to `target` plus any
        `extra` targets. Replaces the dominant boilerplate pattern of
        `OSCParam(osc, addr, lambda: o.f, lambda _, a: obj_param_setter(a, "f", [o]))`.
        """
        targets = [target, *extra]
        return cls(
            osc,
            addr,
            lambda: getattr(target, field),
            lambda _addr, args: cls.obj_param_setter(args, field, targets),
            on_change=on_change,
        )

    @classmethod
    def obj_param_setter(cls, value: Any, field: str, objs: List[Any]) -> None:
        for obj in objs:
            try:
                descriptor = getattr(obj.__class__, field)
                # pylint: disable-next=unnecessary-dunder-call
                descriptor.__set__(obj, value)
            except AttributeError:
                obj.__dict__[field] = value
