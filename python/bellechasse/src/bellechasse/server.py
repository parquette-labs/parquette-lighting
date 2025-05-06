from typing import List, Any

import click

from pythonosc.dispatcher import Dispatcher
from pythonosc import osc_server
from pythonosc.udp_client import SimpleUDPClient

from DMXEnttecPro import Controller  # type: ignore[import-untyped]

import serial.tools.list_ports as slp


class OSCManager(object):
    def __init__(self) -> None:
        self.dispatcher = Dispatcher()

    def set_debug(self, debug: bool) -> None:
        self.debug = debug

        if debug:
            self._debug_handler = self.dispatcher.map(
                "*", lambda addr, args: self.print_osc(" in", addr, args)
            )
        elif not self._debug_handler is None:
            self.dispatcher.unmap("*", self._debug_handler)

    def set_local(self, local_ip: str, local_port: int) -> None:
        self.server = osc_server.ThreadingOSCUDPServer(
            (local_ip, local_port), self.dispatcher
        )

    def set_target(self, target_ip: str, target_port: int):
        self.client = SimpleUDPClient(target_ip, target_port)

    def print_osc(self, label: str, address: str, *osc_arguments: List[Any]) -> None:
        print(label, address, osc_arguments)

    def send_osc(self, address: str, args: List[Any]) -> None:
        if self.debug:
            if self.client is None:
                print("No UDP target, not sending")
            else:
                self.print_osc("out", address, args)

        if not self.client is None:
            self.client.send_message(address, args)

    def serve(self) -> None:
        if not self.server is None:
            self.server.serve_forever()


class DMXManager(object):
    def __init__(self, osc_manager) -> None:
        self.osc_manager = osc_manager
        self.osc_manager.dispatcher.map(
            "/dmx_port_refresh", lambda addr, args: self.dmx_port_refresh()
        )
        self.osc_manager.dispatcher.map(
            "/dmx_port_name", lambda addr, args: self.setup_dmx(args[0])
        )

    @classmethod
    def list_dmx_ports(cls) -> List[str]:
        return [l.device for l in slp.comports() if l.manufacturer == "FTDI"]

    def dmx_port_refresh(self) -> None:
        ports_dict = {port: port for port in DMXManager.list_dmx_ports()}
        print(ports_dict)
        self.osc_manager.send_osc("/dmx_port_name/values", ports_dict)

    def setup_dmx(self, port: str) -> None:
        self.close()
        self.controller = Controller(port, auto_submit=False, dmx_size=256)

    def close(self) -> None:
        if not self.controller is None:
            self.controller.close()


# def setup_dmx(port) -> Controller:
#     # dmx.set_channel(1, 255)  # Sets DMX channel 1 to max 255
#     # dmx.submit()  # Sends the update to the controller
#     # dmx = Controller(my_port)


@click.command()
@click.option("--local-ip", default="127.0.0.1", type=str, help="IP address")
@click.option("--local-port", default=5005, type=int, help="port")
@click.option("--target-ip", default="127.0.0.1", type=str, help="IP address")
@click.option("--target-port", default=5006, type=int, help="port")
def run(local_ip: str, local_port: int, target_ip: str, target_port: int) -> None:
    osc = OSCManager()
    osc.set_target(target_ip, target_port)
    osc.set_local(local_ip, local_port)
    osc.set_debug(True)
    DMXManager(osc)
    osc.serve()
