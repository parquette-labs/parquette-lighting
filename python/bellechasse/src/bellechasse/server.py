from typing import List, Any, Mapping, cast, Tuple, Optional
import time
import struct
from threading import Thread

import click
import pyaudio
import numpy as np

from pythonosc.dispatcher import Dispatcher
from pythonosc import osc_server
from pythonosc.udp_client import SimpleUDPClient

from DMXEnttecPro import Controller  # type: ignore[import-untyped]

import serial.tools.list_ports as slp
from serial import SerialException


class OSCManager(object):
    server_thread: Optional[Thread] = None

    def __init__(self) -> None:
        self.dispatcher = Dispatcher()

        self.debug = False
        self._debug_handler = None

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

    def serve(self, threaded=False) -> None:
        if self.server is None:
            return

        if threaded:
            self.server_thread = Thread(target=self.server.serve_forever)
            self.server_thread.start()
        else:
            self.server.serve_forever()

    def close(self):
        if not self.server is None:
            self.server.shutdown()


class DMXManager(object):
    controller: Controller = None

    def __init__(self, osc_manager: OSCManager) -> None:
        self.osc_manager = osc_manager
        self.osc_manager.dispatcher.map(
            "/dmx_port_refresh", lambda addr, args: self.dmx_port_refresh()
        )
        self.osc_manager.dispatcher.map(
            "/dmx_port_name", lambda addr, args: self.setup_dmx(args)
        )
        self.close()

    @classmethod
    def list_dmx_ports(cls) -> List[str]:
        return [l.device for l in slp.comports() if l.manufacturer == "FTDI"]

    def dmx_port_refresh(self) -> None:
        ports_dict = {port: port for port in DMXManager.list_dmx_ports()}
        self.osc_manager.send_osc("/dmx_port_name/values", [str(ports_dict)])

    def setup_dmx(self, port: str) -> None:
        self.close(deselect=False)
        try:
            self.controller = Controller(port, auto_submit=False, dmx_size=256)
            self.osc_manager.send_osc("/dmx_port_name", [port])
        except SerialException as e:
            print(e)
            self.close()

    def close(self, deselect=True) -> None:
        if not self.controller is None:
            self.controller.close()

        if deselect:
            self.osc_manager.send_osc("/dmx_port_name", [None])


# def setup_dmx(port) -> Controller:
#     # dmx.set_channel(1, 255)  # Sets DMX channel 1 to max 255
#     # dmx.submit()  # Sends the update to the controller
#     # dmx = Controller(my_port)


class FFTManager(object):
    stream: Optional[pyaudio.Stream] = None
    rate: int
    chunk: int

    def __init__(self, osc_manager: OSCManager, fft_per_sec: int = 30):
        self.paudio = pyaudio.PyAudio()
        self.fft_per_sec = fft_per_sec

        self.osc_manager = osc_manager
        self.osc_manager.dispatcher.map(
            "/audio_port_refresh", lambda addr, args: self.audio_port_refresh()
        )
        self.osc_manager.dispatcher.map(
            "/audio_port_name", lambda addr, args: self.setup_audio(args)
        )
        self.osc_manager.dispatcher.map("/fft_test", self.test_fwd)
        self.close()

    def list_audio_ports(self) -> list[Mapping[str, str | int | float]]:
        ports = [
            self.paudio.get_device_info_by_index(i)
            for i in range(self.paudio.get_device_count())
        ]
        return ports

    def audio_port_refresh(self) -> None:
        port_opts = {
            port["name"]: i
            for i, port in enumerate(self.list_audio_ports())
            if int(port["maxInputChannels"]) > 0
        }
        self.osc_manager.send_osc("/audio_port_name/values", [str(port_opts)])

    def setup_audio(self, port: int) -> None:
        self.close(deselect=False)
        try:
            port = int(port)
            port_info = self.paudio.get_device_info_by_index(port)

            self.chunk = int(
                cast(int, port_info["defaultSampleRate"]) / self.fft_per_sec
            )
            self.rate = int(cast(int, port_info["defaultSampleRate"]))

            self.stream = self.paudio.open(
                format=pyaudio.paInt16,
                channels=1,  # todo stereo ? min(cast(int, port_info["maxInputChannels"]), 2)
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
            )

            self.osc_manager.send_osc("/audio_port_name", [port])
        except SerialException as e:
            print(e)
            self.close()

    def forward(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        if self.stream is None:
            return (None, None)

        window = np.blackman(self.chunk)
        t1 = time.time()
        data = self.stream.read(self.chunk, exception_on_overflow=False)
        waveData = struct.unpack("%dh" % (self.chunk), data)
        npArrayData = np.array(waveData)
        indata = npArrayData * window
        fftData = np.abs(np.fft.rfft(indata))
        fftTime = np.fft.rfftfreq(self.chunk, 1.0 / self.rate)
        print("took {} ms".format((time.time() - t1) * 1000))
        return (fftTime, fftData)

    def _test_fwd(self):
        while True:
            fft_time, fft_data = self.forward()
            if not fft_data is None:
                banded = []
                for i in range(len(fft_data) // 100):
                    summation = 0
                    for j in range(min(100, len(fft_data) - i * 100)):
                        summation += fft_data[i * 100 + j]
                    banded.append(summation)
                self.osc_manager.send_osc(
                    "/fft_viz",
                    banded,
                )
            time.sleep(0.02)

    def test_fwd(self):
        self.fft_thread = Thread(target=self._test_fwd)
        self.fft_thread.start()

    def close(self, deselect=True) -> None:
        if not self.stream is None:
            self.stream.stop_stream()
            self.stream.close()
            # p.terminate()

        if deselect:
            self.osc_manager.send_osc("/audio_port_name", [None])

    def terminate(self):
        self.close()
        self.paudio.terminate()


@click.command()
@click.option("--local-ip", default="127.0.0.1", type=str, help="IP address")
@click.option("--local-port", default=5005, type=int, help="port")
@click.option("--target-ip", default="127.0.0.1", type=str, help="IP address")
@click.option("--target-port", default=5006, type=int, help="port")
def run(local_ip: str, local_port: int, target_ip: str, target_port: int) -> None:
    # while True:
    #     import time, random

    #     time.sleep(0.05)
    #     osc.send_osc(
    #         "/fft_viz",
    #         str([[random.random(), random.random()] for _ in range(20)]),
    #     )

    osc = OSCManager()
    osc.set_target(target_ip, target_port)
    osc.set_local(local_ip, local_port)
    osc.set_debug(False)
    dmx = DMXManager(osc)
    fft = FFTManager(osc)

    fft.test_fwd()

    osc.serve(threaded=True)

    while True:
        time.sleep(1)

    dmx.close()
    fft.terminate()
