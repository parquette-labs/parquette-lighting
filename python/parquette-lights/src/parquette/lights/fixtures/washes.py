class RGBWash(object):
    def __init__(self, dmx, addr):
        self.dmx = dmx
        self.addr = addr

    def back(self):
        self.off()

    def white(self):
        self.on()

    def on(self):
        self.rgb(255, 255, 255)

    def off(self):
        self.rgb(0, 0, 0)

    def rgb(self, r, g, b):
        self.dmx.set_channel(self.addr, r)
        self.dmx.set_channel(1 + self.addr, g)
        self.dmx.set_channel(2 + self.addr, b)
