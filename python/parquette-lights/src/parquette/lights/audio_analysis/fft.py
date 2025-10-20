from typing import Optional, List

from threading import Thread
import time
from serial import SerialException

from librosa import (
    stft,  # pylint: disable=no-name-in-module
    A_weighting,  # pylint: disable=no-name-in-module
    mel_frequencies,  # pylint: disable=no-name-in-module
    db_to_amplitude,  # pylint: disable=no-name-in-module
)  # pylint: disable=no-name-in-module
from librosa.feature import melspectrogram  # pylint: disable=no-name-in-module
from librosa.beat import beat_track
import numpy as np

from ..generators import BPMGenerator, FFTGenerator
from ..osc import OSCManager, UIDebugFrame
from .audio import AudioCapture


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
