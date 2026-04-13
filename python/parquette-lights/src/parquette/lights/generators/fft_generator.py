import time
from copy import copy
import numpy as np
from .generator import Generator
from ..util.math import constrain


class FFTGenerator(Generator):
    stamps: list[float]
    memory: list[list[float]]
    bounds: list[float]

    def __init__(
        self,
        *,
        name: str,
        category: str,
        amp: float = 1,
        offset: float = 0.5,
        subdivisions: int = 0,
        memory_length: int = 0,
        lpf_alpha: float = 1.0,
    ):
        super().__init__(
            name=name, category=category, amp=amp, offset=offset, period=0, phase=0
        )
        self.set_subdivisions_and_memory(subdivisions, memory_length)

        self.thres = 0
        self.set_bounds(0, 1)
        self.fft_bounds = [0.0, 1.0]
        # Single-pole EMA on value() output. 1.0 = no filtering.
        self.lpf_alpha = lpf_alpha
        self._lpf_state = offset
        self.debug = False
        self.debug_fwd_tick = 0
        self.debug_val_tick = 0

    def set_bounds(self, low, high):
        low = constrain(low, 0, 1)
        high = constrain(high, 0, 1)

        if low > high:
            (low, high) = (high, low)
        self.fft_bounds = [low, high]

    def set_subdivisions_and_memory(
        self, subdivisions: int, memory_length: int
    ) -> None:
        self.memory_length = memory_length
        self.subdivisions = subdivisions

        self.stamps = [0 for i in range(memory_length)]
        self.memory = [[0 for i in range(subdivisions)] for j in range(memory_length)]

    def forward(self, values: list[float] | np.ndarray, millis: float) -> None:
        self.stamps[1:] = self.stamps[0:-1]
        self.stamps[0] = millis

        self.memory[1:] = self.memory[0:-1]

        for i in range(self.subdivisions):
            self.memory[0][i] = copy(values[i])

            if self.memory[0][i] < self.thres:
                self.memory[0][i] = 0
            else:
                self.memory[0][i] -= self.thres

        if self.debug:
            self.debug_fwd_tick += 1
            if self.debug_fwd_tick % 500 == 1:
                mem_sum = sum(self.memory[0])
                print(
                    "DEBUG {}.forward: tick={}, millis={:.0f}, subdivisions={}, "
                    "memory_length={}, memory[0] sum={:.4f}, thres={}".format(
                        self.name,
                        self.debug_fwd_tick,
                        millis,
                        self.subdivisions,
                        self.memory_length,
                        mem_sum,
                        self.thres,
                    ),
                    flush=True,
                )

    def value(self, millis: float = -1) -> float:
        if millis == -1:
            millis = time.time() * 1000

        best_index = 0
        for i, _ in enumerate(self.stamps):
            best = abs(self.stamps[best_index] - millis)
            curr = abs(self.stamps[i] - millis)

            if curr < best:
                best_index = i

        fft_sum = 0.0
        start_ix = int(
            constrain(
                int(self.fft_bounds[0] * self.subdivisions),
                0,
                len(self.memory[best_index]) - 1,
            )
        )
        end_ix = int(
            constrain(
                max(int(self.fft_bounds[1] * self.subdivisions), start_ix + 1),
                0,
                len(self.memory[best_index]) - 1,
            )
        )

        for i in range(start_ix, end_ix):
            fft_sum += self.memory[best_index][i]

        if start_ix == end_ix:
            raw = 0.0
        else:
            raw = fft_sum * self.amp / (end_ix - start_ix) + self.offset

        if self.debug:
            self.debug_val_tick += 1
            if self.debug_val_tick % 500 == 1:
                stamp_age = (
                    millis - self.stamps[best_index]
                    if self.stamps[best_index] > 0
                    else -1
                )
                print(
                    "DEBUG {}.value: tick={}, millis={:.0f}, best_index={}, "
                    "stamp_age={:.0f}ms, start_ix={}, end_ix={}, fft_sum={:.4f}, "
                    "raw={:.4f}, amp={}, offset={}, fft_bounds={}, subdivisions={}, "
                    "mem_len={}".format(
                        self.name,
                        self.debug_val_tick,
                        millis,
                        best_index,
                        stamp_age,
                        start_ix,
                        end_ix,
                        fft_sum,
                        raw,
                        self.amp,
                        self.offset,
                        self.fft_bounds,
                        self.subdivisions,
                        len(self.memory[best_index]),
                    ),
                    flush=True,
                )

        alpha = self.lpf_alpha
        if alpha >= 1.0:
            self._lpf_state = raw
        else:
            self._lpf_state = alpha * raw + (1.0 - alpha) * self._lpf_state
        return self._lpf_state
