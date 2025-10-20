from typing import Optional, List, Any

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

    def print_osc(self, label: str, address: str, osc_arguments: List[Any]) -> None:
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
