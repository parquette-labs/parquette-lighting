from typing import Optional
from .generator import Generator


class FFTGenerator(Generator):
    weighting: list[float]
    stamps: list[float]
    memory: list[list[float]]

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

    def set_subdivisions_and_memory(
        self, subdivisions: int, memory_length: int
    ) -> None:
        self.memory_length = memory_length
        self.subdivisions = subdivisions

        self.weighting = [1 for i in range(subdivisions)]
        self.stamps = [0 for i in range(memory_length)]
        self.memory = [[0 for i in range(subdivisions)] for j in range(memory_length)]

    def set_weighting(self, weighting: list[float]) -> None:
        self.weighting = weighting.copy()

    def forward(self, values: list[float], millis: float) -> None:
        self.stamps[1:] = self.stamps[0:-1]
        self.stamps[0] = millis

        self.memory[1:] = self.memory[0:-1]

        for i in range(self.subdivisions):
            self.memory[0][i] = values[i] * self.weighting[i]

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
        for i in range(self.subdivisions):
            fft_sum += self.memory[best_index][i]

        return fft_sum * self.amp + self.offset
