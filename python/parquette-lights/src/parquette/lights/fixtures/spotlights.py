from typing import cast, List
from abc import ABC

from enum import Enum

from ..util.math import constrain, value_map
from ..dmx import DMXManager


class Spot(ABC):
    def __init__(self, dmx: DMXManager, addr: int):
        self.dmx = dmx
        self.addr = addr

        self.x_val = [0, 0]
        self.y_val = [0, 0]
        self.dimming_val = 0
        self.color_index = 0
        self.pattern_index = 0

        self.prisim_enabled = False
        self.prisim_rotation = 0

        # TODO make base methods


class YRXY200Spot(Spot):
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
        PATTERN_1 = 6
        PATTERN_2 = 12
        PATTERN_3 = 18
        PATTERN_4 = 24
        PATTERN_5 = 30
        PATTERN_6 = 36
        PATTERN_7 = 42
        PATTERN_8 = 48
        PATTERN_9 = 54
        PATTERN_10 = 60
        PATTERN_11 = 66
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
        super().__init__(dmx=dmx, addr=addr)

    def xy(self, x: int, y: int, fine=False):
        if not fine:
            self.x(x)
            self.y(y)
        else:
            self.x((x & 0xFF00) >> 8)
            self.x_fine((x & 0xFF00) >> 8)
            self.x(x & 0xFF)
            self.y_fine(y & 0xFF)

    def x(self, x: int) -> None:
        self.x_val[0] = cast(int, constrain(x, 0, 255))
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.X_AXIS.value, self.x_val[0]
        )

    def x_fine(self, x_fine: int) -> None:
        self.x_val[1] = cast(int, constrain(x_fine, 0, 255))
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.X_AXIS_FINE.value, self.x_val[1]
        )

    def y(self, y: int) -> None:
        self.y_val[0] = cast(int, constrain(y, 0, 255))
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.Y_AXIS.value, self.y_val[0]
        )

    def y_fine(self, y_fine: int) -> None:
        self.y_val[1] = cast(int, constrain(y_fine, 0, 255))
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.Y_AXIS_FINE.value, self.y_val[1]
        )

    def xy_speed(self, speed: int) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.XY_SPEED.value, speed
        )

    def dimming(self, value: int) -> None:
        self.dimming_val = cast(int, constrain(value, 0, 255))
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.DIMMING.value, self.dimming_val
        )

    def shutter(self, close_shutter: bool) -> None:
        self.strobe_enabled = False
        self.strobe_rate = 0

        if close_shutter:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.STROBE.value,
                YRXY200Spot.YRXY200Strobe.CLOSE.value,
            )
        else:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.STROBE.value,
                YRXY200Spot.YRXY200Strobe.OPEN.value,
            )

    def strobe(self, enable: bool, rate: int = 0) -> None:
        self.strobe_enabled = enable

        if not enable:
            self.shutter(False)
            return

        self.strobe_rate = cast(int, value_map(rate, 0, 255, 0, 249 - 10, True))

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.STROBE.value,
            YRXY200Spot.YRXY200Strobe.STROBE.value + self.strobe_rate,
        )

    def colors(self) -> List[YRXY200Color]:
        return [
            YRXY200Spot.YRXY200Color.WHITE,
            YRXY200Spot.YRXY200Color.COLOR_1,
            YRXY200Spot.YRXY200Color.COLOR_2,
            YRXY200Spot.YRXY200Color.COLOR_3,
            YRXY200Spot.YRXY200Color.COLOR_4,
            YRXY200Spot.YRXY200Color.COLOR_5,
            YRXY200Spot.YRXY200Color.COLOR_6,
            YRXY200Spot.YRXY200Color.COLOR_7,
            YRXY200Spot.YRXY200Color.HALF_COLOR_1,
            YRXY200Spot.YRXY200Color.HALF_COLOR_2,
            YRXY200Spot.YRXY200Color.HALF_COLOR_3,
            YRXY200Spot.YRXY200Color.HALF_COLOR_4,
            YRXY200Spot.YRXY200Color.HALF_COLOR_5,
            YRXY200Spot.YRXY200Color.HALF_COLOR_6,
        ]

    def color(self, index: int) -> None:
        self.color_index = int(constrain(index, 0, len(self.colors()) - 1))

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.COLOR.value,
            self.colors()[self.color_index].value,
        )

    def white(self) -> None:
        self.color(0)

    def rotate_color(self, forward: bool, rate: int = 0) -> None:
        if forward:
            rate = cast(int, value_map(rate, 0, 255, 0, 197 - 140, True))
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.COLOR.value,
                YRXY200Spot.YRXY200Color.FORWARD_FLOW.value + rate,
            )
        else:
            rate = cast(int, value_map(rate, 0, 255, 0, 255 - 198, True))
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.COLOR.value,
                YRXY200Spot.YRXY200Color.REVERSE_FLOW.value + rate,
            )

    def patterns(self) -> List[YRXY200Pattern]:
        return [
            YRXY200Spot.YRXY200Pattern.CIRCULAR_WHITE,
            YRXY200Spot.YRXY200Pattern.PATTERN_1,
            YRXY200Spot.YRXY200Pattern.PATTERN_2,
            YRXY200Spot.YRXY200Pattern.PATTERN_3,
            YRXY200Spot.YRXY200Pattern.PATTERN_4,
            YRXY200Spot.YRXY200Pattern.PATTERN_5,
            YRXY200Spot.YRXY200Pattern.PATTERN_6,
            YRXY200Spot.YRXY200Pattern.PATTERN_7,
            YRXY200Spot.YRXY200Pattern.PATTERN_8,
            YRXY200Spot.YRXY200Pattern.PATTERN_9,
            YRXY200Spot.YRXY200Pattern.PATTERN_10,
            YRXY200Spot.YRXY200Pattern.PATTERN_11,
        ]

    def pattern(self, index: int) -> None:
        self.pattern_index = int(constrain(index, 0, len(self.patterns()) - 1))

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.PATTERN.value,
            self.patterns()[self.pattern_index].value,
        )

    def no_pattern(self) -> None:
        self.pattern(0)

    def rotate_pattern(self, forward: bool, rate: int = 0) -> None:
        if forward:
            rate = cast(int, value_map(rate, 0, 255, 0, 144 - 199, True))

            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.PATTERN.value,
                YRXY200Spot.YRXY200Pattern.FORWARD_FLOW.value + rate,
            )
        else:
            rate = cast(int, value_map(rate, 0, 255, 0, 255 - 200, True))

            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.PATTERN.value,
                YRXY200Spot.YRXY200Pattern.REVERSE_FLOW.value + rate,
            )

    def rotate_dither(self, index: int, rate: int) -> None:
        index = int(constrain(index, 0, len(self.patterns()) - 1))
        rate = cast(int, value_map(rate, 0, 255, 0, 6, True))

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.PATTERN.value,
            YRXY200Spot.YRXY200Pattern.PATTERN_DITHER.value
            + self.patterns()[index].value
            + rate,
        )

    def colorful(self, enabled) -> None:
        # light prisim doing color diffraction
        if enabled:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.COLORFUL.value,
                YRXY200Spot.YRXY200Colorful.COLORFUL_CLOSE.value,
            )
        else:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.COLORFUL.value,
                YRXY200Spot.YRXY200Colorful.COLORFUL_OPEN.value,
            )

    def prisim(self, enable: bool, rotation: int = 0) -> None:
        self.prisim_enabled = enable
        self.prisim_rotation = rotation

        if not enable:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.PRISIM.value,
                YRXY200Spot.YRXY200Prisim.NONE.value,
            )
        elif rotation == 0:
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.PRISIM.value,
                YRXY200Spot.YRXY200Prisim.PRISIM.value,
            )
        else:
            self.prisim_rotation = cast(
                int, value_map(rotation, 0, 255, 0, 255 - 192, True)
            )
            self.dmx.set_channel(
                self.addr + YRXY200Spot.YRXY200Channel.PRISIM.value,
                YRXY200Spot.YRXY200Prisim.PRISIM_ROTATION.value + self.prisim_rotation,
            )

    def self_propelled(
        self, self_propelled: YRXY200SelfPropelled, offset: int = 0
    ) -> None:
        if self_propelled == YRXY200Spot.YRXY200SelfPropelled.SELF_PROPELLED:
            offset = cast(int, value_map(offset, 0, 255, 0, 149 - 30, True))
        elif self_propelled == YRXY200Spot.YRXY200SelfPropelled.VOICE_ACTIVATED:
            offset = cast(int, value_map(offset, 0, 255, 0, 255 - 150, True))
        else:
            offset = 0

        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.SELF_PROPELLED.value,
            self_propelled.value + offset,
        )

    def reset(self, reset: YRXY200Reset) -> None:
        self.dmx.set_channel(
            self.addr + YRXY200Spot.YRXY200Channel.RESET.value, reset.value
        )

    def light_strip_scene(
        self, light_strip_scene: YRXY200RingScene, rate: int = 0
    ) -> None:
        if light_strip_scene == YRXY200Spot.YRXY200RingScene.COLOR_SELECTION:
            rate = cast(int, value_map(rate, 0, 255, 0, 74 - 5, True))
        elif light_strip_scene == YRXY200Spot.YRXY200RingScene.EFFECT_SELECTION:
            rate = cast(int, value_map(rate, 0, 255, 0, 248 - 75, True))
        elif light_strip_scene == YRXY200Spot.YRXY200RingScene.RANDOM_SELECTION:
            rate = cast(int, value_map(rate, 0, 255, 0, 255 - 249, True))
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


class YUER150Spot(Spot):
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
        PRISIM = 128
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
        super().__init__(dmx=dmx, addr=addr)

    def xy(self, x: int, y: int, fine=False):
        if not fine:
            self.x(x)
            self.y(y)
        else:
            self.x((x & 0xFF00) >> 8)
            self.x_fine((x & 0xFF00) >> 8)
            self.x(x & 0xFF)
            self.y_fine(y & 0xFF)

    def x(self, x: int) -> None:
        self.x_val[0] = cast(int, constrain(x, 0, 255))
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.X_AXIS.value, self.x_val[0]
        )

    def x_fine(self, x_fine: int) -> None:
        self.x_val[1] = cast(int, constrain(x_fine, 0, 255))
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.X_AXIS_FINE.value, self.x_val[1]
        )

    def y(self, y: int) -> None:
        self.y_val[0] = cast(int, constrain(y, 0, 255))
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.Y_AXIS.value, self.y_val[0]
        )

    def y_fine(self, y_fine: int) -> None:
        self.y_val[1] = cast(int, constrain(y_fine, 0, 255))
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.Y_AXIS_FINE.value, self.y_val[1]
        )

    def xy_speed(self, speed: int) -> None:
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.XY_SPEED.value, speed
        )

    def dimming(self, value: int) -> None:
        self.dimming_val = cast(int, constrain(value, 0, 255))
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.DIMMING.value, value
        )

    def strobe(self, enable: bool, rate: int = 0) -> None:
        self.strobe_enabled = enable

        if not enable:
            self.dmx.set_channel(
                self.addr + YUER150Spot.YUER150Channel.STROBE.value,
                YUER150Spot.YUER150Strobe.NO_STROBE.value,
            )
            self.strobe_rate = 0
        else:
            self.strobe_rate = cast(int, value_map(rate, 0, 255, 0, 255 - 16, True))
            self.dmx.set_channel(
                self.addr + YUER150Spot.YUER150Channel.STROBE.value,
                YUER150Spot.YUER150Strobe.STROBE.value + self.strobe_rate,
            )

    def colors(self) -> List[YUER150Color]:
        return [
            YUER150Spot.YUER150Color.WHITE,
            YUER150Spot.YUER150Color.COLOR_1_RED,
            YUER150Spot.YUER150Color.COLOR_2_GREEN,
            YUER150Spot.YUER150Color.COLOR_3_BLUE,
            YUER150Spot.YUER150Color.COLOR_4_PURPLE,
            YUER150Spot.YUER150Color.COLOR_5_ORANGE,
            YUER150Spot.YUER150Color.COLOR_6_TEAL,
            YUER150Spot.YUER150Color.COLOR_7_YELLOW,
        ]

    def color(self, index: int) -> None:
        self.color_index = int(constrain(index, 0, len(self.colors()) - 1))

        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.COLOR.value,
            self.colors()[self.color_index].value,
        )

    def white(self) -> None:
        self.color(0)

    # pylint: disable-next=unused-argument
    def rotate_color(self, forward: bool, rate: int = 0) -> None:
        # no reverse flow available

        rate = cast(int, value_map(rate, 0, 255, 0, 255 - 128, True))
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.PATTERN.value,
            YUER150Spot.YUER150Color.FORWARD_FLOW.value + rate,
        )

    def patterns(self) -> List[YUER150Pattern]:
        return [
            YUER150Spot.YUER150Pattern.CIRCULAR_WHITE,
            YUER150Spot.YUER150Pattern.PATTERN_1_MUSIC,
            YUER150Spot.YUER150Pattern.PATTERN_2_ZIG,
            YUER150Spot.YUER150Pattern.PATTERN_3_CROSS,
            YUER150Spot.YUER150Pattern.PATTERN_4_FLOWER,
            YUER150Spot.YUER150Pattern.PATTERN_5_CROSS,
            YUER150Spot.YUER150Pattern.PATTERN_6_TRIDENT,
            YUER150Spot.YUER150Pattern.PATTERN_7_SMALL_FLOWER,
        ]

    def pattern(self, index: int) -> None:
        self.pattern_index = int(constrain(index, 0, len(self.patterns()) - 1))

        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.PATTERN.value,
            self.patterns()[self.pattern_index].value,
        )

    def no_pattern(self) -> None:
        self.pattern(0)

    # pylint: disable-next=unused-argument
    def rotate_pattern(self, forward: bool, rate: int = 0) -> None:
        rate = cast(int, constrain(rate, 0, 255 - 128))

        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.PATTERN.value,
            YUER150Spot.YUER150Pattern.REVERSE_FLOW.value + rate,
        )

    def prisim(self, enable: bool, rotation: int = 0) -> None:
        self.prisim_enabled = enable
        self.prisim_rotation = rotation

        if not enable:
            self.dmx.set_channel(
                self.addr + YUER150Spot.YUER150Channel.PRISIM.value,
                YUER150Spot.YUER150Prisim.NONE.value,
            )
        elif rotation == 0:
            self.dmx.set_channel(
                self.addr + YUER150Spot.YUER150Channel.PRISIM.value,
                YUER150Spot.YUER150Prisim.PRISIM.value,
            )
        else:
            self.prisim_rotation = cast(
                int, value_map(rotation, 0, 255, 0, 255 - 137, True)
            )
            self.dmx.set_channel(
                self.addr + YUER150Spot.YUER150Channel.PRISIM.value,
                YUER150Spot.YUER150Prisim.PRISIM_ROTATION.value + self.prisim_rotation,
            )

    def self_propelled(
        self, self_propelled: YUER150SelfPropelled, offset: int = 0
    ) -> None:
        if self_propelled == YUER150Spot.YUER150SelfPropelled.FAST:
            offset = cast(int, value_map(offset, 0, 255, 0, 100 - 51, True))
        elif self_propelled == YUER150Spot.YUER150SelfPropelled.SLOW:
            offset = cast(int, value_map(offset, 0, 255, 0, 200 - 101, True))
        elif self_propelled == YUER150Spot.YUER150SelfPropelled.SOUND:
            offset = cast(int, value_map(offset, 0, 255, 0, 255 - 201, True))

        else:
            offset = 0

        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.SELF_PROPELLED.value,
            self_propelled.value + offset,
        )

    def reset(self, reset: YUER150Reset) -> None:
        self.dmx.set_channel(
            self.addr + YUER150Spot.YUER150Channel.RESET.value, reset.value
        )


class PinSpot(Spot):
    def __init__(self, dmx: DMXManager, addr: int):
        super().__init__(dmx=dmx, addr=addr)

    def black(self):
        self.off()

    def off(self):
        self.rgbw(0, 0, 0, 0)

    def white(self):
        self.rgbw(0, 0, 0, 255)

    def on(self):
        self.rgbw(255, 255, 255, 255)

    def rgbw(self, r, g, b, w):
        self.dmx.set_channel(0 + self.addr, 255)
        self.dmx.set_channel(1 + self.addr, r)
        self.dmx.set_channel(2 + self.addr, g)
        self.dmx.set_channel(3 + self.addr, b)
        self.dmx.set_channel(4 + self.addr, w)
        self.dmx.set_channel(5 + self.addr, 0)
