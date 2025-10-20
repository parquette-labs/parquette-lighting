from typing import cast
from enum import Enum
from ..util.math import constrain
from ..dmx import DMXManager


class YRXY200SpotLight(object):
    # https://yuerlighting.com/product/280w-rgbw-led-moving-head-light-200w-white-21x-smd-5050-rgb-540-pan-200-tilt-for-dj-shows-weddings-church-services-events/

    class YRXY200SpotChannel(Enum):
        X_AXIS = 0
        X_AXIS_FINE = 1
        Y_AXIS = 2
        Y_AXIS_FINE = 3
        XY_SPEED = 4
        DIMMING = 5
        STROBE = 6
        COLOR = 7
        PATTERN = 8
        PRISIM = 9
        COLORFUL = 10
        SELF_PROPELLED = 11
        RESET = 12
        LIGHT_STRIP_SCENE = 13
        SCENE_SPEED = 14

    class YRXY200SpotStrobe(Enum):
        CLOSE = 0
        STROBE = 10
        OPEN = 250

    class YRXY200SpotColor(Enum):
        WHITE = 0
        COLOR_1 = 10
        COLOR_2 = 20
        COLOR_3 = 30
        COLOR_4 = 40
        COLOR_5 = 50
        COLOR_6 = 60
        COLOR_7 = 70
        HALF_COLOR_1 = 80
        HALF_COLOR_2 = 90
        HALF_COLOR_3 = 100
        HALF_COLOR_4 = 110
        HALF_COLOR_5 = 120
        HALF_COLOR_6 = 130
        REVERSE_FLOW = 140
        FORWARD_FLOW = 198

    class YRXY200SpotPattern(Enum):
        CIRCULAR_WHITE = 0
        PATTERN = 6
        PATTERN_DITHER = 72
        FORWARD_FLOW = 144
        REVERSE_FLOW = 200

    class YRXY200SpotPrisim(Enum):
        NONE = 0
        PRISIM = 100
        PRISIM_ROTATION = 128

    class YRXY200SpotColorful(Enum):
        COLORFUL_OPEN = 0
        COLORFUL_CLOSE = 127

    class YRXY200SpotSelfPropelled(Enum):
        NONE = 0
        SELF_PROPELLED = 30
        VOICE_ACTIVATED = 150

    class YRXY200SpotReset(Enum):
        NONE = 0
        X_AXIS = 21
        Y_AXIS = 101
        XY_AXIS = 201
        LAMPS = 250

    class YRXY200SpotLightRingScene(Enum):
        OFF = 0
        COLOR_SELECTION = 16
        EFFECT_SELECTION = 24
        RANDOM_SELECTION = 32

    def __init__(self, dmx: DMXManager, addr: int):
        self.dmx = dmx
        self.addr = addr

    def x(self, x: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.X_AXIS.value, x
        )

    def x_fine(self, x_fine: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.X_AXIS_FINE.value, x_fine
        )

    def y(self, y: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.Y_AXIS.value, y
        )

    def y_fine(self, y_fine: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.Y_AXIS_FINE.value, y_fine
        )

    def xy_speed(self, xy_speed: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.XY_SPEED.value, xy_speed
        )

    def dimming(self, value: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.DIMMING.value, value
        )

    def shutter_strobe(self, shutter_strobe: YRXY200SpotStrobe, rate: int = 0):
        if shutter_strobe == YRXY200SpotLight.YRXY200SpotStrobe.STROBE:
            rate = cast(int, constrain(rate, 0, 249 - 10))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.STROBE.value,
            shutter_strobe.value + rate,
        )

    def color(self, color: YRXY200SpotColor, rate: int = 0) -> None:
        if color == YRXY200SpotLight.YRXY200SpotColor.REVERSE_FLOW:
            rate = cast(int, constrain(rate, 0, 255 - 198))  # TODO from enum
        elif color == YRXY200SpotLight.YRXY200SpotColor.FORWARD_FLOW:
            rate = cast(int, constrain(rate, 0, 197 - 140))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.COLOR.value,
            color.value + rate,
        )

    def pattern(self, pattern: YRXY200SpotPattern, rate: int = 0) -> None:
        if pattern == YRXY200SpotLight.YRXY200SpotPattern.CIRCULAR_WHITE:
            rate = cast(int, constrain(rate, 0, 5))
        elif pattern == YRXY200SpotLight.YRXY200SpotPattern.PATTERN:
            rate = cast(int, constrain(rate, 0, 71 - 6))
        elif pattern == YRXY200SpotLight.YRXY200SpotPattern.PATTERN_DITHER:
            rate = cast(int, constrain(rate, 0, 143 - 72))
        elif pattern == YRXY200SpotLight.YRXY200SpotPattern.FORWARD_FLOW:
            rate = cast(int, constrain(rate, 0, 144 - 199))
        elif pattern == YRXY200SpotLight.YRXY200SpotPattern.REVERSE_FLOW:
            rate = cast(int, constrain(rate, 0, 255 - 200))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.PATTERN.value,
            pattern.value + rate,
        )

    def colorful(self, colorful: YRXY200SpotColorful) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.COLORFUL.value,
            colorful.value,
        )

    def prisim(self, prisim: YRXY200SpotPrisim, rotation: int = 0) -> None:
        # TODO bounce non enum
        if prisim == YRXY200SpotLight.YRXY200SpotPrisim.PRISIM_ROTATION:
            rotation = cast(int, constrain(rotation, 0, 255 - 192))
        else:
            rotation = 0

        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.PRISIM.value,
            prisim.value + rotation,
        )

    def self_propelled(
        self, self_propelled: YRXY200SpotSelfPropelled, rate: int = 0
    ) -> None:
        if self_propelled == YRXY200SpotLight.YRXY200SpotSelfPropelled.SELF_PROPELLED:
            rate = cast(int, constrain(rate, 0, 149 - 30))
        elif (
            self_propelled == YRXY200SpotLight.YRXY200SpotSelfPropelled.VOICE_ACTIVATED
        ):
            rate = cast(int, constrain(rate, 0, 255 - 150))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.SELF_PROPELLED.value,
            self_propelled.value + rate,
        )

    def reset(self, reset: YRXY200SpotReset) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.RESET.value, reset.value
        )

    def light_strip_scene(
        self, light_strip_scene: YRXY200SpotLightRingScene, rate: int = 0
    ) -> None:
        if (
            light_strip_scene
            == YRXY200SpotLight.YRXY200SpotLightRingScene.COLOR_SELECTION
        ):
            rate = cast(int, constrain(rate, 0, 74 - 5))
        elif (
            light_strip_scene
            == YRXY200SpotLight.YRXY200SpotLightRingScene.EFFECT_SELECTION
        ):
            rate = cast(int, constrain(rate, 0, 248 - 75))
        elif (
            light_strip_scene
            == YRXY200SpotLight.YRXY200SpotLightRingScene.RANDOM_SELECTION
        ):
            rate = cast(int, constrain(rate, 0, 255 - 249))
        else:
            rate = 0

        self.dmx.set_channel(
            YRXY200SpotLight.YRXY200SpotChannel.LIGHT_STRIP_SCENE.value,
            light_strip_scene.value + rate,
        )

    def scene_speed(self, scene_speed):
        self.dmx.set_channel(
            self.addr + YRXY200SpotLight.YRXY200SpotChannel.SCENE_SPEED.value,
            scene_speed,
        )


class PinSpot(object):
    def __init__(self, dmx, addr):
        self.dmx = dmx
        self.addr = addr

    def back(self):
        self.off()

    def off(self):
        self.set(0, 0, 0, 0)

    def white(self):
        self.set(0, 0, 0, 255)

    def on(self):
        self.set(255, 255, 255, 255)

    def set(self, r, g, b, w):
        self.dmx.set_channel(0 + self.addr, 255)
        self.dmx.set_channel(1 + self.addr, r)
        self.dmx.set_channel(2 + self.addr, g)
        self.dmx.set_channel(3 + self.addr, b)
        self.dmx.set_channel(4 + self.addr, w)
        self.dmx.set_channel(5 + self.addr, 0)
