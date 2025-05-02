class FFTGenerator(Generator):

    def __init__(self, name, amp, subdivisions, memory_length):
        super().__init__(name, amp, 0, 0)
        self.set_memory_and_subdivisions(subdivisions, memory_length)

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

        for i in range(subdivisions):
            self.memory[0][i] = values[i] * self.weighting[i]

            if self.memory[0][i] < thres:
                self.memory[0][i] = 0
            else:
                self.memory[0][i] -= thres

    def value(self, millis):
        best_index = 0
        for i, value in enumerate(self.stamps):
            best = math.abs(self.stamps[best_index] - millis)
            curr = math.abs(self.stamps[i] - millis)

            if curr < best:
                best_index = i

        fft_sum = 0
        for i in range(self.memory_length):
            fft_sum += self.memory[best_index][i]

        return fft_sum


#   public float value(int millis) {
#     int bestIndex = -1;
#     for (int i = 0; i < stamps.length; i++) {
#         if (bestIndex == -1) {
#             bestIndex = i;
#             continue;
#         }

#         float best = p.abs(stamps[bestIndex] - millis);
#         float curr = p.abs(stamps[i] - millis);
#         if (curr < best) bestIndex = i;
#     }

#     float sum = 0.0f;
#     for (int i = 0; i < memory[0].length; i++) {
#         sum += memory[bestIndex][i];
#     }
#     return sum*amp;
#   }
# }
