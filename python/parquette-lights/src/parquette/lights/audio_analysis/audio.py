from typing import Optional, List, Mapping, cast

import time
import struct

from threading import Thread

import pyaudio
import numpy as np
from serial import SerialException

from ..osc import OSCManager, UIDebugFrame


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
