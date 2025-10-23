class RGBLight(object):
    def __init__(self, dmx, addr):
        self.dmx = dmx
        self.addr = addr

    def on(self, value=255):
        self.rgb(value, value, value)

    def off(self):
        self.rgb(0, 0, 0)

    def rgb(self, r, g, b):
        self.dmx.set_channel(self.addr, r)
        self.dmx.set_channel(1 + self.addr, g)
        self.dmx.set_channel(2 + self.addr, b)


class SingleLight(object):
    def __init__(self, dmx, addr):
        self.dmx = dmx
        self.addr = addr

    def on(self, value=255):
        self.dmx.set_channel(self.addr, value)

    def off(self):
        self.on(0)
