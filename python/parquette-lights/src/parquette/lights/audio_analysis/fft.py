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
from librosa.onset import onset_strength
import numpy as np

from ..generators import BPMGenerator, FFTGenerator
from ..osc import OSCManager, UIDebugFrame
from ..util.math import fold_tempo, fold_tempo_for_stability
from .audio import AudioCapture


class FFTManager(object):
    bpm: BPMGenerator
    fft_thread: Optional[Thread] = None
    fft_running: bool = False
    downstream: List[FFTGenerator] = []
    weighting = None

    def __init__(
        self,
        osc: OSCManager,
        audio_cap: AudioCapture,
        *,
        energy_threshold: float = 100.0,
        confidence_threshold: float = 0.4,
        tempo_alpha: float = 0.1,
        debug_timeout: int = 30,
        rms_window_secs: float = 1.0,
    ) -> None:
        self.osc = osc
        self.audio_cap = audio_cap
        self.n_mels = self.audio_cap.chunk // 8

        self.energy_threshold = energy_threshold
        self.confidence_threshold = confidence_threshold
        self.tempo_alpha = tempo_alpha
        self.rms_window_secs = rms_window_secs
        self.bpm_confidence = 0.0
        self.current_rms: float = 0.0
        self._last_beat_track_time: float = 0.0

        self.bpm_history: List[float] = []
        self.offset_history: List[float] = []
        self.rms_history: List[float] = []
        self.confidence_history: List[float] = []
        self.bpm_history_len: int = (
            600  # 1 min at 10 samples/sec (one sample per 100ms)
        )
        # Raw (unsmoothed) histories updated at 500ms cadence (beat_track rate)
        self.raw_bpm_history: List[float] = []
        self.alignment_conf_history: List[float] = []
        self.stability_conf_history: List[float] = []
        self.raw_bpm_history_len: int = 120  # 1 min at 500ms cadence
        self.bpm_viz_counter: int = 0

        self.uidb = UIDebugFrame(osc, "/fft_debug_frame")
        self.send_fft_debug_data = False
        self.send_fft_debug_timeout: float = 0.0
        self.debug_timeout = debug_timeout

        self.osc.dispatcher.map("/start_fft", lambda addr, args: self.start_fft())
        self.osc.dispatcher.map("/stop_fft", lambda addr, args: self.stop_fft())
        self.osc.dispatcher.map(
            "/set_fft_viz",
            lambda addr, *args: self.enable_fft_debug_data(bool(args[0])),
        )

    def enable_fft_debug_data(self, enable: bool) -> None:
        self.send_fft_debug_data = enable
        self.send_fft_debug_timeout = time.time()

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
            if self.send_fft_debug_data:
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

    def _update_rms(self, win: List[np.ndarray]) -> None:
        if not self.audio_ready():
            return

        n_rms_chunks = min(
            len(win) - 1,
            max(
                1,
                int(self.rms_window_secs * self.audio_cap.rate / self.audio_cap.chunk),
            ),
        )
        rms_data = np.concatenate(win[-n_rms_chunks:])
        self.current_rms = float(np.sqrt(np.mean(rms_data**2)))

        self.uidb["audio_rms"] = "{rms:.2} {sign} {thres:.2}".format(
            rms=self.current_rms,
            sign="<" if self.current_rms < self.energy_threshold else ">",
            thres=self.energy_threshold,
        )

        if self.current_rms >= self.energy_threshold:
            self.bpm.rms_valid = True
        else:
            self.bpm.rms_valid = False
            self.bpm_confidence = 0.0
            self.uidb["reported_tempo"] = "n/a"
            self.uidb["bpm_confidence"] = "n/a"

    def _run_beat_track(self, win: List[np.ndarray]) -> None:
        if not self.bpm.rms_valid:
            return

        win_ts = self.audio_cap.window_ts
        end_ts = win_ts[-1]
        window_len = (
            self.audio_cap.chunk * self.audio_cap.window_len / self.audio_cap.rate
        )
        start_ts = end_ts - window_len

        y = np.concatenate(win)
        sr = self.audio_cap.rate
        hop_length = 512  # librosa default

        reported_tempo, beat_frames = beat_track(
            y=y,
            sr=sr,
            units="frames",
            start_bpm=130,
            tightness=200,
        )
        beats = beat_frames * hop_length / sr  # seconds, for phase calc
        reported_tempo = fold_tempo(reported_tempo)
        self.uidb["reported_tempo"] = reported_tempo

        # Track raw (unsmoothed) tempo for stability calculation
        self.raw_bpm_history.append(float(reported_tempo))
        if len(self.raw_bpm_history) > self.raw_bpm_history_len:
            self.raw_bpm_history = self.raw_bpm_history[-self.raw_bpm_history_len :]

        # Option A: onset alignment
        # Onset envelope is computed independently of beat_track's forced grid.
        # Structured music: strong onsets at beat positions → ratio >> 1.
        # Ambient music: onset envelope flat relative to beats → ratio ≈ 1.
        oenv = onset_strength(y=y, sr=sr, hop_length=hop_length)
        valid_frames = beat_frames[beat_frames < len(oenv)]
        if len(valid_frames) > 0:
            alignment_ratio = float(np.mean(oenv[valid_frames])) / (
                float(np.mean(oenv)) + 1e-6
            )
            alignment_conf = float(np.clip((alignment_ratio - 1.0) / 3.0, 0.0, 1.0))
        else:
            alignment_conf = 0.0

        # Option C: tempo stability
        # Arrhythmic music causes beat_track to report a different tempo each call.
        # Use last 5 raw readings (~2.5s at 500ms cadence) — unsmoothed so variance
        # reflects actual detection instability, not EMA lag.
        # Fold by both 2x and 1.5x before computing variance so the tracker
        # alternating between T and 1.5T (or 2T/3) does not penalise stability.
        reference = self.bpm.bpm if self.bpm.bpm > 0 else 100.0
        recent_raw = self.raw_bpm_history[-5:]
        if len(recent_raw) >= 3:
            folded = [fold_tempo_for_stability(b, reference) for b in recent_raw]
            tempo_cv = float(np.std(folded) / (np.mean(folded) + 1e-6))
            stability_conf = float(np.clip(1.0 - tempo_cv * 5.0, 0.0, 1.0))
        else:
            stability_conf = 0.0  # not enough history yet

        self.alignment_conf_history.append(alignment_conf)
        if len(self.alignment_conf_history) > self.raw_bpm_history_len:
            self.alignment_conf_history = self.alignment_conf_history[
                -self.raw_bpm_history_len :
            ]

        self.stability_conf_history.append(stability_conf)
        if len(self.stability_conf_history) > self.raw_bpm_history_len:
            self.stability_conf_history = self.stability_conf_history[
                -self.raw_bpm_history_len :
            ]

        # Both must independently pass
        self.bpm_confidence = min(alignment_conf, stability_conf)
        self.bpm.bpm_valid = self.bpm_confidence >= self.confidence_threshold
        self.uidb["bpm_confidence"] = "{bpm:.2} {sign} {thres:.2}".format(
            bpm=self.bpm_confidence,
            sign=">" if self.bpm.bpm_valid else "<",
            thres=self.confidence_threshold,
        )

        if self.bpm.bpm > 0:
            self.bpm.bpm = (
                self.tempo_alpha * float(reported_tempo)
                + (1 - self.tempo_alpha) * self.bpm.bpm
            )
        else:
            self.bpm.bpm = float(reported_tempo)

        if len(beats) > 0:
            period_ms = 1000 * 60 / float(reported_tempo)
            beat_phases = [(start_ts + float(b)) * 1000 % period_ms for b in beats]
            avg_phase = float(np.mean(beat_phases))
            self.bpm.offset_time = (
                self.tempo_alpha * avg_phase
                + (1 - self.tempo_alpha) * self.bpm.offset_time
            )

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

            # Single atomic read of the window for consistent state across both calls
            win = self.audio_cap.window

            fft_data = self.forward()
            self._update_rms(win)

            now = time.time()
            if now - self._last_beat_track_time >= 0.5:
                self._last_beat_track_time = now
                self._run_beat_track(win)

            if fft_data is None:
                time.sleep(0.1)
                continue

            fft_data = fft_data.clip(0, np.inf)

            for d in self.downstream:
                d.forward(fft_data, time.time() * 1000)

            if (
                self.send_fft_debug_data
                and time.time() - self.send_fft_debug_timeout > self.debug_timeout
            ):
                self.send_fft_debug_data = False

            if self.send_fft_debug_data:
                self.osc.send_osc("/fftgen_1_viz", self.downstream[0].value())
                self.osc.send_osc("/fftgen_2_viz", self.downstream[1].value())

            self.uidb["fft_max"] = max(fft_data)
            self.uidb["fft_min"] = min(fft_data)

            downsampled = 1
            if self.send_fft_debug_data and fft_data is not None:
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

            self.bpm_viz_counter += 1
            if self.bpm_viz_counter >= 10:  # every ~100ms
                self.bpm_viz_counter = 0

                self.bpm_history.append(self.bpm.bpm)
                if len(self.bpm_history) > self.bpm_history_len:
                    self.bpm_history = self.bpm_history[-self.bpm_history_len :]

                self.offset_history.append(self.bpm.offset_time)
                if len(self.offset_history) > self.bpm_history_len:
                    self.offset_history = self.offset_history[-self.bpm_history_len :]

                self.rms_history.append(self.current_rms)
                if len(self.rms_history) > self.bpm_history_len:
                    self.rms_history = self.rms_history[-self.bpm_history_len :]

                self.confidence_history.append(self.bpm_confidence)
                if len(self.confidence_history) > self.bpm_history_len:
                    self.confidence_history = self.confidence_history[
                        -self.bpm_history_len :
                    ]

                if self.send_fft_debug_data:
                    self.osc.send_osc("/bpm_history_viz", self.bpm_history)
                    self.osc.send_osc("/bpm_offset_viz", self.offset_history)
                    self.osc.send_osc("/rms_history_viz", self.rms_history)
                    self.osc.send_osc(
                        "/confidence_history_viz", self.confidence_history
                    )
                    self.osc.send_osc("/raw_bpm_history_viz", self.raw_bpm_history)
                    self.osc.send_osc(
                        "/alignment_conf_viz", self.alignment_conf_history
                    )
                    self.osc.send_osc(
                        "/stability_conf_viz", self.stability_conf_history
                    )

            counter += 1
            if counter % 100 == 0 and self.send_fft_debug_data:
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
