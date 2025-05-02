from abc import abstractclassmethod


class Generator(object):

    def __init__(self, name, amp, phase, period, offset=0.5):
        self.name = name
        self.amp = amp
        self.phase = phase
        self.period = period
        self.offset = offset

    @abstractclassmethod
    def value(self, millis):
        pass
