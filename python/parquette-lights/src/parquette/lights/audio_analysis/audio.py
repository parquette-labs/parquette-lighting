from typing import Optional, Mapping, cast
from collections import deque

import time
from threading import Thread, Event

import pyaudio
import numpy as np
from serial import SerialException

from ..osc import OSCManager, UIDebugFrame
from ..dmx import DMXManager


class AudioCapture(object):
    stream: Optional[pyaudio.Stream] = None
    rate: int
    chunk: int
    audio_thread: Optional[Thread] = None
    audio_running: bool = False
    window: deque
    window_ts: deque
    dmx: DMXManager  # set by server.py; loop checks dmx.passthrough to skip work

    def __init__(
        self,
        osc: OSCManager,
        chunk: int = 512,
        audio_window_secs: float = 5,
        debug: bool = False,
    ) -> None:
        self.paudio = pyaudio.PyAudio()
        self.chunk = chunk
        self.audio_window_secs = audio_window_secs
        self.debug = debug
        self.window_len = 250  # fallback until audio is configured and rate is known
        self.window = deque()
        self.window_ts = deque()
        self.new_chunk_event = Event()

        self.uidb = UIDebugFrame(osc, "/debug/audio_frame")

        self.osc = osc
        self.osc.dispatcher.map(
            "/audio_config/port_refresh",
            lambda addr, args: self.audio_port_refresh(),
        )
        self.osc.dispatcher.map(
            "/audio_config/port_name", lambda addr, args: self.setup_audio(args)
        )
        self.osc.dispatcher.map(
            "/audio_config/start_audio", lambda addr, args: self.start_audio()
        )
        self.osc.dispatcher.map(
            "/audio_config/stop_audio", lambda addr, args: self.stop_audio()
        )
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
        self.osc.send_osc("/audio_config/port_name/values", [str(port_opts)])

    def setup_audio(self, port: int) -> None:
        if port == "undefined":
            return

        self.close(deselect=False)
        try:
            port = int(port)
            port_info = self.paudio.get_device_info_by_index(port)

            self.rate = int(cast(int, port_info["defaultSampleRate"]))
            self.window_len = int(self.audio_window_secs * self.rate / self.chunk)
            self.window = deque(self.window, maxlen=self.window_len)
            self.window_ts = deque(self.window_ts, maxlen=self.window_len)

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

            self.osc.send_osc("/audio_config/port_name", [port])
        except SerialException as e:
            print(e, flush=True)
            self.close()

    def _run_capture(self) -> None:
        capture_tick = 0
        debug_interval_start = time.monotonic()
        avg_ms = 0.0

        while self.audio_running:
            try:
                if self.stream is None:
                    time.sleep(0.1)
                    continue

                iter_start = time.monotonic()
                data = self.stream.read(self.chunk, exception_on_overflow=False)

                if self.dmx is not None and self.dmx.passthrough:
                    continue

                indata = np.frombuffer(data, dtype=np.int16).astype(np.float32)

                ts = time.time()
                self.window.append(indata)
                self.window_ts.append(ts)
                self.new_chunk_event.set()

                capture_tick += 1
                iter_ms = (time.monotonic() - iter_start) * 1000
                avg_ms = avg_ms * 0.9 + iter_ms * 0.1
                self.uidb["capture_avg_time"] = avg_ms
                if self.debug and capture_tick % 500 == 0:
                    now = time.monotonic()
                    wall_avg = (now - debug_interval_start) / 500 * 1000
                    expected_ms = self.chunk / self.rate * 1000 if self.rate else 0
                    print(
                        "DEBUG audio capture tick {}: "
                        "process_avg={:.1f}ms wall_avg={:.1f}ms "
                        "expected={:.1f}ms".format(
                            capture_tick, avg_ms, wall_avg, expected_ms
                        ),
                        flush=True,
                    )
                    debug_interval_start = now

            except ValueError as e:
                print("Malformed audio buffer", e, flush=True)
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
            self.osc.send_osc("/audio_config/port_name", [None])

    def terminate(self) -> None:
        self.close()
        self.paudio.terminate()
