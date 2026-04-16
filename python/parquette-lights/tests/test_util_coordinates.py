import math

import pytest

from parquette.lights.util.coordinates import (
    SpotCoordFrame,
    latlon_to_direction,
    latlon_to_pan_tilt,
    pan_tilt_to_direction,
)


# Standard YRXY200-style frame: ceiling mount, pan 0-540, tilt 0-200,
# straight down at tilt=100, one pole horizontal at pan=0 tilt=10.
def default_frame(
    pan_range: tuple[float, float] = (0.0, 540.0),
    tilt_range: tuple[float, float] = (0.0, 200.0),
) -> SpotCoordFrame:
    return SpotCoordFrame(
        pan_down=0.0,
        tilt_down=100.0,
        pan_north=0.0,
        tilt_north=10.0,
        pan_range=pan_range,
        tilt_range=tilt_range,
    )


def assert_close(
    actual: tuple[float, float], expected: tuple[float, float], tol: float = 1e-6
) -> None:
    assert actual is not None
    assert abs(actual[0] - expected[0]) < tol, f"pan: {actual[0]} vs {expected[0]}"
    assert abs(actual[1] - expected[1]) < tol, f"tilt: {actual[1]} vs {expected[1]}"


# Anchor points: asking for the exact direction the frame was configured
# against should return the exact pan/tilt we configured when the current
# position is nearby.


def test_anchor_straight_down():
    frame = default_frame()
    assert_close(latlon_to_pan_tilt(0, 0, frame, current=(0, 100)), (0, 100))


def test_anchor_north_pole():
    frame = default_frame()
    assert_close(latlon_to_pan_tilt(90, 0, frame, current=(0, 10)), (0, 10))


def test_anchor_south_pole_via_pan_180():
    # South pole is antipodal to the configured north pole. It is reachable
    # at either (pan=180, tilt=10) or (pan=0, tilt=190); which one we get
    # depends on which the caller's current position is closer to.
    frame = default_frame()
    assert_close(latlon_to_pan_tilt(-90, 0, frame, current=(180, 10)), (180, 10))


def test_anchor_south_pole_via_mirror_tilt():
    frame = default_frame()
    assert_close(latlon_to_pan_tilt(-90, 0, frame, current=(0, 190)), (0, 190))


# Cardinal directions on the equator: longitude sweeps a horizontal arc.


def test_equator_plus_90():
    frame = default_frame()
    # (lat=0, lon=90) points in +y (horizontal); reachable at pan=90, tilt=10.
    assert_close(latlon_to_pan_tilt(0, 90, frame, current=(90, 10)), (90, 10))


def test_equator_minus_90():
    frame = default_frame()
    # (lat=0, lon=-90) points in -y (horizontal); reachable at pan=270,
    # tilt=10 via pan wrap (base pan = -90, + 360 = 270, in range).
    assert_close(latlon_to_pan_tilt(0, -90, frame, current=(270, 10)), (270, 10))


# Mirror-tilt branch selection: the two valid tilts for a direction are
# chosen based on proximity to current.


def test_mirror_tilt_picks_low_branch():
    frame = default_frame()
    # lat=45, lon=0 is reachable at (0, 55) or (180, 145) or (360, 55).
    assert_close(latlon_to_pan_tilt(45, 0, frame, current=(0, 55)), (0, 55))


def test_mirror_tilt_picks_high_branch():
    frame = default_frame()
    assert_close(latlon_to_pan_tilt(45, 0, frame, current=(180, 145)), (180, 145))


# Pan-wrap branch selection: with a range wider than 360 degrees the same
# direction is reachable at pan and pan+360.


def test_pan_wrap_picks_near_copy():
    frame = default_frame()
    # (lat=45, lon=0) base pan=0, so copies at pan=0 and pan=360. A current
    # near pan=350 should snap to the ~360 copy, not the pan=0 copy.
    result = latlon_to_pan_tilt(45, 0, frame, current=(350, 100))
    assert result is not None
    assert_close(result, (360, 55))


# Unreachable: if the tilt range excludes both mirror solutions for a
# direction, the function returns None.


def test_unreachable_returns_none():
    # Shrink tilt to the area around straight-down; the pole is unreachable.
    frame = default_frame(tilt_range=(90.0, 110.0))
    assert latlon_to_pan_tilt(90, 0, frame, current=(0, 10)) is None


# No current: target falls back to the centre of the pan/tilt ranges.


def test_current_none_picks_centre_nearest():
    frame = default_frame()
    # Default range centre is (270, 100). For (lat=60, lon=30) the three
    # in-range solutions are roughly (16, 36), (196, 164), (376, 36). The
    # one nearest (270, 100) is (196, 164).
    result = latlon_to_pan_tilt(60, 30, frame, current=None)
    assert result is not None
    assert abs(result[0] - 196.1) < 0.5
    assert abs(result[1] - 164.3) < 0.5


# Config validation: a pole that is not perpendicular to straight-down is
# a configuration error.


def test_validation_non_perpendicular_pole_raises():
    with pytest.raises(ValueError, match="not ~90"):
        SpotCoordFrame(
            pan_down=0.0,
            tilt_down=100.0,
            pan_north=0.0,
            tilt_north=50.0,  # 50 degrees off down, not 90 -> invalid.
            pan_range=(0.0, 540.0),
            tilt_range=(0.0, 200.0),
        )


def test_validation_bad_pan_range_raises():
    with pytest.raises(ValueError, match="pan_range"):
        SpotCoordFrame(
            pan_down=0.0,
            tilt_down=100.0,
            pan_north=0.0,
            tilt_north=10.0,
            pan_range=(540.0, 0.0),
            tilt_range=(0.0, 200.0),
        )


# Direction-vector sanity: spot-check the building blocks independently.


def test_pan_tilt_to_direction_straight_down():
    x, y, z = pan_tilt_to_direction(0, 100, pan_down=0, tilt_down=100)
    assert abs(x) < 1e-12 and abs(y) < 1e-12 and abs(z + 1) < 1e-12


def test_pan_tilt_to_direction_horizontal_x():
    x, y, z = pan_tilt_to_direction(0, 10, pan_down=0, tilt_down=100)
    assert abs(x - 1) < 1e-12 and abs(y) < 1e-12 and abs(z) < 1e-12


def test_latlon_to_direction_pole_and_equator():
    # With pole_azimuth=0 the pole-aligned and world frames coincide.
    x, y, z = latlon_to_direction(90, 0, pole_azimuth_rad=0.0)
    assert abs(x - 1) < 1e-12 and abs(y) < 1e-12 and abs(z) < 1e-12
    x, y, z = latlon_to_direction(0, 90, pole_azimuth_rad=0.0)
    assert abs(x) < 1e-12 and abs(y - 1) < 1e-12 and abs(z) < 1e-12


# Continuity: stepping the pad smoothly (and passing the prior result back
# as `current`) should not jump across mirror solutions or pan wraps.


def test_continuity_on_smooth_sweep():
    frame = default_frame()
    prev = (0.0, 55.0)  # at (lat=45, lon=0)
    max_step = 0.0
    for i in range(1, 91):
        lon = float(i)  # sweep from 0 to 90 degrees longitude
        curr = latlon_to_pan_tilt(45, lon, frame, current=prev)
        assert curr is not None
        step = math.hypot(curr[0] - prev[0], curr[1] - prev[1])
        max_step = max(max_step, step)
        prev = curr
    # Each 1-degree lon step should move pan/tilt by ~1 degree; allow 3x
    # slack for geometry nonlinearity. Jumping a mirror branch would cost
    # ~180 degrees, so a loose bound still catches regressions.
    assert max_step < 3.0, f"unexpected jump of {max_step:.2f} deg"
