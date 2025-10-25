from typing import Optional, List, Any, Callable

from threading import Thread

from pythonosc.dispatcher import Dispatcher, Handler
from pythonosc import osc_server
from pythonosc.udp_client import SimpleUDPClient


class OSCManager(object):
    server: osc_server.ThreadingOSCUDPServer
    server_thread: Optional[Thread] = None

    def __init__(self) -> None:
        self.dispatcher = Dispatcher()

        self.debug = False
        self._debug_handler: Optional[Handler] = None

    def set_debug(self, debug: bool) -> None:
        self.debug = debug

        if debug:
            self._debug_handler = self.dispatcher.map(
                "*", lambda addr, *args: self.print_osc(" in", addr, *args)
            )
        elif not self._debug_handler is None:
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
        if self.debug:
            if self.client is None:
                print("No UDP target, not sending", flush=True)
            else:
                self.print_osc("out", address, args)

        if not self.client is None:
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
        if not self.server is None:
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
    ) -> None:
        self.osc = osc
        self.addr = addr
        self.value_lambda = value_lambda
        self.dispatch_lambda = dispatch_lambda

        osc.dispatcher.map(addr, dispatch_lambda)

    def load(self, addr: str, args: Any) -> None:
        self.dispatch_lambda(addr, args)
        self.sync()

    def sync(self) -> None:
        self.osc.send_osc(self.addr, self.value_lambda())

    @classmethod
    def obj_param_setter(cls, value: Any, field: str, objs: List[Any]) -> None:
        for obj in objs:
            # TODO I assume this is hacky and can be nicer
            try:
                _field = getattr(obj.__class__, field)
                # this is some trash surely the pylint is a warning I'm doing garbage, but fix later
                # pylint: disable-next=unnecessary-dunder-call
                _field.__set__(obj, value)

            except AttributeError:
                obj.__dict__[field] = value
