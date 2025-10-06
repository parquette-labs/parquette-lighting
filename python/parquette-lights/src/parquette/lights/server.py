# pylint: disable=too-many-lines

from typing import List, Dict, Any, Mapping, cast, Optional, Union, Callable, Tuple
import sys
import time
from copy import copy
import math
import struct
from threading import Thread
import pickle
import pprint

from librosa import (
    stft,  # pylint: disable=no-name-in-module
    A_weighting,  # pylint: disable=no-name-in-module
    mel_frequencies,  # pylint: disable=no-name-in-module
    db_to_amplitude,  # pylint: disable=no-name-in-module
)  # pylint: disable=no-name-in-module
from librosa.feature import melspectrogram  # pylint: disable=no-name-in-module
from librosa.beat import beat_track
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
    BPMGenerator,
    Generator,
)

from .util.math import constrain


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


class DMXManager(object):
    controller: Controller = None

    def __init__(self, osc: OSCManager) -> None:
        self.osc = osc
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
        return [
            l.device for l in slp.comports() if l.manufacturer in ("FTDI", "ENTTEC")
        ]

    def dmx_port_refresh(self) -> None:
        ports_dict = {port: port for port in DMXManager.list_dmx_ports()}
        self.osc.send_osc("/dmx_port_name/values", [str(ports_dict)])

    def setup_dmx(self, port: str) -> None:
        self.close(deselect=False)

        try:
            self.controller = Controller(port, auto_submit=False, dmx_size=256)
            self.osc.send_osc("/dmx_port_name", [port])
        except SerialException as e:
            print(e, flush=True)
            self.close()

    def set_channel(
        self, chan: int, val: Union[int, float], clamp: bool = True
    ) -> None:
        if self.controller is None:
            return

        if clamp:
            val = int(constrain(val, 0, 255))

        try:
            self.controller.set_channel(chan, val)
        except SerialException:
            self.close()

    def submit(self) -> None:
        if self.controller is None:
            return

        try:
            self.controller.submit()
        except SerialException:
            self.close()

    def close(self, deselect=True) -> None:
        if not self.controller is None:
            try:
                self.controller.close()
            except:
                pass
            self.controller = None

        if deselect:
            self.osc.send_osc("/dmx_port_name", [None])


class AudioCapture(object):
    stream: Optional[pyaudio.Stream] = None
    rate: int
    chunk: int
    audio_thread: Optional[Thread] = None
    audio_running: bool = False
    window: List[np.ndarray] = []
    window_ts: List[float] = []

    def __init__(
        self, osc: OSCManager, chunk: int = 512, window_len: int = 250
    ) -> None:
        self.paudio = pyaudio.PyAudio()
        self.chunk = chunk
        self.window_len = window_len

        self.uidb = UIDebugFrame(osc, "/audio_debug_frame")

        self.osc = osc
        self.osc.dispatcher.map(
            "/audio_port_refresh", lambda addr, args: self.audio_port_refresh()
        )
        self.osc.dispatcher.map(
            "/audio_port_name", lambda addr, args: self.setup_audio(args)
        )
        self.osc.dispatcher.map("/start_audio", lambda addr, args: self.start_audio())
        self.osc.dispatcher.map("/stop_audio", lambda addr, args: self.stop_audio())
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
        if port == "undefined":
            return

        self.close(deselect=False)
        try:
            port = int(port)
            port_info = self.paudio.get_device_info_by_index(port)

            self.rate = int(cast(int, port_info["defaultSampleRate"]))

            self.stream = self.paudio.open(
                format=pyaudio.paInt16,
                input_device_index=port,
                channels=1,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
            )

            self.uidb["audio_channels"] = 1
            self.uidb["audio_rate"] = self.rate
            self.uidb["audio_chunk"] = self.chunk
            self.uidb["audio_resolution"] = self.rate / self.chunk
            self.uidb["audio_nyquist"] = self.rate / 2
            self.uidb.update_ui()

            self.osc.send_osc("/audio_port_name", [port])
        except SerialException as e:
            print(e, flush=True)
            self.close()

    def _run_capture(self) -> None:
        while self.audio_running:
            try:
                if self.stream is None:
                    self.audio_running = False
                    return

                data = self.stream.read(self.chunk, exception_on_overflow=False)
                waveData = struct.unpack("%dh" % (self.chunk), data)
                indata = np.array(waveData).astype(float)

                if len(self.window) < self.window_len:
                    self.window.append(indata)
                    self.window_ts.append(time.time())
                else:
                    self.window[0:-1] = self.window[1:]
                    self.window[-1] = indata

                    self.window_ts[0:-1] = self.window_ts[1:]
                    self.window_ts[-1] = time.time()

            except struct.error as e:
                print("Malformed struct", e, flush=True)
            except OSError as e:
                print("OSError your stream died", e, flush=True)

    def start_audio(self) -> None:
        if not self.audio_thread is None:
            self.stop_audio()

        self.audio_running = True
        self.audio_thread = Thread(target=self._run_capture)
        self.audio_thread.start()

    def stop_audio(self) -> None:
        self.audio_running = False
        if not self.audio_thread is None:
            self.audio_thread.join()

    def close(self, deselect=True) -> None:
        self.stop_audio()

        if not self.stream is None:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass

        if deselect:
            self.osc.send_osc("/audio_port_name", [None])

    def terminate(self) -> None:
        self.close()
        self.paudio.terminate()


class FFTManager(object):
    bpm: BPMGenerator
    fft_thread: Optional[Thread] = None
    fft_running: bool = False
    downstream: List[FFTGenerator] = []
    weighting = None

    def __init__(self, osc: OSCManager, audio_cap: AudioCapture) -> None:
        self.osc = osc
        self.audio_cap = audio_cap
        self.n_mels = self.audio_cap.chunk // 8

        self.uidb = UIDebugFrame(osc, "/fft_debug_frame")

        self.osc.dispatcher.map("/start_fft", lambda addr, args: self.start_fft())
        self.osc.dispatcher.map("/stop_fft", lambda addr, args: self.stop_fft())

    def setup_fft(self) -> None:
        if self.audio_cap is None or self.audio_cap.stream is None:
            return

        self.stop_fft()
        try:
            self.weighting = db_to_amplitude(
                A_weighting(
                    mel_frequencies(self.n_mels, fmin=0, fmax=self.audio_cap.rate / 2)
                )
            )

            for d in self.downstream:
                d.set_subdivisions_and_memory(self.n_mels, d.memory_length)

            self.uidb["mels"] = self.n_mels
            self.uidb.update_ui()
        except SerialException as e:
            print(e, flush=True)
            self.stop_fft()

    def audio_ready(self) -> bool:
        return not (
            self.audio_cap is None
            or self.audio_cap.stream is None
            or len(self.audio_cap.window) == 0
        )

    def beat_calc(self):
        if not self.audio_ready():
            return

        end_ts = self.audio_cap.window_ts[-1]
        window_len = (
            self.audio_cap.chunk * self.audio_cap.window_len / self.audio_cap.rate
        )
        start_ts = end_ts - window_len

        full_data = np.concatenate(self.audio_cap.window)

        reported_tempo, beats = beat_track(
            y=full_data,
            sr=self.audio_cap.rate,
            units="time",
            start_bpm=130,
            tightness=800,
        )
        self.uidb["reported_tempo"] = reported_tempo

        self.bpm.bpm = reported_tempo

        if len(beats) > 0:
            self.bpm.set_offset_time((start_ts + beats[0]) * 1000)

    def forward(self) -> Optional[np.ndarray]:
        if not self.audio_ready():
            return None

        fftData = stft(
            y=self.audio_cap.window[-1], n_fft=self.audio_cap.chunk, center=False
        )
        fftData = np.abs(
            melspectrogram(
                y=self.audio_cap.window[-1],
                S=fftData,
                sr=self.audio_cap.rate,
                n_fft=self.audio_cap.chunk,
                center=False,
                n_mels=self.n_mels,
            )
        )

        return fftData[:, 0] * self.weighting

    def _run_fwd(self) -> None:
        self.uidb["fft_avg_time"] = 0
        counter = 0

        while self.fft_running:
            t1 = time.time()

            if not self.audio_ready():
                time.sleep(0.1)
                continue

            fft_data = self.forward()

            if counter % 200 == 0:
                self.beat_calc()

            if fft_data is None:
                time.sleep(0.1)
                continue

            fft_data = fft_data.clip(0, np.inf)

            for d in self.downstream:
                d.forward(fft_data, time.time() * 1000)

            self.osc.send_osc("/fftgen_1_viz", self.downstream[0].value())
            self.osc.send_osc("/fftgen_2_viz", self.downstream[1].value())

            self.uidb["fft_max"] = max(fft_data)
            self.uidb["fft_min"] = min(fft_data)

            downsampled = 1
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
            compute_time = time.time() - t1

            self.uidb["fft_avg_time"] = (
                self.uidb["fft_avg_time"] * 0.9 + compute_time * 1000 * 0.1
            )

            counter += 1
            if counter % 100 == 0:
                self.uidb.update_ui()

            if 0.01 - compute_time > 0:
                time.sleep(0.01 - compute_time)

    def start_fft(self) -> None:
        if not self.fft_thread is None:
            self.stop_fft()

        self.setup_fft()

        self.fft_running = True
        self.fft_thread = Thread(target=self._run_fwd)
        self.fft_thread.start()

    def stop_fft(self) -> None:
        self.fft_running = False
        if not self.fft_thread is None:
            self.fft_thread.join()


class Mixer(object):
    def __init__(
        self,
        *,
        osc: OSCManager,
        dmx: DMXManager,
        generators: List[Generator],
        history_len: float,
    ) -> None:
        self.mode = "MONO"
        self.osc = osc
        self.dmx = dmx
        self.generators = generators
        self.channel_names: List[str] = [
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
            "under_1",
            "under_2",
            "chan_spot",
            "sodium",
            "ceil_1",
            "ceil_2",
            "ceil_3",
        ]
        self.num_channels = len(self.channel_names)

        self.dmx_mappings = {
            "left": [4, 3, 2, 1],
            "right": [5, 6, 7, 8],
            "front": [12, 9],
            "under": [10, 11],
            "spot": [13],
            "sodium": [20],
            "ceil": [18, 19, 17],
        }

        # TODO control the matrix sizing in open sound control with this var?
        # TODO this could be initialized / resetup in a subfn that can be reused if the live setup changes
        # This is an array of the output values at different time slices, the design is that each timeslice is 20ms back in time, so self.channels[timeslice][chan]
        self.channels = [
            [0.0] * self.num_channels for _ in range(math.ceil(history_len * 1000 / 20))
        ]
        # This is the default base value of each chan
        self.channel_offsets = [0.0] * self.num_channels
        # This is a matrix from the patch bay of what signals go to what chans of shape signal_matrix[num_gen][num_chan]
        self.signal_matrix = [
            [0.0] * self.num_channels for _ in range(len(self.generators))
        ]

        self.stutter_period = 500
        self.master_amp = 1
        self.wash_master = 1

    def setChannelLevel(self, chan_name: str, level: float):
        self.channel_offsets[self.channel_names.index(chan_name)] = level

    def getChannelLevel(self, chan_name: str) -> float:
        return self.channel_offsets[self.channel_names.index(chan_name)]

    def clearSignalMatrix(self) -> None:
        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.signal_matrix)):
            for chan_ix in range(len(self.signal_matrix[gen_ix])):
                self.signal_matrix[gen_ix][chan_ix] = 0

    def configureSignalMatrix(
        self, target_gen: str, target_chans: Tuple[str] | List[str]
    ) -> None:
        try:
            gen_ix = list(map(lambda gen: gen.name, self.generators)).index(target_gen)
            destinations = [
                self.channel_names.index(chan_name) for chan_name in target_chans
            ]
            for i in range(len(self.signal_matrix[gen_ix])):
                if i in destinations:
                    self.signal_matrix[gen_ix][i] = 1
                else:
                    self.signal_matrix[gen_ix][i] = 0

        except ValueError:
            print, flush = True(
                "Couldn't parse signal mapping, gen {}, chans {}".format(
                    target_gen, target_chans
                )
            )

    def runChannelMix(self) -> None:
        # slide the channel history back one timestep
        self.channels[1:] = self.channels[0:-1]

        # setup current times
        self.channels[0] = copy(self.channel_offsets)

        ts = time.time() * 1000
        for gen_idx, gen_connected_chans in enumerate(self.signal_matrix):
            for chan_idx, chan_connected in enumerate(gen_connected_chans):
                self.channels[0][chan_idx] += (
                    self.generators[gen_idx].value(ts) * chan_connected
                )

        for i, val in enumerate(self.channels[0]):
            if not self.channel_names[i] in (
                "chan_spot",
                "under_1",
                "under_2",
                "sodium",
                "ceil_1",
                "ceil_2",
                "ceil_3",
            ):
                self.channels[0][i] = val * self.master_amp

        for i, val in enumerate(self.channels[0]):
            if self.channel_names[i] in (
                "under_1",
                "under_2",
                "ceil_1",
                "ceil_2",
                "ceil_3",
            ):
                self.channels[0][i] = val * self.wash_master
        # for g in self.generators:
        #     if g.name == "bpm":
        #         print(g.value(ts), flush=True)

    def runOutputMix(self) -> None:
        self.dmx.set_channel(
            self.dmx_mappings["spot"][0],
            self.channels[0][self.channel_names.index("chan_spot")],
        )

        self.dmx.set_channel(
            self.dmx_mappings["under"][0],
            self.channels[0][self.channel_names.index("under_1")],
        )
        self.dmx.set_channel(
            self.dmx_mappings["under"][1],
            self.channels[0][self.channel_names.index("under_2")],
        )

        self.dmx.set_channel(
            self.dmx_mappings["sodium"][0],
            self.channels[0][self.channel_names.index("sodium")],
        )
        self.dmx.set_channel(
            self.dmx_mappings["ceil"][0],
            self.channels[0][self.channel_names.index("ceil_1")],
        )

        self.dmx.set_channel(
            self.dmx_mappings["ceil"][1],
            self.channels[0][self.channel_names.index("ceil_2")],
        )
        self.dmx.set_channel(
            self.dmx_mappings["ceil"][2],
            self.channels[0][self.channel_names.index("ceil_3")],
        )

        if self.mode == "MONO":
            for group, chans in self.dmx_mappings.items():
                if not group in ("spot", "under", "ceil", "sodium"):
                    for chan in chans:
                        self.dmx.set_channel(chan, self.channels[0][0])

        elif self.mode == "PENTA":
            for i, (chan_l, chan_r) in enumerate(
                zip(self.dmx_mappings["left"], self.dmx_mappings["right"])
            ):
                self.dmx.set_channel(chan_l, self.channels[0][i + 1])
                self.dmx.set_channel(chan_r, self.channels[0][i + 1])

            self.dmx.set_channel(self.dmx_mappings["front"][0], self.channels[0][0])
            self.dmx.set_channel(self.dmx_mappings["front"][1], self.channels[0][0])
        elif self.mode == "DECA":
            for i, chan in enumerate(
                self.dmx_mappings["left"]
                + self.dmx_mappings["right"]
                + self.dmx_mappings["front"]
            ):
                self.dmx.set_channel(chan, self.channels[0][i])
        elif self.mode in ("FWD", "BACK"):
            chan_zip = list(
                zip(
                    self.dmx_mappings["front"][0:1] + self.dmx_mappings["left"],
                    self.dmx_mappings["front"][1:2] + self.dmx_mappings["right"],
                )
            )
            if self.mode == "BACK":
                chan_zip = list(reversed(chan_zip))
            for i, (chan_l, chan_r) in enumerate(chan_zip):
                stutter_index = int(
                    constrain(
                        self.stutter_period * i / 10,
                        0,
                        len(self.channels) - 1,
                    )
                )
                self.dmx.set_channel(
                    chan_l,
                    int(
                        constrain(
                            self.channels[stutter_index][0],
                            0,
                            255,
                        )
                    ),
                )
                self.dmx.set_channel(
                    chan_r,
                    int(
                        constrain(
                            self.channels[stutter_index][1],
                            0,
                            255,
                        )
                    ),
                )
        elif self.mode == "ZIG":
            interleaved_chans = [
                val
                for tup in zip(
                    self.dmx_mappings["front"][0:1] + self.dmx_mappings["left"],
                    self.dmx_mappings["front"][1:2] + self.dmx_mappings["right"],
                )
                for val in tup
            ]

            for i, chan in enumerate(interleaved_chans):
                stutter_index = int(
                    constrain(
                        self.stutter_period * i / 10,
                        0,
                        len(self.channels) - 1,
                    )
                )
                self.dmx.set_channel(
                    chan,
                    int(
                        constrain(
                            self.channels[stutter_index][0],
                            0,
                            255,
                        )
                    ),
                )

    def updateDMX(self) -> None:
        self.dmx.submit()


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


class PresetManager(object):
    def __init__(
        self,
        osc: OSCManager,
        exposed_params: List[OSCParam],
        filename: str,
        debug: bool = False,
    ) -> None:
        self.osc = osc
        self.exposed_params = exposed_params
        self.filename = filename
        self.stored_presets: Dict[str, List[Tuple[str, Any]]] = {}
        self.current_preset = "default"
        self.debug = debug

        osc.dispatcher.map("/save_preset", lambda addr, args: self.save())
        osc.dispatcher.map("/clear_preset", lambda addr, args: self.clear())
        osc.dispatcher.map("/preset_selector", lambda _, args: self.select(args))

    def load(self):
        try:
            with open(self.filename, "rb") as f:
                self.stored_presets = pickle.load(f)
        # pylint: disable=broad-exception-caught
        except Exception as e:
            print("Pickle load failed, bad or missing pickle", e, flush=True)

    def clear(self) -> None:
        del self.stored_presets[self.current_preset]

        with open("./params.pickle", "wb") as f:  # type: ignore
            pickle.dump(self.stored_presets, f)

    def save(self) -> None:
        self.stored_presets[self.current_preset] = []
        for param in self.exposed_params:
            self.stored_presets[self.current_preset].append(
                (param.addr, param.value_lambda())
            )
        if self.debug:
            pprint.pp(self.stored_presets)

        with open("./params.pickle", "wb") as f:  # type: ignore
            pickle.dump(self.stored_presets, f)

    def select(self, preset_name: str) -> None:
        self.current_preset = preset_name
        if self.current_preset not in self.stored_presets.keys():
            return

        for param_preset in self.stored_presets[self.current_preset]:
            addr, value = param_preset[0], param_preset[1]
            for param in self.exposed_params:
                if param.addr == addr:
                    param.load(addr, value)


class SignalPatchParam(OSCParam):
    def __init__(
        self,
        osc: OSCManager,
        addr: str,
        mixer: Mixer,
    ) -> None:
        super().__init__(osc, addr, self.value_builder, self.dispatch_patch)
        self.mixer = mixer

    def value_builder(self) -> List[List[str]]:
        mappings: List[List[str]] = []
        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.mixer.signal_matrix)):
            gen_mapping = [self.mixer.generators[gen_ix].name]
            for chan_ix in range(len(self.mixer.signal_matrix[gen_ix])):
                if self.mixer.signal_matrix[gen_ix][chan_ix]:
                    gen_mapping.append(self.mixer.channel_names[chan_ix])
            mappings.append(gen_mapping)
        return mappings

    def load(self, addr: str, args: List[List[str]]) -> None:
        self.mixer.clearSignalMatrix()

        for conf in args:
            self.mixer.configureSignalMatrix(conf[0], cast(List[str], conf[1:]))

        self.sync()

    def dispatch_patch(self, _: str, *args):
        self.mixer.configureSignalMatrix(args[0], args[1:])

    def sync(self) -> None:
        for gen_ix in range(len(self.mixer.signal_matrix)):
            output_val = [self.mixer.generators[gen_ix].name]
            self.osc.send_osc("/signal_patchbay", output_val)

        # pylint: disable-next=consider-using-enumerate
        for gen_ix in range(len(self.mixer.signal_matrix)):
            output_val = [self.mixer.generators[gen_ix].name]
            for chan_ix in range(len(self.mixer.signal_matrix[gen_ix])):
                if self.mixer.signal_matrix[gen_ix][chan_ix]:
                    output_val.append(self.mixer.channel_names[chan_ix])

            self.osc.send_osc("/signal_patchbay", output_val)


@click.command()
@click.option("--local-ip", default="127.0.0.1", type=str, help="IP address")
@click.option("--local-port", default=5005, type=int, help="port")
@click.option("--target-ip", default="127.0.0.1", type=str, help="IP address")
@click.option("--target-port", default=5006, type=int, help="port")
@click.option("--debug", is_flag=True, default=False)
def run(
    local_ip: str, local_port: int, target_ip: str, target_port: int, debug: bool
) -> None:
    print("Setup", flush=True)

    osc = OSCManager()
    osc.set_target(target_ip, target_port)
    osc.set_local(local_ip, local_port)
    osc.set_debug(debug)
    dmx = DMXManager(osc)
    audio_capture = AudioCapture(osc)
    fft_manager = FFTManager(osc, audio_capture)

    initialAmp: float = 200
    initialPeriod: int = 3500

    noise1 = NoiseGenerator(
        name="noise_1", amp=initialAmp, offset=0, period=initialPeriod
    )
    noise2 = NoiseGenerator(
        name="noise_2", amp=initialAmp, offset=0, period=initialPeriod
    )
    wave1 = WaveGenerator(
        name="sin",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.SIN,
    )
    wave2 = WaveGenerator(
        name="square",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.SQUARE,
    )

    sq1 = WaveGenerator(
        name="sq_1",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.SQUARE,
        duty=150,
    )

    sq2 = WaveGenerator(
        name="sq_2",
        amp=initialAmp,
        period=initialPeriod,
        phase=476,
        offset=0,
        shape=WaveGenerator.Shape.SQUARE,
        duty=150,
    )

    sq3 = WaveGenerator(
        name="sq_3",
        amp=initialAmp,
        period=initialPeriod,
        phase=335,
        offset=0,
        shape=WaveGenerator.Shape.SQUARE,
        duty=150,
    )

    wave3 = WaveGenerator(
        name="triangle",
        amp=initialAmp,
        period=initialPeriod,
        phase=0,
        offset=0,
        shape=WaveGenerator.Shape.TRIANGLE,
    )
    impulse = ImpulseGenerator(
        name="impulse",
        amp=255,
        offset=0,
        period=150,
        echo=1,
        echo_decay=1,
        duty=100,
    )

    fft1 = FFTGenerator(name="fft_1", amp=1, offset=0, subdivisions=1, memory_length=20)
    fft2 = FFTGenerator(name="fft_2", amp=1, offset=0, subdivisions=1, memory_length=20)

    bpm = BPMGenerator(name="bpm", amp=255, offset=0, duty=100)

    generators = [
        noise1,
        noise2,
        wave1,
        wave2,
        wave3,
        sq1,
        sq2,
        sq3,
        impulse,
        fft1,
        fft2,
        bpm,
    ]

    fft_manager.downstream = [fft1, fft2]
    fft_manager.bpm = bpm

    mixer = Mixer(
        osc=osc,
        dmx=dmx,
        generators=generators,
        history_len=666 * 6,
    )

    def fft_dispatch_wedge(fft, args):
        if len(args) == 1:
            fft.set_bounds(args[0][0], args[0][2])
        else:
            fft.set_bounds(args[0], args[2])

    exposed_params = [
        OSCParam(
            osc,
            "/amp",
            lambda: noise1.amp,
            lambda _, args: OSCParam.obj_param_setter(
                args, "amp", [noise1, noise2, wave1, wave2, wave3, sq1, sq2, sq3]
            ),
        ),
        OSCParam(
            osc,
            "/period",
            lambda: noise1.period,
            lambda _, args: OSCParam.obj_param_setter(
                args, "period", [noise1, noise2, wave1, wave2, wave3, sq1, sq2, sq3]
            ),
        ),
        OSCParam(
            osc,
            "/fft1_amp",
            lambda: fft1.amp,
            lambda _, args: OSCParam.obj_param_setter(args, "amp", [fft1]),
        ),
        OSCParam(
            osc,
            "/fft2_amp",
            lambda: fft2.amp,
            lambda _, args: OSCParam.obj_param_setter(args, "amp", [fft2]),
        ),
        OSCParam(
            osc,
            "/impulse_amp",
            lambda: impulse.amp,
            lambda _, args: OSCParam.obj_param_setter(args, "amp", [impulse]),
        ),
        OSCParam(
            osc,
            "/impulse_period",
            lambda: impulse.period,
            lambda _, args: OSCParam.obj_param_setter(args, "period", [impulse]),
        ),
        OSCParam(
            osc,
            "/impulse_duty",
            lambda: impulse.duty,
            lambda _, args: OSCParam.obj_param_setter(args, "duty", [impulse]),
        ),
        OSCParam(
            osc,
            "/impulse_echo",
            lambda: impulse.echo,
            lambda _, args: OSCParam.obj_param_setter(args, "echo", [impulse]),
        ),
        OSCParam(
            osc,
            "/impulse_decay",
            lambda: impulse.echo_decay,
            lambda _, args: OSCParam.obj_param_setter(args, "echo_decay", [impulse]),
        ),
        OSCParam(
            osc,
            "/stutter_period",
            lambda: mixer.stutter_period,
            lambda _, args: OSCParam.obj_param_setter(args, "stutter_period", [mixer]),
        ),
        OSCParam(
            osc,
            "/master_fader",
            lambda: mixer.master_amp,
            lambda _, args: OSCParam.obj_param_setter(args, "master_amp", [mixer]),
        ),
        OSCParam(
            osc,
            "/wash_master",
            lambda: mixer.wash_master,
            lambda _, args: OSCParam.obj_param_setter(args, "wash_master", [mixer]),
        ),
        OSCParam(
            osc,
            "/mode_switch",
            lambda: mixer.mode,
            lambda _, args: OSCParam.obj_param_setter(args, "mode", [mixer]),
        ),
        OSCParam(
            osc,
            "/fft_threshold_1",
            lambda: fft1.thres,
            lambda _, args: OSCParam.obj_param_setter(args, "thres", [fft1]),
        ),
        OSCParam(
            osc,
            "/fft_threshold_2",
            lambda: fft2.thres,
            lambda _, args: OSCParam.obj_param_setter(args, "thres", [fft2]),
        ),
        OSCParam(
            osc,
            "/manual_bpm_offset",
            lambda: bpm.manual_offset,
            lambda _, args: OSCParam.obj_param_setter(args, "manual_offset", [bpm]),
        ),
        OSCParam(
            osc,
            "/bpm_mult",
            lambda: bpm.bpm_mult,
            lambda _, args: OSCParam.obj_param_setter(args, "bpm_mult", [bpm]),
        ),
        OSCParam(
            osc,
            "/bpm_duty",
            lambda: bpm.duty,
            lambda _, args: OSCParam.obj_param_setter(args, "duty", [bpm]),
        ),
        OSCParam(
            osc,
            "/bpm_amp",
            lambda: bpm.amp,
            lambda _, args: OSCParam.obj_param_setter(args, "amp", [bpm]),
        ),
        SignalPatchParam(osc, "/signal_patchbay", mixer),
        OSCParam(
            osc,
            "/fft_bounds_1",
            lambda: (fft1.fft_bounds[0], 0, fft1.fft_bounds[1], 0),
            lambda addr, *args: fft_dispatch_wedge(fft1, args),
        ),
        OSCParam(
            osc,
            "/fft_bounds_2",
            lambda: (fft2.fft_bounds[0], 0, fft2.fft_bounds[1], 0),
            lambda addr, *args: fft_dispatch_wedge(fft2, args),
        ),
    ]

    for chan_name in mixer.channel_names:
        exposed_params.append(
            OSCParam(
                osc,
                "/chan_levels/{}".format(chan_name),
                lambda chan=chan_name: mixer.getChannelLevel(chan),
                lambda addr, args: mixer.setChannelLevel(addr.split("/")[2], args),
            )
        )

    presets = PresetManager(osc, exposed_params, "params.pickle", debug)
    presets.load()
    presets.select("default")

    def send_all_params():
        for p in exposed_params:
            p.sync()
        osc.send_osc("/preset_selector", presets.current_preset)

    osc.dispatcher.map("/reload", lambda addr, args: send_all_params())
    osc.dispatcher.map(
        "/impulse_punch",
        lambda addr, *args: impulse.punch(),
    )

    print("Start OSC server", flush=True)
    osc.serve(threaded=True)

    print("Sync front end", flush=True)
    send_all_params()

    print("Start compute loop", flush=True)
    try:
        while True:
            mixer.runChannelMix()
            mixer.runOutputMix()
            mixer.updateDMX()
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nShutdown FFT", flush=True)
        fft_manager.stop_fft()
        print("Shutdown audio capture and pyaudio", flush=True)
        audio_capture.terminate()
        print("Close OSC server", flush=True)
        osc.close()
        print("Close DMX port", flush=True)
        dmx.close()

        sys.exit(0)
