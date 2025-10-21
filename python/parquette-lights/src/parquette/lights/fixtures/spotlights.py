from typing import cast
from enum import Enum
from ..util.math import constrain
from ..dmx import DMXManager


class YRXY200Spot(object):
    # https://yuerlighting.com/product/280w-rgbw-led-moving-head-light-200w-white-21x-smd-5050-rgb-540-pan-200-tilt-for-dj-shows-weddings-church-services-events/

    class YRXY200Channel(Enum):
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

    class YRXY200Strobe(Enum):
        CLOSE = 0
        STROBE = 10
        OPEN = 250

    class YRXY200Color(Enum):
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

    class YRXY200Pattern(Enum):
        CIRCULAR_WHITE = 0
        PATTERN = 6
        PATTERN_DITHER = 72
        FORWARD_FLOW = 144
        REVERSE_FLOW = 200

    class YRXY200Prisim(Enum):
        NONE = 0
        PRISIM = 100
        PRISIM_ROTATION = 128

    class YRXY200Colorful(Enum):
        COLORFUL_OPEN = 0
        COLORFUL_CLOSE = 127

    class YRXY200SelfPropelled(Enum):
        NONE = 0
        SELF_PROPELLED = 30
        VOICE_ACTIVATED = 150

    class YRXY200Reset(Enum):
        NONE = 0
        X_AXIS = 21
        Y_AXIS = 101
        XY_AXIS = 201
        LAMPS = 250

    class YRXY200RingScene(Enum):
        OFF = 0
        COLOR_SELECTION = 16
        EFFECT_SELECTION = 24
        RANDOM_SELECTION = 32

    def __init__(self, dmx: DMXManager, addr: int):
        self.dmx = dmx
        self.addr = addr

    def x(self, x: int) -> None:
        self.dmx.set_channel(self.addr + YRXY200Spot.YRXY200Channel.X_AXIS.value, x)

    def x_fine(self, x_fine: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.X_AXIS_FINE.value, x_fine
        )

    def y(self, y: int) -> None:
        self.dmx.set_channel(self.addr + YRXY200Spot.YRXY200Channel.Y_AXIS.value, y)

    def y_fine(self, y_fine: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.Y_AXIS_FINE.value, y_fine
        )

    def xy_speed(self, xy_speed: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.XY_SPEED.value, xy_speed
        )

    def dimming(self, value: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.DIMMING.value, value
        )

    def strobe(self, strobe: YRXY200Strobe, rate: int = 0):
        if strobe == YRXY200Spot.YRXY200Strobe.STROBE:
            rate = cast(int, constrain(rate, 0, 249 - 10))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.STROBE.value,
            strobe.value + rate,
        )

    def color(self, color: YRXY200Color, rate: int = 0) -> None:
        if color == YRXY200Spot.YRXY200Color.REVERSE_FLOW:
            rate = cast(int, constrain(rate, 0, 255 - 198))  # TODO from enum
        elif color == YRXY200Spot.YRXY200Color.FORWARD_FLOW:
            rate = cast(int, constrain(rate, 0, 197 - 140))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.COLOR.value,
            color.value + rate,
        )

    def pattern(self, pattern: YRXY200Pattern, rate: int = 0) -> None:
        if pattern == YRXY200Spot.YRXY200Pattern.CIRCULAR_WHITE:
            rate = cast(int, constrain(rate, 0, 5))
        elif pattern == YRXY200Spot.YRXY200Pattern.PATTERN:
            rate = cast(int, constrain(rate, 0, 71 - 6))
        elif pattern == YRXY200Spot.YRXY200Pattern.PATTERN_DITHER:
            rate = cast(int, constrain(rate, 0, 143 - 72))
        elif pattern == YRXY200Spot.YRXY200Pattern.FORWARD_FLOW:
            rate = cast(int, constrain(rate, 0, 144 - 199))
        elif pattern == YRXY200Spot.YRXY200Pattern.REVERSE_FLOW:
            rate = cast(int, constrain(rate, 0, 255 - 200))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.PATTERN.value,
            pattern.value + rate,
        )

    def colorful(self, colorful: YRXY200Colorful) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.COLORFUL.value,
            colorful.value,
        )

    def prisim(self, prisim: YRXY200Prisim, rotation: int = 0) -> None:
        # TODO bounce non enum
        if prisim == YRXY200Spot.YRXY200Prisim.PRISIM_ROTATION:
            rotation = cast(int, constrain(rotation, 0, 255 - 192))
        else:
            rotation = 0

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.PRISIM.value,
            prisim.value + rotation,
        )

    def self_propelled(
        self, self_propelled: YRXY200SelfPropelled, rate: int = 0
    ) -> None:
        if self_propelled == YRXY200Spot.YRXY200SelfPropelled.SELF_PROPELLED:
            rate = cast(int, constrain(rate, 0, 149 - 30))
        elif self_propelled == YRXY200Spot.YRXY200SelfPropelled.VOICE_ACTIVATED:
            rate = cast(int, constrain(rate, 0, 255 - 150))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.SELF_PROPELLED.value,
            self_propelled.value + rate,
        )

    def reset(self, reset: YRXY200Reset) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.RESET.value, reset.value
        )

    def light_strip_scene(
        self, light_strip_scene: YRXY200RingScene, rate: int = 0
    ) -> None:
        if light_strip_scene == YRXY200Spot.YRXY200RingScene.COLOR_SELECTION:
            rate = cast(int, constrain(rate, 0, 74 - 5))
        elif light_strip_scene == YRXY200Spot.YRXY200RingScene.EFFECT_SELECTION:
            rate = cast(int, constrain(rate, 0, 248 - 75))
        elif light_strip_scene == YRXY200Spot.YRXY200RingScene.RANDOM_SELECTION:
            rate = cast(int, constrain(rate, 0, 255 - 249))
        else:
            rate = 0

        self.dmx.set_channel(
            YRXY200Spot.YRXY200Channel.LIGHT_STRIP_SCENE.value,
            light_strip_scene.value + rate,
        )

    def scene_speed(self, scene_speed):
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.SCENE_SPEED.value,
            scene_speed,
        )


class YUER150Spot(object):
    class YUER150Channel(Enum):
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
        SELF_PROPELLED = 10
        RESET = 11

    class YUER150Strobe(Enum):
        NO_STROBE = 0
        STROBE = 16

    class YUER150Color(Enum):
        WHITE = 0
        COLOR_1_RED = 16
        COLOR_2_GREEN = 32
        COLOR_3_BLUE = 48
        COLOR_4_PURPLE = 64
        COLOR_5_ORANGE = 80
        COLOR_6_TEAL = 96
        COLOR_7_YELLOW = 112
        FORWARD_FLOW = 128

    class YUER150Pattern(Enum):
        CIRCULAR_WHITE = 0
        PATTERN_1_MUSIC = 16
        PATTERN_2_ZIG = 32
        PATTERN_3_CROSS = 48
        PATTERN_4_FLOWER = 64
        PATTERN_5_CROSS = 80
        PATTERN_6_TRIDENT = 96
        PATTERN_7_SMALL_FLOWER = 112
        REVERSE_FLOW = 128

    class YUER150Prisim(Enum):
        NONE = 0
        PRISIM = 127
        PRISIM_ROTATION = 137

    class YUER150SelfPropelled(Enum):
        NONE = 0
        FAST = 51
        SLOW = 101
        SOUND = 201

    class YUER150Reset(Enum):
        NONE = 0
        RESET = 250

    def __init__(self, dmx: DMXManager, addr: int):
        self.dmx = dmx
        self.addr = addr

    def x(self, x: int) -> None:
        self.dmx.set_channel(self.addr + YUER150Spot.YUER150Channel.X_AXIS.value, x)

    def x_fine(self, x_fine: int) -> None:
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.X_AXIS_FINE.value, x_fine
        )

    def y(self, y: int) -> None:
        self.dmx.set_channel(self.addr + YUER150Spot.YUER150Channel.Y_AXIS.value, y)

    def y_fine(self, y_fine: int) -> None:
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.Y_AXIS_FINE.value, y_fine
        )

    def xy_speed(self, xy_speed: int) -> None:
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.XY_SPEED.value, xy_speed
        )

    def dimming(self, value: int) -> None:
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.DIMMING.value, value
        )

    def strobe(self, strobe: YUER150Strobe, rate: int = 0):
        if strobe == YUER150Spot.YUER150Strobe.STROBE:
            rate = cast(int, constrain(rate, 0, 255 - 16))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.STROBE.value,
            strobe.value + rate,
        )

    def color(self, color: YUER150Color, rate: int = 0) -> None:
        if color == YUER150Spot.YUER150Color.FORWARD_FLOW:
            rate = cast(int, constrain(rate, 0, 255 - 128))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.COLOR.value,
            color.value + rate,
        )

    def pattern(self, pattern: YUER150Pattern, rate: int = 0) -> None:
        if pattern == YUER150Spot.YUER150Pattern.REVERSE_FLOW:
            rate = cast(int, constrain(rate, 0, 255 - 128))
        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.PATTERN.value,
            pattern.value + rate,
        )

    def prisim(self, prisim: YUER150Prisim, rotation: int = 0) -> None:
        if prisim == YUER150Spot.YUER150Prisim.PRISIM_ROTATION:
            rotation = cast(int, constrain(rotation, 0, 255 - 137))
        else:
            rotation = 0

        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.PRISIM.value,
            prisim.value + rotation,
        )

    def self_propelled(
        self, self_propelled: YUER150SelfPropelled, rate: int = 0
    ) -> None:
        if self_propelled == YUER150Spot.YUER150SelfPropelled.FAST:
            rate = cast(int, constrain(rate, 0, 100 - 51))
        elif self_propelled == YUER150Spot.YUER150SelfPropelled.SLOW:
            rate = cast(int, constrain(rate, 0, 200 - 101))
        elif self_propelled == YUER150Spot.YUER150SelfPropelled.SOUND:
            rate = cast(int, constrain(rate, 0, 255 - 201))

        else:
            rate = 0

        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.SELF_PROPELLED.value,
            self_propelled.value + rate,
        )

    def reset(self, reset: YUER150Reset) -> None:
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.RESET.value, reset.value
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
