import math

import pytest

from parquette.lights.util.aiming import (
    AimingConfig,
    xyz_to_pantilt,
    pantilt_to_xyz,
)


YRXY = AimingConfig(
    pan_min_deg=0.0,
    pan_max_deg=540.0,
    tilt_min_deg=0.0,
    tilt_max_deg=200.0,
    pan_center_deg=270.0,
    tilt_center_deg=100.0,
)


def test_center_points_forward():
    x, y, z = pantilt_to_xyz(270.0, 100.0, YRXY)
    assert x == pytest.approx(0.0, abs=1e-12)
    assert y == pytest.approx(0.0, abs=1e-12)
    assert z == pytest.approx(1.0, abs=1e-12)


def test_inverse_of_center_is_center():
    pt = xyz_to_pantilt(
        0.0, 0.0, 1.0, YRXY, current_pan_deg=270.0, current_tilt_deg=100.0
    )
    assert pt is not None
    pan, tilt = pt
    assert pan == pytest.approx(270.0, abs=1e-9)
    assert tilt == pytest.approx(100.0, abs=1e-9)


def test_round_trip_grid():
    # Stay safely inside both ranges so the natural family is the unique
    # in-range solution and round-trip is exact.
    for pan in (200.0, 250.0, 270.0, 300.0, 340.0):
        for tilt in (60.0, 90.0, 100.0, 110.0, 140.0):
            x, y, z = pantilt_to_xyz(pan, tilt, YRXY)
            pt = xyz_to_pantilt(
                x, y, z, YRXY, current_pan_deg=pan, current_tilt_deg=tilt
            )
            assert pt is not None, (pan, tilt)
            assert pt[0] == pytest.approx(pan, abs=1e-7)
            assert pt[1] == pytest.approx(tilt, abs=1e-7)


def test_pan_overlap_prefers_nearer_wrap():
    # A direction reachable at both pan=10 and pan=370. Starting near 540,
    # the 370 solution should win.
    x, y, z = pantilt_to_xyz(10.0, 100.0, YRXY)
    pt = xyz_to_pantilt(x, y, z, YRXY, current_pan_deg=520.0, current_tilt_deg=100.0)
    assert pt is not None
    assert pt[0] == pytest.approx(370.0, abs=1e-7)
    # And starting near 0, the 10 solution should win.
    pt2 = xyz_to_pantilt(x, y, z, YRXY, current_pan_deg=0.0, current_tilt_deg=100.0)
    assert pt2 is not None
    assert pt2[0] == pytest.approx(10.0, abs=1e-7)


def test_alternate_family_near_zenith():
    # For YRXY200 the natural and alternate trig families both land in
    # range only near the zenith overlap. At pan=300, tilt=185 the natural
    # solution exists; the alternate is the same direction reached by
    # rotating the yoke 180 deg and flipping the head through the zenith.
    x, y, z = pantilt_to_xyz(300.0, 185.0, YRXY)
    pt = xyz_to_pantilt(x, y, z, YRXY, current_pan_deg=300.0, current_tilt_deg=185.0)
    assert pt is not None
    # The natural (closer) solution wins from this start.
    assert pt[0] == pytest.approx(300.0, abs=1e-7)
    assert pt[1] == pytest.approx(185.0, abs=1e-7)
    # Now start far from natural but near an alternate solution and verify
    # we converge to a different in-range candidate that produces the same
    # direction.
    pt2 = xyz_to_pantilt(x, y, z, YRXY, current_pan_deg=120.0, current_tilt_deg=15.0)
    assert pt2 is not None
    assert pt2 != pt
    x2, y2, z2 = pantilt_to_xyz(pt2[0], pt2[1], YRXY)
    assert (x2, y2, z2) == pytest.approx((x, y, z), abs=1e-9)


def test_unreachable_returns_none():
    cfg = AimingConfig(
        pan_min_deg=0.0,
        pan_max_deg=360.0,
        tilt_min_deg=95.0,
        tilt_max_deg=105.0,  # only ~+/- 5 deg of tilt about center=100
        pan_center_deg=180.0,
        tilt_center_deg=100.0,
    )
    # Straight up: requires tilt offset of +90, way outside range. Alternate
    # also outside range.
    pt = xyz_to_pantilt(
        0.0, 1.0, 0.0, cfg, current_pan_deg=180.0, current_tilt_deg=100.0
    )
    assert pt is None


def test_zero_vector_returns_none():
    assert (
        xyz_to_pantilt(
            0.0, 0.0, 0.0, YRXY, current_pan_deg=270.0, current_tilt_deg=100.0
        )
        is None
    )


def test_direction_is_unit_length():
    for pan in (10.0, 200.0, 350.0, 530.0):
        for tilt in (5.0, 50.0, 100.0, 150.0, 195.0):
            x, y, z = pantilt_to_xyz(pan, tilt, YRXY)
            assert math.sqrt(x * x + y * y + z * z) == pytest.approx(1.0, abs=1e-12)
