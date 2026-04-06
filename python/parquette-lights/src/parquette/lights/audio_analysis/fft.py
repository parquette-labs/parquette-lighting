import math
from collections import deque
from concurrent.futures import ThreadPoolExecutor, Future
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


# Empirical reference for mapping the RMS-power-normalized mel spectrum into [0, 1].
# After dividing the mel power by current_rms**2 the bin scale is loudness-invariant
# but still depends on mel filter shape and A-weighting; tune by watching fft_max in
# the debug viz against typical material and adjusting until peaks sit near 1.0.
MEL_NORM_REF = 1.0


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
        tempo_alpha: float = 0.25,
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
        self._last_viz_time: float = 0.0

        self.bpm_history_len: int = (
            600  # 1 min at 10 samples/sec (one sample per 100ms)
        )
        self.raw_bpm_metric_history_len: int = 120

        # C2: all history buffers as deques — O(1) append/eviction, no list copies
        self.bpm_history: deque = deque(maxlen=self.bpm_history_len)
        self.offset_history: deque = deque(maxlen=self.bpm_history_len)
        self.rms_history: deque = deque(maxlen=self.bpm_history_len)
        self.confidence_history: deque = deque(maxlen=self.bpm_history_len)
        # Raw (unsmoothed) histories updated at 500ms cadence (beat_track rate)
        self.raw_bpm_history: deque = deque(maxlen=self.raw_bpm_metric_history_len)
        self.alignment_conf_history: deque = deque(
            maxlen=self.raw_bpm_metric_history_len
        )
        self.stability_conf_history: deque = deque(
            maxlen=self.raw_bpm_metric_history_len
        )

        # Incremental RMS: per-chunk sum-of-squares avoids np.concatenate every loop
        self._rms_ss: deque = deque()

        # C6: executor created once here; stop_fft waits for in-flight future but
        # does not shut down or recreate the executor
        self._beat_executor = ThreadPoolExecutor(max_workers=1)
        self._beat_future: Optional[Future] = None

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

        # Incremental sum-of-squares: push new chunk, trim to window, no concatenation
        self._rms_ss.append(float(np.dot(win[-1], win[-1])))
        while len(self._rms_ss) > n_rms_chunks:
            self._rms_ss.popleft()
        self.current_rms = math.sqrt(
            sum(self._rms_ss) / (len(self._rms_ss) * self.audio_cap.chunk)
        )

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

    # C1: win_ts snapshot passed in — no longer reads live audio_cap.window_ts deque
    def _run_beat_track(self, win: List[np.ndarray], win_ts: List[float]) -> None:
        if not self.bpm.rms_valid:
            return

        compute_start_time = time.monotonic()

        end_ts = win_ts[-1]
        window_len = (
            self.audio_cap.chunk * self.audio_cap.window_len / self.audio_cap.rate
        )
        start_ts = end_ts - window_len

        y = np.concatenate(win)
        sr = self.audio_cap.rate
        hop_length = 512  # librosa default

        # Compute onset envelope once; reuse for both beat_track and alignment score
        oenv = onset_strength(y=y, sr=sr)
        reported_tempo, beat_frames = beat_track(
            onset_envelope=oenv,
            sr=sr,
            units="frames",
            start_bpm=130,
            tightness=200,
        )
        beats = beat_frames * hop_length / sr  # seconds, for phase calc
        reported_tempo = fold_tempo(float(reported_tempo))
        self.uidb["reported_tempo"] = reported_tempo

        # Track raw (unsmoothed) tempo for stability calculation
        self.raw_bpm_history.append(float(reported_tempo))

        # Option A: onset alignment
        # Onset envelope is computed independently of beat_track's forced grid.
        # Structured music: strong onsets at beat positions → ratio >> 1.
        # Ambient music: onset envelope flat relative to beats → ratio ≈ 1.
        valid_frames = beat_frames[beat_frames < len(oenv)]
        self.uidb["len_beat_frames"] = len(beat_frames)
        if len(valid_frames) > 0 and len(beat_frames) > 6:
            alignment_ratio = float(np.mean(oenv[valid_frames])) / (
                float(np.mean(oenv)) + 1e-6
            )
            alignment_conf = float(np.clip((alignment_ratio - 1.0) / 3.0, 0.0, 1.0))
        else:
            alignment_conf = 0.0

        # Option C: tempo stability
        # Arrhythmic music causes beat_track to report a different tempo each call.
        # Fold by both 2x and 1.5x before computing variance so the tracker
        # alternating between T and 1.5T (or 2T/3) does not penalise stability.
        reference = self.bpm.bpm if self.bpm.bpm > 0 else 100.0
        recent_raw = list(self.raw_bpm_history)[-5:]
        if len(recent_raw) >= 3:
            folded = [fold_tempo_for_stability(b, reference) for b in recent_raw]
            tempo_cv = float(np.std(folded) / (np.mean(folded) + 1e-6))
            stability_conf = float(np.clip(1.0 - tempo_cv * 5.0, 0.0, 1.0))
        else:
            stability_conf = 0.0  # not enough history yet

        self.alignment_conf_history.append(alignment_conf)
        self.stability_conf_history.append(stability_conf)

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

        if len(beats) > 0:
            period_ms = 1000 * 60 / float(reported_tempo)
            beat_phases = [(start_ts + float(b)) * 1000 % period_ms for b in beats]
            avg_phase = float(np.mean(beat_phases))
            # self.bpm.offset_time = (
            #     self.tempo_alpha * avg_phase
            #     + (1 - self.tempo_alpha) * self.bpm.offset_time
            # )

        compute_time = time.monotonic() - compute_start_time

        self.uidb["beat_avg_time"] = (
            self.uidb["beat_avg_time"] * 0.9 + compute_time * 1000 * 0.1
        )

    def forward(self, chunk: np.ndarray) -> Optional[np.ndarray]:
        if not self.audio_ready():
            return None

        # C3: pass power spectrum (|STFT|²) — melspectrogram(S=) expects power, not complex
        stft_mag = np.abs(stft(y=chunk, n_fft=self.audio_cap.chunk, center=False))
        fftData = melspectrogram(
            y=chunk,
            S=stft_mag**2,
            sr=self.audio_cap.rate,
            n_fft=self.audio_cap.chunk,
            center=False,
            n_mels=self.n_mels,
        )

        # Loudness-invariant: mel bins are |STFT|² so they scale with rms²;
        # divide by rms² to remove input-loudness dependence, then by an empirical
        # reference and clip to [0, 1] for downstream consumers.
        weighted = fftData[:, 0] * self.weighting
        normalized = weighted / (self.current_rms**2 + 1e-12)
        return normalized / MEL_NORM_REF

    def _run_fwd(self) -> None:
        self.uidb["fft_avg_time"] = 0
        self.uidb["beat_avg_time"] = 0

        while self.fft_running:
            # Block until the audio thread delivers a new chunk (or timeout to check
            # fft_running). This synchronises naturally to the audio hardware rate
            # (~86 Hz at chunk=512/44100 Hz) with no sleep jitter.
            if not self.audio_cap.new_chunk_event.wait(timeout=0.1):
                continue
            self.audio_cap.new_chunk_event.clear()

            compute_start_time = time.monotonic()

            if not self.audio_ready():
                continue

            # Stable shallow copy of the window and timestamps for this iteration.
            # Required for deque thread-safety and so the beat executor receives
            # a snapshot that won't be mutated while beat_track runs.
            win = list(self.audio_cap.window)
            win_ts = list(self.audio_cap.window_ts)  # C1: snapshot to avoid race

            # _update_rms must run before forward() so forward() can divide by
            # the current (smoothed) rms² to make the mel output loudness-invariant.
            self._update_rms(win)
            fft_data = self.forward(win[-1])

            now = time.monotonic()
            if now - self._last_beat_track_time >= 0.2:
                if self._beat_future is None or self._beat_future.done():
                    self._last_beat_track_time = now
                    self._beat_future = self._beat_executor.submit(
                        self._run_beat_track, win, win_ts  # C1: pass snapshot
                    )

            if fft_data is None:
                continue

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

            # C4: cap OSC payload at 64 bins; use direct tolist() when no downsampling
            if self.send_fft_debug_data:
                max_bins = 64
                downsampled = max(1, len(fft_data) // max_bins)
                if downsampled == 1:
                    self.osc.send_osc("/fft_viz", fft_data.tolist())
                else:
                    n = (len(fft_data) // downsampled) * downsampled
                    banded = fft_data[:n].reshape(-1, downsampled).sum(axis=1).tolist()
                    self.osc.send_osc("/fft_viz", banded)

            compute_time = time.monotonic() - compute_start_time

            self.uidb["fft_avg_time"] = (
                self.uidb["fft_avg_time"] * 0.9 + compute_time * 1000 * 0.1
            )

            # Wall-clock viz timer: fires every 100ms regardless of audio hardware rate
            now_viz = time.monotonic()
            if now_viz - self._last_viz_time >= 0.1:
                self._last_viz_time = now_viz

                self.bpm_history.append(self.bpm.bpm)
                self.offset_history.append(self.bpm.offset_time)
                self.rms_history.append(self.current_rms)
                self.confidence_history.append(self.bpm_confidence)

                if self.send_fft_debug_data:
                    self.osc.send_osc("/bpm_history_viz", list(self.bpm_history))
                    self.osc.send_osc("/bpm_offset_viz", list(self.offset_history))
                    self.osc.send_osc("/rms_history_viz", list(self.rms_history))
                    self.osc.send_osc(
                        "/confidence_history_viz", list(self.confidence_history)
                    )
                    self.osc.send_osc(
                        "/raw_bpm_history_viz", list(self.raw_bpm_history)
                    )
                    self.osc.send_osc(
                        "/alignment_conf_viz", list(self.alignment_conf_history)
                    )
                    self.osc.send_osc(
                        "/stability_conf_viz", list(self.stability_conf_history)
                    )
                    # C5: uidb update consolidated into wall-clock block; counter removed
                    self.uidb.update_ui()

    def start_fft(self) -> None:
        if self.fft_thread is not None:
            self.stop_fft()

        self.setup_fft()

        self.fft_running = True
        self.fft_thread = Thread(target=self._run_fwd)
        self.fft_thread.start()

    def stop_fft(self) -> None:
        self.fft_running = False
        if self.fft_thread is not None:
            self.fft_thread.join()
            self.fft_thread = None
        # C6: wait for any in-flight beat_track without shutting down the executor
        if self._beat_future is not None:
            self._beat_future.result()
            self._beat_future = None
