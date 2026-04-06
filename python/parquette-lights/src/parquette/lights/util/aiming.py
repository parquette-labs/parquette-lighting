"""Geometric helpers for aiming moving-head spotlights.

Maps between (pan, tilt) yoke angles and the cartesian direction of the beam
on a unit sphere centered at the fixture.

Axis convention (default and currently the only one supported):

    up      = +Y     (pan rotates about this axis)
    forward = +Z     (beam direction at pan_center / tilt_center)
    right   = +X

With Delta_p = pan - pan_center, Delta_t = tilt - tilt_center, the beam
direction is::

    d_x = sin(Delta_p) * cos(Delta_t)
    d_y = sin(Delta_t)
    d_z = cos(Delta_p) * cos(Delta_t)

The inverse has two families of solutions because flipping the head through
the zenith and rotating the yoke 180 degrees yields the same beam direction;
additionally, fixtures with > 360 degrees of pan travel admit pan +/- 360
duplicates. ``pantilt_to_xyz`` enumerates all valid candidates within
the fixture's limits and picks the one minimizing weighted travel from the
current pose.
"""

from dataclasses import dataclass
from math import asin, atan2, cos, degrees, radians, sin, sqrt
from typing import Optional, Tuple


@dataclass(frozen=True)
class AimingConfig:
    """Per-fixture aiming limits and zero-direction calibration.

    All angles in degrees. ``pan_center`` / ``tilt_center`` are the raw
    pan/tilt values at which the beam points along the fixture's forward
    axis (+Z by default).
    """

    pan_min_deg: float
    pan_max_deg: float
    tilt_min_deg: float
    tilt_max_deg: float
    pan_center_deg: float
    tilt_center_deg: float

    def __post_init__(self) -> None:
        if self.pan_max_deg <= self.pan_min_deg:
            raise ValueError("pan_max_deg must be > pan_min_deg")
        if self.tilt_max_deg <= self.tilt_min_deg:
            raise ValueError("tilt_max_deg must be > tilt_min_deg")
        if not self.pan_min_deg <= self.pan_center_deg <= self.pan_max_deg:
            raise ValueError("pan_center_deg must lie within [pan_min, pan_max]")
        if not self.tilt_min_deg <= self.tilt_center_deg <= self.tilt_max_deg:
            raise ValueError("tilt_center_deg must lie within [tilt_min, tilt_max]")


def pantilt_to_xyz(
    pan_deg: float, tilt_deg: float, cfg: AimingConfig
) -> Tuple[float, float, float]:
    """Forward map: yoke angles -> unit beam direction (x, y, z)."""
    dp = radians(pan_deg - cfg.pan_center_deg)
    dt = radians(tilt_deg - cfg.tilt_center_deg)
    cdt = cos(dt)
    return (sin(dp) * cdt, sin(dt), cos(dp) * cdt)


def xyz_to_pantilt(
    x: float,
    y: float,
    z: float,
    cfg: AimingConfig,
    *,
    current_pan_deg: Optional[float] = None,
    current_tilt_deg: Optional[float] = None,
    tilt_weight: Optional[float] = None,
) -> Optional[Tuple[float, float]]:
    """Inverse map: unit direction -> (pan_deg, tilt_deg) within limits.

    Enumerates the two trig solutions and all in-range pan +/- 360 duplicates,
    then returns the candidate minimizing weighted travel from the current
    pose. Returns ``None`` if the target is unreachable.

    ``tilt_weight`` scales the tilt term of the travel cost. The default
    normalizes a "full sweep" of either axis to the same cost.
    """
    if current_pan_deg is None:
        current_pan_deg = cfg.pan_center_deg
    if current_tilt_deg is None:
        current_tilt_deg = cfg.tilt_center_deg

    n = sqrt(x * x + y * y + z * z)
    if n == 0:
        return None
    x, y, z = x / n, y / n, z / n
    # Numerical clamp before asin.
    y_clamped = max(-1.0, min(1.0, y))

    pan_range = cfg.pan_max_deg - cfg.pan_min_deg
    tilt_range = cfg.tilt_max_deg - cfg.tilt_min_deg
    if tilt_weight is None:
        tilt_weight = pan_range / tilt_range

    # Two trig families. Family 0 is the natural asin/atan2 result.
    # Family 1 flips the head through zenith and rotates the yoke 180 deg.
    dt0 = degrees(asin(y_clamped))
    dp0 = degrees(atan2(x, z))
    dt1 = 180.0 - dt0
    dp1 = dp0 + 180.0

    candidates = []
    for dp_base, dt in ((dp0, dt0), (dp1, dt1)):
        tilt = cfg.tilt_center_deg + dt
        if not cfg.tilt_min_deg <= tilt <= cfg.tilt_max_deg:
            continue
        # Try all pan wraps that land in range.
        pan_natural = cfg.pan_center_deg + dp_base
        # Find smallest k such that pan_natural + 360k >= pan_min.
        k_min = int(-((pan_natural - cfg.pan_min_deg) // 360))
        # Walk forward through valid wraps.
        k = k_min - 1  # safety margin for floor edge cases
        while True:
            pan = pan_natural + 360.0 * k
            if pan > cfg.pan_max_deg:
                break
            if pan >= cfg.pan_min_deg:
                candidates.append((pan, tilt))
            k += 1

    if not candidates:
        return None

    def cost(pt: Tuple[float, float]) -> float:
        return abs(pt[0] - current_pan_deg) + tilt_weight * abs(
            pt[1] - current_tilt_deg
        )

    return min(candidates, key=cost)
