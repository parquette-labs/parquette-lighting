from .generator import Generator


class FFTGenerator(Generator):

    def __init__(self, *, name=None, amp=1, offset=0.5, subdivisions=0, memory_length=0):
        super().__init__(name=name, amp=amp, offset=offset, period=0, phase=0)
        self.set_subdivisions_and_memory(subdivisions, memory_length)

        self.thres = 0

    def set_subdivisions_and_memory(self, subdivisions, memory_length):
        self.memory_length = memory_length
        self.subdivisions = subdivisions

        self.weighting = [0 for i in range(subdivisions)]
        self.stamps = [0 for i in range(memory_length)]
        self.memory = [[0 for i in range(subdivisions)] for j in range(memory_length)]

    def set_weighting(self, weighting):
        self.weighting = weighting.copy()

    def forward(self, values, millis):
        self.stamps[1:] = self.stamps[0:-1]
        self.stamps[0] = millis

        self.memory[1:] = self.memory_length[0:-1]

        for i in range(self.subdivisions):
            self.memory[0][i] = values[i] * self.weighting[i]

            if self.memory[0][i] < self.thres:
                self.memory[0][i] = 0
            else:
                self.memory[0][i] -= self.thres

    def value(self, millis):
        best_index = 0
        for i, _ in enumerate(self.stamps):
            best = abs(self.stamps[best_index] - millis)
            curr = abs(self.stamps[i] - millis)

            if curr < best:
                best_index = i

        fft_sum = 0
        for i in range(self.memory_length):
            fft_sum += self.memory[best_index][i]

        return fft_sum * self.amp + self.offset
