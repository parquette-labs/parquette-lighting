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
from librosa import resample  # pylint: disable=no-name-in-module
from librosa.feature import melspectrogram  # pylint: disable=no-name-in-module
from librosa.beat import beat_track
from librosa.onset import onset_strength, onset_detect
from librosa.effects import hpss
import numpy as np

from ..generators import BPMGenerator, FFTGenerator
from ..osc import OSCManager, OSCParam, UIDebugFrame
from ..dmx import DMXManager
from .audio import AudioCapture


# Empirical reference for mapping the RMS-power-normalized mel spectrum into [0, 1].
# After dividing the mel power by current_rms**2 the bin scale is loudness-invariant
# but still depends on mel filter shape and A-weighting; tune by watching fft_max in
# the debug viz against typical material and adjusting until peaks sit near 1.0.
MEL_NORM_REF = 1.0


class FFTManager(object):
    bpms: List[BPMGenerator] = []
    fft_thread: Optional[Thread] = None
    fft_running: bool = False
    downstream: List[FFTGenerator] = []
    weighting = None

    def __init__(
        self,
        osc: OSCManager,
        audio_cap: AudioCapture,
        dmx: DMXManager,
        *,
        energy_threshold: float = 100.0,
        tempo_alpha: float = 0.25,
        offset_alpha: float = 0.25,
        debug_timeout: int = 2,
        rms_window_secs: float = 1.0,
        debug: bool = False,
        onset_envelope_floor: float = 2.0,
        min_business: float = 0.5,
        min_regularity: float = 0.4,
        bpm_publish_interval: float = 5.0,
    ) -> None:
        self.debug = debug
        self.onset_envelope_floor = onset_envelope_floor
        self.min_business = min_business
        self.min_regularity = min_regularity
        self.osc = osc
        self.audio_cap = audio_cap
        self.dmx = dmx
        self.n_mels = self.audio_cap.chunk // 8

        self.energy_threshold = energy_threshold
        self.tempo_alpha = tempo_alpha
        self.offset_alpha = offset_alpha
        self.rms_window_secs = rms_window_secs
        self.current_rms: float = 0.0
        self.last_beat_track_time: float = 0.0
        self.last_debug_update: float = 0.0

        self.bpm_publish_interval = bpm_publish_interval
        self.smoothed_bpm: float = 0.0
        self.smoothed_offset_time: Optional[float] = None
        self.last_bpm_publish_time: float = 0.0

        self.bpm_history_len: int = 150

        self.bpm_history: deque = deque(maxlen=self.bpm_history_len)
        self.raw_bpm_history: deque = deque(maxlen=self.bpm_history_len)
        self.rms_history: deque = deque(maxlen=self.bpm_history_len)
        self.harmonic_percussive_history: deque = deque(maxlen=self.bpm_history_len)
        self.business_history: deque = deque(maxlen=self.bpm_history_len)
        self.regularity_history: deque = deque(maxlen=self.bpm_history_len)
        self.offset_history: deque = deque(maxlen=self.bpm_history_len)

        # Incremental RMS: per-chunk sum-of-squares avoids np.concatenate every loop
        self.rms_ss: deque = deque()

        # Executor created once; stop_fft waits for in-flight future but
        # does not shut down or recreate the executor
        self._beat_executor = ThreadPoolExecutor(max_workers=1)
        self._beat_future: Optional[Future] = None

        self.uidb = UIDebugFrame(osc, "/debug/fft_frame")
        self.send_fft_debug_data = False
        self.send_fft_debug_timeout: float = 0.0
        self.debug_timeout = debug_timeout

        self.osc.dispatcher.map(
            "/audio_config/start_fft", lambda addr, args: self.start_fft()
        )
        self.osc.dispatcher.map(
            "/audio_config/stop_fft", lambda addr, args: self.stop_fft()
        )
        self.osc.dispatcher.map(
            "/visualizer/enable_fft_spectrum",
            lambda addr, *args: self.enable_fft_debug_data(bool(args[0])),
        )

    def config_params(self, osc: OSCManager) -> List[OSCParam]:
        """Preset-saved /audio_config/... binds for FFT and BPM tuning knobs."""
        return [
            OSCParam.bind(
                osc, "/audio_config/bpm_energy_threshold", self, "energy_threshold"
            ),
            OSCParam.bind(osc, "/audio_config/bpm_tempo_alpha", self, "tempo_alpha"),
            OSCParam.bind(osc, "/audio_config/bpm_offset_alpha", self, "offset_alpha"),
            OSCParam.bind(
                osc, "/audio_config/onset_envelope_floor", self, "onset_envelope_floor"
            ),
            OSCParam.bind(osc, "/audio_config/bpm_business_min", self, "min_business"),
            OSCParam.bind(
                osc, "/audio_config/bpm_regularity_min", self, "min_regularity"
            ),
        ]

    def enable_fft_debug_data(self, enable: bool) -> None:
        # Multi-client safe: only "on" heartbeats extend the gate. If we
        # honoured "off", a second UI tab whose active tab isn't FFT/DMX
        # would override the first tab's heartbeat and freeze the plots.
        # The existing debug_timeout check in run_fwd auto-closes the gate
        # ~debug_timeout seconds after the last "on" message.
        if enable:
            self.send_fft_debug_data = True
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
        # Require a full audio window before any FFT / beat-track work
        # runs. With a partially-filled window the RMS / beat tracker can
        # divide by zero (n_rms_chunks collapses to 0) and librosa emits
        # n_fft warnings on the too-short signal.
        if self.audio_cap is None or self.audio_cap.stream is None:
            return False
        return len(self.audio_cap.window) >= self.audio_cap.window_len

    def update_rms(self, win: List[np.ndarray]) -> None:
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
        self.rms_ss.append(float(np.dot(win[-1], win[-1])))
        while len(self.rms_ss) > n_rms_chunks:
            self.rms_ss.popleft()
        self.current_rms = math.sqrt(
            sum(self.rms_ss) / (len(self.rms_ss) * self.audio_cap.chunk)
        )

        self.uidb["audio_rms"] = "{rms:.2} {sign} {thres:.2}".format(
            rms=self.current_rms,
            sign="<" if self.current_rms < self.energy_threshold else ">",
            thres=self.energy_threshold,
        )

        if self.current_rms >= self.energy_threshold:
            for b in self.bpms:
                b.rms_valid = True
        else:
            for b in self.bpms:
                b.rms_valid = False
                b.bpm_valid = False
            self.uidb["reported_tempo"] = "n/a"
            self.uidb["bpm_valid"] = "n/a"

    def run_beat_track(self, win: List[np.ndarray], win_ts: List[float]) -> None:
        if not self.bpms or not self.bpms[0].rms_valid:
            return

        compute_start_time = time.monotonic()

        y = np.concatenate(win)
        sr = self.audio_cap.rate
        hop_length = 512  # librosa default

        # Compute onset envelope once; reuse for both beat_track and alignment score
        oenv = onset_strength(y=y, sr=sr)
        # Discrete onset frames, computed once and reused by the business /
        # regularity metrics below. `delta` is bumped well above the librosa
        # default (0.07) so the adaptive picker requires a larger jump above
        # the local mean — kills most of the ambient-envelope-wiggle noise.
        onset_frames = onset_detect(
            onset_envelope=oenv,
            sr=sr,
            hop_length=hop_length,
            units="frames",
        )
        reported_tempo, beat_frames = beat_track(
            onset_envelope=oenv,
            sr=sr,
            units="frames",
            start_bpm=130,
            tightness=200,
        )

        # reported_tempo = fold_tempo(float(reported_tempo))

        # Continuously update the smoothed estimate every tick so the IIR
        # dynamics are unchanged; only the publish to generators is throttled.
        self.smoothed_bpm = (
            self.tempo_alpha * float(reported_tempo)
            + (1 - self.tempo_alpha) * self.smoothed_bpm
        )

        # Offset: convert the last detected beat (frame index) back to a
        # wall-clock ms timestamp. Computed every tick so the EMA converges
        # between publishes, mirroring the BPM smoothing above.
        new_offset_time: Optional[float] = None
        if len(beat_frames) > 0 and win_ts:
            last_beat_sample = int(beat_frames[-1]) * hop_length
            samples_after = max(0, len(y) - last_beat_sample)
            end_ts = win_ts[-1]
            new_offset_time = (end_ts - samples_after / sr) * 1000.0

        if new_offset_time is not None:
            if self.smoothed_offset_time is None:
                self.smoothed_offset_time = new_offset_time
            else:
                self.smoothed_offset_time = (
                    self.offset_alpha * new_offset_time
                    + (1 - self.offset_alpha) * self.smoothed_offset_time
                )

        current_time = time.monotonic()
        if current_time - self.last_bpm_publish_time >= self.bpm_publish_interval:
            self.last_bpm_publish_time = current_time

            bpm_int = int(self.smoothed_bpm)
            for b in self.bpms:
                b.bpm = bpm_int
                if self.smoothed_offset_time is not None:
                    b.offset_time = self.smoothed_offset_time

        self.raw_bpm_history.append(float(reported_tempo))
        self.bpm_history.append(self.smoothed_bpm)
        self.offset_history.append(
            self.smoothed_offset_time if self.smoothed_offset_time is not None else 0.0
        )

        # Audio character metrics — see _compute_* helpers below.
        hp_ratio = self.compute_harmonic_percussive_ratio(y, sr)
        business, kept_onset_frames = self.compute_business(
            onset_frames, oenv, sr, hop_length
        )
        regularity = self.compute_regularity(kept_onset_frames, sr, hop_length)

        self.harmonic_percussive_history.append(hp_ratio)
        self.business_history.append(business)
        self.regularity_history.append(regularity)

        # BPM validity gate: require the last 5 ticks of business and
        # regularity to ALL pass the configured floors. Stricter than a
        # mean — a single bad tick drops the gate, so the BPM generator
        # only stays valid through sustained good audio. Raw plots stay raw.
        gate_window = 5
        recent_business_vals = list(self.business_history)[-gate_window:]
        recent_regularity_vals = list(self.regularity_history)[-gate_window:]
        business_pass = len(recent_business_vals) == gate_window and all(
            v >= self.min_business for v in recent_business_vals
        )
        regularity_pass = len(recent_regularity_vals) == gate_window and all(
            v >= self.min_regularity for v in recent_regularity_vals
        )
        bpm_valid = business_pass and regularity_pass
        for b in self.bpms:
            b.bpm_valid = bpm_valid

        compute_time = time.monotonic() - compute_start_time

        self.uidb["reported_tempo"] = reported_tempo
        self.uidb["bpm_valid"] = "b={b:.2f}{bs} r={r:.2f}{rs}".format(
            b=business,
            bs="✓" if business_pass else "✗",
            r=regularity,
            rs="✓" if regularity_pass else "✗",
        )

        self.uidb["harmonic_percussive"] = f"{hp_ratio:.2f}"
        self.uidb["business"] = f"{business:.2f}/s"
        self.uidb["regularity"] = f"{regularity:.2f}"

        self.uidb["beat_avg_time"] = (
            self.uidb["beat_avg_time"] * 0.9 + compute_time * 1000 * 0.1
        )

    def compute_harmonic_percussive_ratio(self, y: np.ndarray, sr: int) -> float:
        """
        >1 means percussive energy dominates (drums, beats),
        <1 means harmonic / sustained energy dominates (pads, vocals, ambient).

        Optimised for tick-rate compute budget:
          - operate on the last ~2 s only (local character, not whole window),
          - downsample to 8 kHz before HPSS (kicks/snares/hats are well below
            4 kHz; HPSS cost scales linearly with sample count),
          - use a smaller median kernel and STFT than librosa defaults.
        """
        tail_secs = 2.0
        tail_samples = int(tail_secs * sr)
        y_tail = y[-tail_samples:] if len(y) > tail_samples else y

        target_sr = 8000
        if sr > target_sr:
            y_tail = resample(y_tail, orig_sr=sr, target_sr=target_sr)

        # Guard against too-short tails (early ticks before the audio window
        # has filled): librosa warns when n_fft > len(y). Skip the analysis
        # and return a neutral 1.0 ratio rather than emit the warning.
        n_fft = 1024
        if len(y_tail) < n_fft:
            return 1.0

        y_h, y_p = hpss(y_tail, kernel_size=17, n_fft=n_fft)
        rms_h = float(np.sqrt(np.mean(y_h * y_h)) + 1e-9)
        rms_p = float(np.sqrt(np.mean(y_p * y_p)) + 1e-9)
        return rms_p / rms_h

    def compute_business(
        self,
        onset_frames: np.ndarray,
        oenv: np.ndarray,
        sr: int,
        hop_length: int,
    ):
        """
        Onsets per second over the analysis window, after filtering candidate
        onsets by an absolute envelope-magnitude floor to kill the onset
        picker's auto-scaling on quiet / ambient material.

        Returns (rate, kept_onset_frames) so downstream metrics (e.g.
        regularity) can consume the same filtered set.
        """
        oenv_len = len(oenv)
        if len(onset_frames) > 0:
            magnitudes = oenv[onset_frames]
            onset_frames = onset_frames[magnitudes >= self.onset_envelope_floor]

        window_secs = (oenv_len * hop_length) / sr
        if window_secs <= 0:
            return 0.0, onset_frames
        return float(len(onset_frames)) / window_secs, onset_frames

    def compute_regularity(
        self, onset_frames: np.ndarray, sr: int, hop_length: int
    ) -> float:
        """
        1.0 = perfectly periodic onsets, 0.0 = no perceivable regularity.
        Uses exp(-CV) of inter-onset intervals so the result is bounded in [0, 1].
        """
        if len(onset_frames) < 4:
            return 0.0
        times = onset_frames * hop_length / sr
        iois = np.diff(times)
        iois = iois[iois > 0]
        if len(iois) < 3:
            return 0.0
        mean_ioi = float(np.mean(iois))
        if mean_ioi <= 0:
            return 0.0
        cv = float(np.std(iois) / mean_ioi)
        return float(np.exp(-cv))

    def forward(self, chunk: np.ndarray) -> Optional[np.ndarray]:
        if not self.audio_ready():
            return None

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

    def run_fwd(self) -> None:
        self.uidb["fft_avg_time"] = 0
        self.uidb["beat_avg_time"] = 0
        debug_fft_tick = 0 if self.debug else -1

        while self.fft_running:
            # Block until the audio thread delivers a new chunk (or timeout to check
            # fft_running). This synchronises naturally to the audio hardware rate
            # (~86 Hz at chunk=512/44100 Hz) with no sleep jitter.
            if not self.audio_cap.new_chunk_event.wait(timeout=0.1):
                continue
            self.audio_cap.new_chunk_event.clear()

            # When DMX passthrough is on, dmx is being driven externally
            # and nothing the FFT analyser computes (rms, mel forward,
            # beat tracking, viz sends) has any downstream effect. Skip the
            # whole iteration to free CPU for the passthrough listener.
            if self.dmx.passthrough:
                continue

            compute_start_time = time.monotonic()

            if not self.audio_ready():
                continue

            # Stable shallow copy of the window and timestamps for this iteration.
            # Required for deque thread-safety and so the beat executor receives
            # a snapshot that won't be mutated while beat_track runs.
            win = list(self.audio_cap.window)
            win_ts = list(self.audio_cap.window_ts)

            # update_rms must run before forward() so forward() can divide by
            # the current (smoothed) rms² to make the mel output loudness-invariant.
            self.update_rms(win)
            fft_data = self.forward(win[-1])

            now = time.monotonic()
            if now - self.last_beat_track_time >= 0.2:
                if self._beat_future is None or self._beat_future.done():
                    self.last_beat_track_time = now
                    self._beat_future = self._beat_executor.submit(
                        self.run_beat_track, win, win_ts
                    )

            if fft_data is None:
                if self.debug:
                    debug_fft_tick += 1
                    if debug_fft_tick % 500 == 1:
                        print(
                            "DEBUG FFT: fft_data is None (tick {}), audio_ready={}".format(
                                debug_fft_tick, self.audio_ready()
                            ),
                            flush=True,
                        )
                continue

            for d in self.downstream:
                d.forward(fft_data, time.time() * 1000)

            if self.debug:
                debug_fft_tick += 1
                if debug_fft_tick % 500 == 1:
                    expected_ms = (
                        self.audio_cap.chunk / self.audio_cap.rate * 1000
                        if self.audio_cap.rate
                        else 0
                    )
                    print(
                        "DEBUG FFT tick {}: fft_avg={:.1f}ms "
                        "beat_avg={:.1f}ms (target=200ms) "
                        "expected={:.1f}ms fft_sum={:.4f} downstream=[{}]".format(
                            debug_fft_tick,
                            self.uidb["fft_avg_time"],
                            self.uidb["beat_avg_time"],
                            expected_ms,
                            float(np.sum(fft_data)),
                            ", ".join(
                                "{}: {:.4f}".format(d.name, d.value())
                                for d in self.downstream
                            ),
                        ),
                        flush=True,
                    )

            if (
                self.send_fft_debug_data
                and time.time() - self.send_fft_debug_timeout > self.debug_timeout
            ):
                self.send_fft_debug_data = False

            if self.send_fft_debug_data:
                max_bins = 64
                downsampled = max(1, len(fft_data) // max_bins)
                if downsampled == 1:
                    self.osc.send_osc("/visualizer/fft", fft_data.tolist())
                else:
                    n = (len(fft_data) // downsampled) * downsampled
                    banded = fft_data[:n].reshape(-1, downsampled).sum(axis=1).tolist()
                    self.osc.send_osc("/visualizer/fft", banded)

            current_time = time.monotonic()
            if current_time - self.last_debug_update >= 0.1:
                self.last_debug_update = current_time

                self.rms_history.append(self.current_rms)

                if self.send_fft_debug_data:
                    self.osc.send_osc(
                        "/visualizer/fftgen_1", self.downstream[0].value()
                    )
                    self.osc.send_osc(
                        "/visualizer/fftgen_2", self.downstream[1].value()
                    )

                    self.osc.send_osc("/visualizer/rms_history", list(self.rms_history))
                    self.osc.send_osc("/visualizer/bpm_history", list(self.bpm_history))
                    self.osc.send_osc(
                        "/visualizer/raw_bpm_history", list(self.raw_bpm_history)
                    )
                    self.osc.send_osc(
                        "/visualizer/harmonic_percussive",
                        list(self.harmonic_percussive_history),
                    )
                    self.osc.send_osc(
                        "/visualizer/business", list(self.business_history)
                    )
                    self.osc.send_osc(
                        "/visualizer/regularity", list(self.regularity_history)
                    )
                    self.osc.send_osc(
                        "/visualizer/offset_history", list(self.offset_history)
                    )

                    self.uidb.update_ui()

            compute_time = time.monotonic() - compute_start_time

            self.uidb["fft_max"] = max(fft_data)
            self.uidb["fft_min"] = min(fft_data)
            self.uidb["fft_avg_time"] = (
                self.uidb["fft_avg_time"] * 0.9 + compute_time * 1000 * 0.1
            )

    def start_fft(self) -> None:
        if self.fft_thread is not None:
            self.stop_fft()

        self.setup_fft()

        self.fft_running = True
        self.fft_thread = Thread(target=self.run_fwd)
        self.fft_thread.start()
        if self.debug:
            print(
                "DEBUG FFT: start_fft called, downstream={}, audio_cap={}".format(
                    [d.name for d in self.downstream],
                    self.audio_cap is not None,
                ),
                flush=True,
            )

    def stop_fft(self) -> None:
        self.fft_running = False

        if self.fft_thread is not None:
            self.fft_thread.join()
            self.fft_thread = None

        if self._beat_future is not None:
            self._beat_future.result()
            self._beat_future = None
