from typing import List

from ..category import Categories
from ..dmx import DMXManager
from ..fixtures import LightFixture, RGBLight, RGBWLight, YRXY200Spot
from ..fixtures.basics import Fixture
from ..fixtures.hazers import RadianceHazer
from ..osc import OSCManager


def create_fixtures(
    *,
    dmx: DMXManager,
    osc: OSCManager,
    categories: Categories,
    spot_color_fade: float,
    spot_mechanical_time: float,
    debug_hazer: bool,
) -> List[Fixture]:
    """Build every physical fixture and return them in mixer order."""
    reds = categories.reds
    booth = categories.booth
    plants = categories.plants
    spots_light = categories.spots_light
    washes = categories.washes

    dimmers: List[LightFixture] = [
        LightFixture(name="left_1", category=reds, dmx=dmx, addr=4, osc=osc),
        LightFixture(name="left_2", category=reds, dmx=dmx, addr=3, osc=osc),
        LightFixture(name="left_3", category=reds, dmx=dmx, addr=2, osc=osc),
        LightFixture(name="left_4", category=reds, dmx=dmx, addr=1, osc=osc),
        LightFixture(name="right_1", category=reds, dmx=dmx, addr=5, osc=osc),
        LightFixture(name="right_2", category=reds, dmx=dmx, addr=6, osc=osc),
        LightFixture(name="right_3", category=reds, dmx=dmx, addr=7, osc=osc),
        LightFixture(name="right_4", category=reds, dmx=dmx, addr=8, osc=osc),
        LightFixture(name="front_1", category=reds, dmx=dmx, addr=12, osc=osc),
        LightFixture(name="front_2", category=reds, dmx=dmx, addr=9, osc=osc),
        LightFixture(name="under_1", category=booth, dmx=dmx, addr=10, osc=osc),
        LightFixture(name="under_2", category=booth, dmx=dmx, addr=11, osc=osc),
        LightFixture(name="ceil_1", category=plants, dmx=dmx, addr=18, osc=osc),
        LightFixture(name="ceil_2", category=plants, dmx=dmx, addr=19, osc=osc),
        LightFixture(name="ceil_3", category=plants, dmx=dmx, addr=17, osc=osc),
    ]

    tung_spot = LightFixture(
        name="tung_spot", category=spots_light, dmx=dmx, addr=13, osc=osc
    )

    spotlights: List[YRXY200Spot] = [
        YRXY200Spot(
            name="spot_1",
            category=spots_light,
            position_category=categories.spots_position,
            dmx=dmx,
            addr=21,
            osc=osc,
        ),
        YRXY200Spot(
            name="spot_2",
            category=spots_light,
            position_category=categories.spots_position,
            dmx=dmx,
            addr=200,
            osc=osc,
        ),
    ]
    for spot in spotlights:
        spot.dimming(255)
        spot.strobe(False)
        spot.color(0)
        spot.no_pattern()
        spot.prisim(False)
        spot.colorful(False)
        spot.self_propelled(YRXY200Spot.YRXY200SelfPropelled.NONE)
        spot.light_strip_scene(YRXY200Spot.YRXY200RingScene.OFF)
        spot.scene_speed(0)
        spot.pan(0)
        spot.tilt(0)
        spot.color_swap_fade_time = spot_color_fade
        spot.color_swap_mechanical_time = spot_mechanical_time

    washfl = RGBLight(name="wash_fl", category=washes, dmx=dmx, addr=104, osc=osc)
    washfl.rgb(0, 0, 0)
    washfr = RGBLight(name="wash_fr", category=washes, dmx=dmx, addr=107, osc=osc)
    washfr.rgb(0, 0, 0)
    washml = RGBLight(name="wash_ml", category=washes, dmx=dmx, addr=110, osc=osc)
    washml.rgb(0, 0, 0)
    washmr = RGBLight(name="wash_mr", category=washes, dmx=dmx, addr=113, osc=osc)
    washmr.rgb(0, 0, 0)
    washbl = RGBLight(name="wash_bl", category=washes, dmx=dmx, addr=120, osc=osc)
    washbl.rgb(0, 0, 0)
    washbr = RGBLight(name="wash_br", category=washes, dmx=dmx, addr=123, osc=osc)
    washbr.rgb(0, 0, 0)
    washceilf = RGBWLight(
        name="wash_ceil_f", category=washes, dmx=dmx, addr=100, osc=osc
    )
    washceilf.rgbw(0, 0, 0, 0)
    washceilr = RGBWLight(
        name="wash_ceil_r", category=washes, dmx=dmx, addr=116, osc=osc
    )
    washceilr.rgbw(0, 0, 0, 0)
    wash_fixtures: List[LightFixture] = [
        washfl,
        washfr,
        washml,
        washmr,
        washbl,
        washbr,
        washceilf,
        washceilr,
    ]

    sodium = LightFixture(
        name="sodium", category=categories.non_saved, dmx=dmx, addr=20, osc=osc
    )

    hazer = RadianceHazer(
        name="hazer",
        category=categories.hazer,
        dmx=dmx,
        addr=250,
        debug=debug_hazer,
    )

    fixtures: List[Fixture] = (
        dimmers + [tung_spot] + spotlights + wash_fixtures + [sodium, hazer]
    )
    return fixtures
