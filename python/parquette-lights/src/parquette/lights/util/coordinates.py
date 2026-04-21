"""Lat/lon -> pan/tilt math for moving-head spot fixtures.

Moving-head spots have pan/tilt axes whose raw angles are not intuitive on
an XY pad: equal pad distance does not produce equal angular motion of the
beam, and any beam direction has multiple valid pan/tilt pairs (pan wraps
by 360 degrees, and for any tilt below straight-down there is a mirror
tilt above straight-down that reaches the same direction via pan+180).

This module wraps the beam's unit-sphere direction in a lat/lon frame whose
poles sit on the horizontal plane. With the default ceiling-mount config
(straight-down at tilt=100, a pole at tilt=10), latitude controls elevation
from the horizontal and longitude sweeps a horizontal arc.

Coordinate conventions:
  World frame: +x/+y horizontal, +z up. Straight down = -z.
  Latitude in [-90, 90] degrees; +90 = the north pole (= +x_hat_pole).
  Longitude in [-180, 180] degrees; the lon=0 meridian points straight down.
"""

from dataclasses import dataclass, field
from typing import Optional
import math


# When validating that the configured pole is perpendicular to straight
# down, allow up to this much slack. One degree is generous for hand-tuned
# config values and catches obvious typos.
POLE_PERPENDICULAR_TOL_DEG = 1.0


def pan_tilt_to_direction(
    pan_deg: float,
    tilt_deg: float,
    pan_down: float,
    tilt_down: float,
) -> tuple[float, float, float]:
    """Forward model from fixture axes to a unit beam-direction vector.

    Let delta = tilt_down - tilt (the signed lift from straight down) and
    p_off = pan - pan_down. Then the beam direction in the world frame is

        dir = R_z(p_off) . (sin delta, 0, -cos delta)
            = (sin delta * cos p_off,
               sin delta * sin p_off,
               -cos delta)

    Sanity checks this satisfies:
      - tilt = tilt_down                       -> (0, 0, -1), straight down
      - tilt = tilt_down - 90, pan = pan_down  -> (1, 0, 0), horizontal
      - tilt = tilt_down + 90, pan = pan_down  -> (-1, 0, 0); same direction
        as (tilt_down - 90, pan_down + 180). This is the mirror-tilt
        identity that creates the two-tilts-per-direction ambiguity.
    """
    delta = math.radians(tilt_down - tilt_deg)
    p_off = math.radians(pan_deg - pan_down)
    sin_d = math.sin(delta)
    cos_d = math.cos(delta)
    return (
        sin_d * math.cos(p_off),
        sin_d * math.sin(p_off),
        -cos_d,
    )


@dataclass(frozen=True)
class SpotCoordFrame:
    """Configuration for the lat/lon <-> pan/tilt mapping.

    pan_down, tilt_down:     pan/tilt where the beam points straight down.
    pan_north, tilt_north:   pan/tilt where the beam points at lat=+90.
                             This direction must lie on the horizontal plane
                             (90 degrees off straight-down); the constructor
                             raises ValueError otherwise.
    pan_range, tilt_range:   inclusive (min, max) of reachable axis values.

    pole_azimuth_rad is derived at construction: it is the angle around the
    world +z axis from the world +x axis to the north pole direction.
    """

    pan_down: float
    tilt_down: float
    pan_north: float
    tilt_north: float
    pan_range: tuple[float, float]
    tilt_range: tuple[float, float]

    pole_azimuth_rad: float = field(init=False, repr=False, default=0.0)

    def __post_init__(self) -> None:
        if self.pan_range[0] > self.pan_range[1]:
            raise ValueError(f"pan_range must be (min, max), got {self.pan_range}")
        if self.tilt_range[0] > self.tilt_range[1]:
            raise ValueError(f"tilt_range must be (min, max), got {self.tilt_range}")

        nx, ny, nz = pan_tilt_to_direction(
            self.pan_north, self.tilt_north, self.pan_down, self.tilt_down
        )
        # For a horizontal pole the z-component of its direction must be
        # zero. sin(POLE_PERPENDICULAR_TOL_DEG) is the equivalent vertical
        # component for a direction tilted by that angle off horizontal.
        if abs(nz) > math.sin(math.radians(POLE_PERPENDICULAR_TOL_DEG)):
            raise ValueError(
                f"Configured north pole (pan={self.pan_north}, "
                f"tilt={self.tilt_north}) is not ~90 degrees off straight "
                f"down (pan={self.pan_down}, tilt={self.tilt_down}); "
                f"vertical component of pole direction is {nz:.4f}."
            )
        # atan2 is stable here because the perpendicular-pole check above
        # rules out (nx, ny) == (0, 0).
        object.__setattr__(self, "pole_azimuth_rad", math.atan2(ny, nx))

    def range_centre(self) -> tuple[float, float]:
        return (
            0.5 * (self.pan_range[0] + self.pan_range[1]),
            0.5 * (self.tilt_range[0] + self.tilt_range[1]),
        )


def latlon_to_direction(
    lat_deg: float, lon_deg: float, pole_azimuth_rad: float
) -> tuple[float, float, float]:
    """Convert lat/lon to a world-frame unit direction vector.

    In the pole-aligned intermediate frame where +x_hat_pole is the north
    pole and the lon=0 meridian points straight down:

        dir_pole = (sin lat,
                    cos lat * sin lon,
                    -cos lat * cos lon)

    Then rotate around the world z axis by pole_azimuth to get the world
    frame: dir_world = R_z(pole_azimuth) . dir_pole.

    Sanity:
      - (lat=0, lon=0)        -> (0, 0, -1), straight down for any azimuth.
      - (lat=90, lon=anything) -> the pole direction, by construction.
    """
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    dp_x = math.sin(lat)
    dp_y = math.cos(lat) * math.sin(lon)
    dp_z = -math.cos(lat) * math.cos(lon)
    c = math.cos(pole_azimuth_rad)
    s = math.sin(pole_azimuth_rad)
    return (
        c * dp_x - s * dp_y,
        s * dp_x + c * dp_y,
        dp_z,
    )


def pan_tilt_to_latlon(
    pan_deg: float, tilt_deg: float, frame: SpotCoordFrame
) -> tuple[float, float]:
    """Convert (pan, tilt) to (lat, lon) in the same coordinate frame.

    Inverse of latlon_to_pan_tilt. Deterministic — every (pan, tilt) maps
    to exactly one (lat, lon) (in contrast with the forward direction,
    which has multiple pan/tilt solutions per direction).

    Steps:
      1. pan/tilt -> world-frame unit direction via pan_tilt_to_direction.
      2. Unrotate by pole_azimuth (apply R_z(-pole_azimuth)) to recover
         dir_pole = (sin lat, cos lat * sin lon, -cos lat * cos lon).
      3. lat = asin(dp_x); lon = atan2(dp_y, -dp_z).

    Returns lat in [-90, 90] and lon in [-180, 180] (degrees).
    """
    dx, dy, dz = pan_tilt_to_direction(
        pan_deg, tilt_deg, frame.pan_down, frame.tilt_down
    )
    c = math.cos(-frame.pole_azimuth_rad)
    s = math.sin(-frame.pole_azimuth_rad)
    dp_x = c * dx - s * dy
    dp_y = s * dx + c * dy
    dp_z = dz
    lat_rad = math.asin(max(-1.0, min(1.0, dp_x)))
    lon_rad = math.atan2(dp_y, -dp_z)
    return (math.degrees(lat_rad), math.degrees(lon_rad))


def direction_to_pan_tilt_candidates(
    direction: tuple[float, float, float],
    frame: SpotCoordFrame,
    singular_pan_hint: float,
) -> list[tuple[float, float]]:
    """Enumerate all in-range (pan, tilt) pairs that produce `direction`.

    Inverts the forward model. Given direction d:

        delta0  = acos(-d_z)                 in [0, pi]
        p_off0  = atan2(d_y, d_x)            undefined near the z-poles

    Two base solutions from the mirror-tilt identity:
      1. tilt = tilt_down - delta0, pan = pan_down + p_off0
      2. tilt = tilt_down + delta0, pan = pan_down + p_off0 + 180

    Each base has infinitely many pan copies (k*360 offsets); we emit every
    copy whose pan falls in pan_range and whose tilt falls in tilt_range.

    At the sphere poles (delta0 ~ 0 or ~ pi), p_off0 is undefined; pan
    becomes a free parameter. We collapse to one tilt (the common value of
    the two bases there) and place pan at singular_pan_hint clamped into
    range.
    """
    dx, dy, dz = direction
    # Clamp to guard against tiny trig round-trip overshoot of |cos| > 1.
    delta0_rad = math.acos(max(-1.0, min(1.0, -dz)))
    delta0_deg = math.degrees(delta0_rad)

    pan_min, pan_max = frame.pan_range
    tilt_min, tilt_max = frame.tilt_range
    candidates: list[tuple[float, float]] = []

    # The mirror bases and their pan edge is what makes pan "continuous"
    # across sin(delta0) = 0 difficult; use a small threshold to branch.
    if math.sin(delta0_rad) < 1e-9:
        tilt_val = frame.tilt_down - delta0_deg
        if tilt_min - 1e-9 <= tilt_val <= tilt_max + 1e-9:
            pan = max(pan_min, min(pan_max, singular_pan_hint))
            candidates.append((pan, tilt_val))
        return candidates

    p_off0_deg = math.degrees(math.atan2(dy, dx))
    bases = (
        (frame.tilt_down - delta0_deg, p_off0_deg),
        (frame.tilt_down + delta0_deg, p_off0_deg + 180.0),
    )
    for tilt_val, p_off_deg in bases:
        if not tilt_min - 1e-9 <= tilt_val <= tilt_max + 1e-9:
            continue
        base_pan = frame.pan_down + p_off_deg
        # All k in the smallest/largest integers keeping base_pan+360k in
        # [pan_min, pan_max].
        k_lo = math.ceil((pan_min - base_pan) / 360.0)
        k_hi = math.floor((pan_max - base_pan) / 360.0)
        for k in range(k_lo, k_hi + 1):
            candidates.append((base_pan + 360.0 * k, tilt_val))

    return candidates


def latlon_to_pan_tilt(
    lat_deg: float,
    lon_deg: float,
    frame: SpotCoordFrame,
    current: Optional[tuple[float, float]] = None,
) -> Optional[tuple[float, float]]:
    """Resolve a lat/lon direction to the closest reachable (pan, tilt).

    The target for "closest" is `current` when provided, else the centre of
    the pan/tilt ranges. Distance is Euclidean in (pan_deg, tilt_deg) with
    equal weighting on both axes. Returns None when no candidate pair
    reaches `direction` inside the configured ranges.
    """
    target = current if current is not None else frame.range_centre()
    direction = latlon_to_direction(lat_deg, lon_deg, frame.pole_azimuth_rad)
    candidates = direction_to_pan_tilt_candidates(
        direction, frame, singular_pan_hint=target[0]
    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda c: (c[0] - target[0]) ** 2 + (c[1] - target[1]) ** 2,
    )
