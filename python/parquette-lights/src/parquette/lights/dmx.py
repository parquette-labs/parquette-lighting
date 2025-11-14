from typing import List, Union

from DMXEnttecPro import Controller as EnttecProController  # type: ignore[import-untyped]
from stupidArtnet import StupidArtnet  # type: ignore[import-untyped]

from serial import SerialException
import serial.tools.list_ports as slp

from .osc import OSCManager
from .util.math import constrain

DMXValue = Union[int, float]
DMXListOrValue = Union[List[DMXValue], DMXValue]


class DMXManager(object):
    enttec_pro_controller: EnttecProController = None
    art_net_controller: StupidArtnet = None
    use_art_net: bool = False

    def __init__(self, osc: OSCManager, art_net_ip: str) -> None:
        self.osc = osc

        self.art_net_ip = art_net_ip
        self.art_net_controller = StupidArtnet(self.art_net_ip)
        self.art_net_controller.set_simplified(False)
        self.art_net_controller.set_universe(0)
        self.art_net_controller.set_subnet(0)
        self.art_net_controller.set_net(0)

        self.osc.dispatcher.map(
            "/dmx_port_refresh", lambda addr, args: self.dmx_port_refresh()
        )
        self.osc.dispatcher.map(
            "/dmx_port_disconnect", lambda addr, args: self.close(deselect=True)
        )

        self.osc.dispatcher.map(
            "/dmx_port_name", lambda addr, args: self.setup_dmx(args)
        )
        self.close()

    @classmethod
    def list_dmx_ports(cls) -> List[str]:
        device = [
            l.device for l in slp.comports() if l.manufacturer in ("FTDI", "ENTTEC")
        ]
        device.append("art-net-node-1")
        return device

    def dmx_port_refresh(self) -> None:
        ports_dict = {port: port for port in DMXManager.list_dmx_ports()}
        self.osc.send_osc("/dmx_port_name/values", [str(ports_dict)])

    def setup_dmx(self, port: str) -> None:
        self.close(deselect=False)

        self.use_art_net = port == "art-net-node-1"

        if not self.use_art_net:
            try:
                self.enttec_pro_controller = EnttecProController(
                    port, auto_submit=False, dmx_size=256
                )
                self.osc.send_osc("/dmx_port_name", [port])
            except SerialException as e:
                print(e, flush=True)
                self.close()

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

            if self.use_art_net:
                self.art_net_controller.set_single_value(chan + i, v)
                return
            elif not self.enttec_pro_controller is None:
                try:
                    self.enttec_pro_controller.set_channel(chan + i, v)
                except SerialException:
                    self.close()

    def submit(self) -> None:
        if self.use_art_net:
            self.art_net_controller.show()
            return
        elif not self.enttec_pro_controller is None:
            try:
                self.enttec_pro_controller.submit()
            except SerialException:
                self.close()

    def close(self, deselect=True) -> None:
        self.use_art_net = False

        if not self.enttec_pro_controller is None:
            try:
                self.enttec_pro_controller.close()
            except:
                pass
            self.enttec_pro_controller = None

        if deselect:
            self.osc.send_osc("/dmx_port_name", [None])
