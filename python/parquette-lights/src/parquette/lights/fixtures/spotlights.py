from typing import cast, List, Optional

from enum import Enum


from ..util.math import constrain, value_map
from .basics import LightFixture
from ..dmx import DMXManager, DMXValue, DMXControlChannel, DMXControlRange


class Spot(LightFixture):
    x_channel: DMXControlChannel
    y_channel: DMXControlChannel
    x_fine_channel: DMXControlChannel
    y_fine_channel: DMXControlChannel
    xy_speed_channel: DMXControlChannel
    dimming_channel: DMXControlChannel
    strobe_channel: DMXControlChannel
    color_channel: DMXControlChannel
    pattern_channel: DMXControlChannel
    prisim_channel: DMXControlChannel

    def __init__(self, dmx: DMXManager, *, addr: int, num_chans: int = 1):
        super().__init__(dmx, addr=addr, num_chans=num_chans)

        self._x: DMXValue = 0
        self._y: DMXValue = 0
        self._x_fine: DMXValue = 0
        self._y_fine: DMXValue = 0
        self._xy_speed: DMXValue = 0
        self._dimming: DMXValue = 0

        self.strobe_enabled: bool = False
        self._strobe_rate: DMXValue = 0

        self.color_index: int = 0

        self.pattern_index: int = 0

        self._prisim_enabled: bool = False
        self._prisim_rotation: DMXValue = 0
        self.prisim_enabled: bool = False
        self.prisim_rotation: DMXValue = 0

    def xy(self, x: int, y: int, fine=False) -> None:
        if not fine:
            self.x(x)
            self.y(y)
        else:
            self.x((x & 0xFF00) >> 8)
            self.x_fine((x & 0xFF00) >> 8)
            self.x(x & 0xFF)
            self.y_fine(y & 0xFF)

    def x(self, val: DMXValue) -> None:
        self._x = cast(DMXValue, self.x_channel.map(val))
        self.dmx.set_channel(self.addr + self.x_channel.offset, self._x)

    def x_fine(self, val: DMXValue) -> None:
        self._x_fine = cast(DMXValue, self.x_fine_channel.map(val))
        self.dmx.set_channel(self.addr + self.x_fine_channel.offset, self._x_fine)

    def y(self, val: DMXValue) -> None:
        self._y = cast(DMXValue, self.y_channel.map(val))
        self.dmx.set_channel(self.addr + self.y_channel.offset, self._y)

    def y_fine(self, val: DMXValue) -> None:
        self._y_fine = cast(DMXValue, self.y_fine_channel.map(val))
        self.dmx.set_channel(self.addr + self.y_fine_channel.offset, self._y_fine)

    def xy_speed(self, val: DMXValue) -> None:
        self._xy_speed = cast(DMXValue, self.xy_speed_channel.map(val))
        self.dmx.set_channel(self.addr + self.xy_speed_channel.offset, self._xy_speed)

    def dimming(self, val: DMXValue) -> None:
        self._dimming = cast(DMXValue, self.dimming_channel.map(val))
        self.dmx.set_channel(self.addr + self.dimming_channel.offset, self._dimming)

    def strobe(self, enable: bool, rate: Optional[int] = None) -> None:
        self.strobe_enabled = enable

        if self.strobe_enabled and not rate is None:
            self.strobe_rate(rate)
        else:
            self.dmx.set_channel(
                self.addr + self.strobe_channel.offset,
                self.strobe_channel.map(range_name="on"),
            )

    def strobe_rate(self, val: DMXValue) -> None:
        self._strobe_rate = cast(
            DMXValue, self.strobe_channel.map(val, range_name="strobe")
        )
        self.dmx.set_channel(self.addr + self.strobe_channel.offset, self._strobe_rate)

    def colors(self) -> List[str]:
        return self.color_channel.range_names()

    def color(self, index: int) -> None:
        self.color_index = int(constrain(index, 0, len(self.colors()) - 1))

        self.dmx.set_channel(
            self.addr + self.color_channel.offset,
            self.color_channel.map(range_index=self.color_index),
        )

    def white(self) -> None:
        self.color(0)

    def patterns(self) -> List[str]:
        return self.pattern_channel.range_names()

    def pattern(self, index: int) -> None:
        self.pattern_index = int(constrain(index, 0, len(self.patterns()) - 1))

        self.dmx.set_channel(
            self.addr + self.pattern_channel.offset,
            self.pattern_channel.map(range_index=self.color_index),
        )

    def no_pattern(self) -> None:
        self.pattern(0)

    def prisim(self, enable: bool, rotation: int = 0) -> None:
        self.prisim_enabled = enable
        self.prisim_rotation = self.prisim_channel.map(rotation, range_name="rotation")

        if not enable:
            self.dmx.set_channel(
                self.addr + self.prisim_channel.offset,
                self.prisim_channel.map(range_name="off"),
            )
        elif rotation == 0:
            self.dmx.set_channel(
                self.addr + self.prisim_channel.offset,
                self.prisim_channel.map(range_name="on"),
            )
        else:
            self.dmx.set_channel(
                self.addr + self.prisim_channel.offset, self.prisim_rotation
            )


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
        super().__init__(dmx=dmx, addr=addr, num_chans=15)

        self.x_channel = DMXControlChannel("x_channel", 0)
        self.y_channel = DMXControlChannel("x_fine_channel", 1)
        self.x_fine_channel = DMXControlChannel("y_channel", 2)
        self.y_fine_channel = DMXControlChannel("y_fine_channel", 3)
        self.xy_speed_channel = DMXControlChannel("xy_speed_channel", 4)
        self.dimming_channel = DMXControlChannel("dimming_channel", 5)
        self.strobe_channel = DMXControlChannel(
            "strobe_channel",
            6,
            [DMXControlRange("strobe", 10, 250), DMXControlRange("on", 250, 255)],
        )
        self.color_channel = DMXControlChannel(
            "color_channel",
            7,
            [
                DMXControlRange("white", 0, 10),
                DMXControlRange("color_1", 10, 20),
                DMXControlRange("color_2", 20, 30),
                DMXControlRange("color_3", 30, 40),
                DMXControlRange("color_4", 40, 50),
                DMXControlRange("color_5", 50, 60),
                DMXControlRange("color_6", 60, 70),
                DMXControlRange("color_7", 70, 80),
                DMXControlRange("half_color_1", 80, 90),
                DMXControlRange("half_color_2", 90, 100),
                DMXControlRange("half_color_3", 100, 110),
                DMXControlRange("half_color_4", 110, 120),
                DMXControlRange("half_color_5", 120, 130),
                DMXControlRange("half_color_6", 130, 140),
            ],
        )
        self.pattern_channel = DMXControlChannel(
            "pattern_channel",
            8,
            [
                DMXControlRange("circular_white", 0, 6),
                DMXControlRange("pattern_1", 6, 12),
                DMXControlRange("pattern_2", 12, 18),
                DMXControlRange("pattern_3", 18, 24),
                DMXControlRange("pattern_4", 24, 30),
                DMXControlRange("pattern_5", 30, 36),
                DMXControlRange("pattern_6", 36, 42),
                DMXControlRange("pattern_7", 42, 48),
                DMXControlRange("pattern_8", 48, 54),
                DMXControlRange("pattern_9", 54, 60),
                DMXControlRange("pattern_10", 60, 66),
                DMXControlRange("pattern_11", 66, 72),
            ],
        )
        self.prisim_channel = DMXControlChannel(
            "prisim_channel",
            9,
            [
                DMXControlRange("off", 0, 100),
                DMXControlRange("on", 100, 128),
                DMXControlRange("rotation", 128, 255),
            ],
        )

    def shutter(self, close_shutter: bool) -> None:
        self.strobe_enabled = False
        self.strobe_rate(0)

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

    # def rotate_dither(self, index: int, rate: int) -> None:
    #     index = int(constrain(index, 0, len(self.patterns()) - 1))
    #     rate = cast(int, value_map(rate, 0, 255, 0, 6, True))

    #     self.dmx.set_channel(
    #         self.addr + YRXY200Spot.YRXY200Channel.PATTERN.value,
    #         YRXY200Spot.YRXY200Pattern.PATTERN_DITHER.value
    #         + self.patterns()[index].value
    #         + rate,
    #     )

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


# class YUER150Spot(Spot):
#     channels = [
#         DMXControlChannel("X_AXIS", 0),
#         DMXControlChannel("X_AXIS_FINE", 1),
#         DMXControlChannel("Y_AXIS", 2),
#         DMXControlChannel("Y_AXIS_FINE", 3),
#         DMXControlChannel("XY_SPEED", 4),
#         DMXControlChannel("DIMMING", 5),
#         DMXControlChannel(
#             "STROBE",
#             6,
#             [DMXControlRange("NO_STROBE", 0, 15), DMXControlRange("STROBE", 16, 255)],
#         ),
#         DMXControlChannel("COLOR", 7),
#         DMXControlChannel("PATTERN", 8),
#         DMXControlChannel("PRISIM", 9),
#         DMXControlChannel("SELF_PROPELLED", 10),
#         DMXControlChannel("RESET", 11),
#     ]

#     class YUER150Channel(Enum):
#         X_AXIS = 0
#         X_AXIS_FINE = 1
#         Y_AXIS = 2
#         Y_AXIS_FINE = 3
#         XY_SPEED = 4
#         DIMMING = 5
#         STROBE = 6
#         COLOR = 7
#         PATTERN = 8
#         PRISIM = 9
#         SELF_PROPELLED = 10
#         RESET = 11

#     class YUER150Strobe(Enum):
#         NO_STROBE = 0
#         STROBE = 16

#     class YUER150Color(Enum):
#         WHITE = 0
#         COLOR_1_RED = 16
#         COLOR_2_GREEN = 32
#         COLOR_3_BLUE = 48
#         COLOR_4_PURPLE = 64
#         COLOR_5_ORANGE = 80
#         COLOR_6_TEAL = 96
#         COLOR_7_YELLOW = 112
#         FORWARD_FLOW = 128

#     class YUER150Pattern(Enum):
#         CIRCULAR_WHITE = 0
#         PATTERN_1_MUSIC = 16
#         PATTERN_2_ZIG = 32
#         PATTERN_3_CROSS = 48
#         PATTERN_4_FLOWER = 64
#         PATTERN_5_CROSS = 80
#         PATTERN_6_TRIDENT = 96
#         PATTERN_7_SMALL_FLOWER = 112
#         REVERSE_FLOW = 128

#     class YUER150Prisim(Enum):
#         NONE = 0
#         PRISIM = 128
#         PRISIM_ROTATION = 137

#     class YUER150SelfPropelled(Enum):
#         NONE = 0
#         FAST = 51
#         SLOW = 101
#         SOUND = 201

#     class YUER150Reset(Enum):
#         NONE = 0
#         RESET = 250

#     def __init__(self, dmx: DMXManager, addr: int):
#         super().__init__(dmx=dmx, addr=addr, num_chans=12)

#     def x(self, x: int) -> None:
#         self.x_val[0] = cast(int, constrain(x, 0, 255))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.X_AXIS.value, self.x_val[0]
#         )

#     def x_fine(self, x_fine: int) -> None:
#         self.x_val[1] = cast(int, constrain(x_fine, 0, 255))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.X_AXIS_FINE.value, self.x_val[1]
#         )

#     def y(self, y: int) -> None:
#         self.y_val[0] = cast(int, constrain(y, 0, 255))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.Y_AXIS.value, self.y_val[0]
#         )

#     def y_fine(self, y_fine: int) -> None:
#         self.y_val[1] = cast(int, constrain(y_fine, 0, 255))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.Y_AXIS_FINE.value, self.y_val[1]
#         )

#     def xy_speed(self, speed: int) -> None:
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.XY_SPEED.value, speed
#         )

#     def dimming(self, value: DMXValue) -> None:
#         self.dimming_val = cast(int, constrain(value, 0, 255))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.DIMMING.value, value
#         )

#     def strobe(self, enable: bool, rate: int = 0) -> None:
#         self.strobe_enabled = enable

#         if not enable:
#             self.dmx.set_channel(
#                 self.addr + YUER150Spot.YUER150Channel.STROBE.value,
#                 YUER150Spot.YUER150Strobe.NO_STROBE.value,
#             )
#             self.strobe_rate = 0
#         else:
#             self.strobe_rate = cast(int, value_map(rate, 0, 255, 0, 255 - 16, True))
#             self.dmx.set_channel(
#                 self.addr + YUER150Spot.YUER150Channel.STROBE.value,
#                 YUER150Spot.YUER150Strobe.STROBE.value + self.strobe_rate,
#             )

#     def colors(self) -> List[YUER150Color]:
#         return [
#             YUER150Spot.YUER150Color.WHITE,
#             YUER150Spot.YUER150Color.COLOR_1_RED,
#             YUER150Spot.YUER150Color.COLOR_2_GREEN,
#             YUER150Spot.YUER150Color.COLOR_3_BLUE,
#             YUER150Spot.YUER150Color.COLOR_4_PURPLE,
#             YUER150Spot.YUER150Color.COLOR_5_ORANGE,
#             YUER150Spot.YUER150Color.COLOR_6_TEAL,
#             YUER150Spot.YUER150Color.COLOR_7_YELLOW,
#         ]

#     def color(self, index: int) -> None:
#         self.color_index = int(constrain(index, 0, len(self.colors()) - 1))

#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.COLOR.value,
#             self.colors()[self.color_index].value,
#         )

#     def white(self) -> None:
#         self.color(0)

#     # pylint: disable-next=unused-argument
#     def rotate_color(self, forward: bool, rate: int = 0) -> None:
#         # no reverse flow available

#         rate = cast(int, value_map(rate, 0, 255, 0, 255 - 128, True))
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.PATTERN.value,
#             YUER150Spot.YUER150Color.FORWARD_FLOW.value + rate,
#         )

#     def patterns(self) -> List[YUER150Pattern]:
#         return [
#             YUER150Spot.YUER150Pattern.CIRCULAR_WHITE,
#             YUER150Spot.YUER150Pattern.PATTERN_1_MUSIC,
#             YUER150Spot.YUER150Pattern.PATTERN_2_ZIG,
#             YUER150Spot.YUER150Pattern.PATTERN_3_CROSS,
#             YUER150Spot.YUER150Pattern.PATTERN_4_FLOWER,
#             YUER150Spot.YUER150Pattern.PATTERN_5_CROSS,
#             YUER150Spot.YUER150Pattern.PATTERN_6_TRIDENT,
#             YUER150Spot.YUER150Pattern.PATTERN_7_SMALL_FLOWER,
#         ]

#     def pattern(self, index: int) -> None:
#         self.pattern_index = int(constrain(index, 0, len(self.patterns()) - 1))

#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.PATTERN.value,
#             self.patterns()[self.pattern_index].value,
#         )

#     def no_pattern(self) -> None:
#         self.pattern(0)

#     # pylint: disable-next=unused-argument
#     def rotate_pattern(self, forward: bool, rate: int = 0) -> None:
#         rate = cast(int, constrain(rate, 0, 255 - 128))

#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.PATTERN.value,
#             YUER150Spot.YUER150Pattern.REVERSE_FLOW.value + rate,
#         )

#     def prisim(self, enable: bool, rotation: int = 0) -> None:
#         self.prisim_enabled = enable
#         self.prisim_rotation = rotation

#         if not enable:
#             self.dmx.set_channel(
#                 self.addr + YUER150Spot.YUER150Channel.PRISIM.value,
#                 YUER150Spot.YUER150Prisim.NONE.value,
#             )
#         elif rotation == 0:
#             self.dmx.set_channel(
#                 self.addr + YUER150Spot.YUER150Channel.PRISIM.value,
#                 YUER150Spot.YUER150Prisim.PRISIM.value,
#             )
#         else:
#             self.prisim_rotation = cast(
#                 int, value_map(rotation, 0, 255, 0, 255 - 137, True)
#             )
#             self.dmx.set_channel(
#                 self.addr + YUER150Spot.YUER150Channel.PRISIM.value,
#                 YUER150Spot.YUER150Prisim.PRISIM_ROTATION.value + self.prisim_rotation,
#             )

#     def self_propelled(
#         self, self_propelled: YUER150SelfPropelled, offset: int = 0
#     ) -> None:
#         if self_propelled == YUER150Spot.YUER150SelfPropelled.FAST:
#             offset = cast(int, value_map(offset, 0, 255, 0, 100 - 51, True))
#         elif self_propelled == YUER150Spot.YUER150SelfPropelled.SLOW:
#             offset = cast(int, value_map(offset, 0, 255, 0, 200 - 101, True))
#         elif self_propelled == YUER150Spot.YUER150SelfPropelled.SOUND:
#             offset = cast(int, value_map(offset, 0, 255, 0, 255 - 201, True))

#         else:
#             offset = 0

#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.SELF_PROPELLED.value,
#             self_propelled.value + offset,
#         )

#     def reset(self, reset: YUER150Reset) -> None:
#         self.dmx.set_channel(
#             self.addr + YUER150Spot.YUER150Channel.RESET.value, reset.value
#         )


class PinSpot(LightFixture):
    def __init__(self, dmx: DMXManager, addr: int):
        super().__init__(dmx=dmx, addr=addr, num_chans=6)

    def dimming(self, val: DMXValue) -> None:
        self.rgbw(val, val, val, val)

    def rgbw(self, r, g, b, w) -> None:
        self.set([255, r, g, b, w, 0])
