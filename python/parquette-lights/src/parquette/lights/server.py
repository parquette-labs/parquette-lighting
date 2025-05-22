from typing import List, Any, Mapping, cast, Tuple, Optional
import time
from copy import copy
import math
import struct
from threading import Thread
from enum import Enum, auto

import click
import pyaudio
import numpy as np

from pythonosc.dispatcher import Dispatcher, Handler
from pythonosc import osc_server
from pythonosc.udp_client import SimpleUDPClient

from DMXEnttecPro import Controller  # type: ignore[import-untyped]

import serial.tools.list_ports as slp
from serial import SerialException

from .generators import (
    FFTGenerator,
    WaveGenerator,
    ImpulseGenerator,
    NoiseGenerator,
    Generator,
)


class OSCManager(object):
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


class DMXManager(object):
    controller: Controller = None

    def __init__(self, osc: OSCManager) -> None:
        self.osc = osc
        self.osc.dispatcher.map(
            "/dmx_port_refresh", lambda addr, args: self.dmx_port_refresh()
        )
        self.osc.dispatcher.map(
            "/dmx_port_name", lambda addr, args: self.setup_dmx(args)
        )
        self.close()

    @classmethod
    def list_dmx_ports(cls) -> List[str]:
        return [l.device for l in slp.comports() if l.manufacturer == "FTDI"]

    def dmx_port_refresh(self) -> None:
        ports_dict = {port: port for port in DMXManager.list_dmx_ports()}
        self.osc.send_osc("/dmx_port_name/values", [str(ports_dict)])

    def setup_dmx(self, port: str) -> None:
        self.close(deselect=False)

        try:
            self.controller = Controller(port, auto_submit=False, dmx_size=256)
            self.osc.send_osc("/dmx_port_name", [port])
        except SerialException as e:
            print(e)
            self.close()

    def set_channel(self, chan: int, val: int) -> None:
        if self.controller is None:
            return

        self.controller.set_channel(chan, val)

    def submit(self) -> None:
        if self.controller is None:
            return

        self.controller.submit()

    def close(self, deselect=True) -> None:
        if not self.controller is None:
            self.controller.close()

        if deselect:
            self.osc.send_osc("/dmx_port_name", [None])


class FFTManager(object):
    stream: Optional[pyaudio.Stream] = None
    rate: int
    chunk: int

    def __init__(self, osc: OSCManager, fft_per_sec: int = 30):
        self.paudio = pyaudio.PyAudio()
        self.fft_per_sec = fft_per_sec

        self.uidb = UIDebugFrame(osc, "fft_debug_frame")

        self.osc = osc
        self.osc.dispatcher.map(
            "/audio_port_refresh", lambda addr, args: self.audio_port_refresh()
        )
        self.osc.dispatcher.map(
            "/audio_port_name", lambda addr, args: self.setup_audio(args)
        )
        self.osc.dispatcher.map("/fft_test", lambda addr, args: self.test_fwd())
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
        self.osc.send_osc("/audio_port_name/values", [str(port_opts)])

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

            self.uidb["fft_channels"] = 1
            self.uidb["fft_rate"] = self.rate
            self.uidb["fft_chunk"] = self.chunk
            self.uidb["fft_resolution"] = self.rate / self.chunk
            self.uidb["fft_nyquist"] = self.rate
            self.uidb["fft_per_sec"] = self.fft_per_sec
            self.uidb.update_ui()

            self.osc.send_osc("/audio_port_name", [port])
        except SerialException as e:
            print(e)
            self.close()

    def forward(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        if self.stream is None:
            return (None, None)

        try:
            window = np.blackman(self.chunk)
            # t1 = time.time()
            data = self.stream.read(self.chunk, exception_on_overflow=False)
            waveData = struct.unpack("%dh" % (self.chunk), data)
            npArrayData = np.array(waveData)
            indata = npArrayData * window
            fftData = np.abs(np.fft.rfft(indata))
            fftTime = np.fft.rfftfreq(self.chunk, 1.0 / self.rate)
            # print("took {} ms".format((time.time() - t1) * 1000))
        except struct.error:
            print("Malformed struct")
            return (None, None)

        return (fftTime, fftData)

    def _test_fwd(self):
        while True:
            if self.stream is None:
                return
            _, fft_data = self.forward()
            downsampled = 2
            if not fft_data is None:
                banded = []
                for i in range(len(fft_data) // downsampled):
                    summation = 0
                    for j in range(min(downsampled, len(fft_data) - i * downsampled)):
                        summation += fft_data[i * downsampled + j]
                    banded.append(summation)
                self.osc.send_osc(
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
            self.osc.send_osc("/audio_port_name", [None])

    def terminate(self):
        self.close()
        self.paudio.terminate()


class Mixer(object):
    class OutputMode(Enum):
        MONO = auto()
        QUAD = auto()
        OCTO = auto()
        FWD = auto()
        BACK = auto()
        ZIG = auto()

    def __init__(
        self,
        *,
        osc: OSCManager,
        dmx: DMXManager,
        generators: List[Generator],
        channel_names: List[str],
        history_len: float,
    ):
        self.mode = Mixer.OutputMode.MONO
        self.osc = osc
        self.dmx = dmx
        self.generators = generators
        self.channel_names = channel_names
        self.num_channels = len(self.channel_names)
        # TODO control the matrix sizing in open sound control with this var?
        self.channels = [
            [0.0] * self.num_channels for _ in range(math.ceil(history_len * 1000 / 20))
        ]
        self.channel_offsets = [0.0] * self.num_channels
        self.signal_matrix = [
            [0.0] * self.num_channels for _ in range(len(self.generators))
        ]

        # TODO register for offests
        # TODO register for mixing mode
        # TODO register for master
        # TODO register for connecting matrix
        # TODO register mode

        # self.osc.dispatcher.map(
        #     "/audio_port_refresh", lambda addr, args: self.audio_port_refresh()
        # )

    def runChannelMix(self) -> None:
        self.channels[1:] = self.channels[0:-1]

        self.channels[0] = copy(self.channel_offsets)

        for gen_idx, gen_connected_chans in enumerate(self.signal_matrix):
            for chan_idx, chan_connected in enumerate(gen_connected_chans):
                self.channels[gen_idx][chan_idx] = (
                    self.generators[gen_idx].value(time.time() * 1000) * chan_connected
                )

    def runOutputMix(self) -> None:
        if self.mode == Mixer.OutputMode.MONO:
            pass
        elif self.mode == Mixer.OutputMode.QUAD:
            pass
        elif self.mode == Mixer.OutputMode.OCTO:
            pass
        elif self.mode == Mixer.OutputMode.FWD:
            pass
        elif self.mode == Mixer.OutputMode.BACK:
            pass
        elif self.mode == Mixer.OutputMode.ZIG:
            pass

    def updateDMX(self) -> None:
        pass


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
    osc.set_debug(True)
    dmx = DMXManager(osc)
    fft = FFTManager(osc)

    initialAmp: float = 100
    initialPeriod: int = 300
    initialAmpImp: float = 255
    initialAmpFFT1: float = 3
    initialAmpFFT2: float = 3
    initialImpPeriod: int = 200
    initialImpDuty: int = 100
    initialImpEcho: int = 6
    initialImpDecay: float = 0.66

    # TODO wrapper for controlling the variables via OSC

    noise1 = NoiseGenerator(
        name="Noise1", amp=initialAmp, offset=0, period=initialPeriod
    )
    noise2 = NoiseGenerator(
        name="Noise2", amp=initialAmp, offset=0, period=initialPeriod
    )
    wave1 = WaveGenerator(
        name="SIN1",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        shape=WaveGenerator.Shape.SIN,
    )
    wave2 = WaveGenerator(
        name="SQ1",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        shape=WaveGenerator.Shape.SQUARE,
    )
    wave3 = WaveGenerator(
        name="TRI1",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        shape=WaveGenerator.Shape.TRIANGLE,
    )
    impulse = ImpulseGenerator(
        name="IMP",
        amp=initialAmpImp,
        offset=0,
        period=initialImpPeriod,
        echo=initialImpEcho,
        echo_decay=initialImpDecay,
        duty=initialImpDuty,
    )

    fft1 = FFTGenerator(
        name="FFT1", amp=initialAmpFFT1, offset=0, subdivisions=1, memory_length=1
    )
    fft2 = FFTGenerator(
        name="FFT2", amp=initialAmpFFT2, offset=0, subdivisions=1, memory_length=1
    )

    generators = [
        noise1,
        noise2,
        wave1,
        wave2,
        wave3,
        impulse,
        fft1,
        fft2,
    ]

    mixer = Mixer(
        osc=osc,
        dmx=dmx,
        generators=generators,
        channel_names=[
            "chan_1",
            "chan_2",
            "chan_3",
            "chan_4",
            "chan_5",
            "chan_6",
            "chan_7",
            "chan_8",
            "chan_9",
            "chan_10",
            "chan_11",
        ],
        history_len=2,
    )

    osc.serve(threaded=False)

    while True:
        time.sleep(1)

    dmx.close()
    fft.terminate()
