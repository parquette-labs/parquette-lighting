from copy import copy
from typing import Optional
from .generator import Generator
from ..util.math import constrain


class FFTGenerator(Generator):
    stamps: list[float]
    memory: list[list[float]]
    bounds: list[float]

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        amp: float = 1,
        offset: float = 0.5,
        subdivisions: int = 0,
        memory_length: int = 0
    ):
        super().__init__(name=name, amp=amp, offset=offset, period=0, phase=0)
        self.set_subdivisions_and_memory(subdivisions, memory_length)

        self.thres = 0
        self.set_bounds(0, 1)
        self.fft_bounds = [0.0, 1.0]

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

    def forward(self, values: list[float], millis: float) -> None:
        self.stamps[1:] = self.stamps[0:-1]
        self.stamps[0] = millis

        self.memory[1:] = self.memory[0:-1]

        for i in range(self.subdivisions):
            self.memory[0][i] = copy(values[i])

            if self.memory[0][i] < self.thres:
                self.memory[0][i] = 0
            else:
                self.memory[0][i] -= self.thres

    def value(self, millis: float) -> float:
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
            return 0

        return fft_sum * self.amp / (end_ix - start_ix) + self.offset
