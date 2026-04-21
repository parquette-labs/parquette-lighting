"""Coordinate-system abstraction for spot pan/tilt UI controls.

A CoordSystem maps between mapping-space (the 16-bit coords the UI and
mixer work in) and real pan/tilt 16-bit values that the fixture firmware
expects. The mixer is coord-system-agnostic: all offsets and generator
outputs accumulate in mapping-space; the conversion to real pan/tilt
happens once per tick inside the spot fixture's post_map_output hook.

Implementations:
  - PanTiltCoordSystem: identity. Mapping-space IS real pan/tilt.
  - RawCoordSystem:     functional duplicate of PanTiltCoordSystem, kept
                        as a separate class for naming clarity.
  - LatLonCoordSystem:  treats the 16-bit XY input as latitude/longitude
                        encoded over a fixed degree range.
"""

from typing import Dict, List, Optional, Protocol

from .coordinates import (
    SpotCoordFrame,
    latlon_to_pan_tilt,
    pan_tilt_to_latlon,
)
from .math import constrain, value_map


SIXTEEN_BIT_MAX = 65535
LAT_DEG_RANGE = (-90.0, 90.0)
LON_DEG_RANGE = (-180.0, 180.0)


class CoordSystem(Protocol):
    """Maps between mapping-space (UI / mixer) and real pan/tilt 16-bit.

    Implementations are stateless; all per-spot context (frame, current
    real pan/tilt) is passed in by the caller.
    """

    name: str

    def mapping_to_real(
        self,
        xy: List[float],
        frame: SpotCoordFrame,
        current_real: Optional[List[float]] = None,
    ) -> Optional[List[float]]:
        """Convert a mapping-space 2-vec to a real pan/tilt 2-vec.

        `current_real` is the most recent real pan/tilt — used as a
        nearest-solution hint where the mapping has multiple valid
        pan/tilt solutions. Returns None if the requested mapping point
        is unreachable inside the frame's pan/tilt ranges.
        """

    def real_to_mapping(
        self, pan_tilt: List[float], frame: SpotCoordFrame
    ) -> List[float]:
        """Convert a real pan/tilt 2-vec back into mapping-space."""


# pylint: disable=unused-argument
# Identity systems must accept the same arguments as the Protocol but do
# not need to consult the frame or current_real.
class PanTiltCoordSystem:
    """Identity coord system. Mapping-space IS real pan/tilt 16-bit."""

    name = "pantilt"

    def mapping_to_real(
        self,
        xy: List[float],
        frame: SpotCoordFrame,
        current_real: Optional[List[float]] = None,
    ) -> Optional[List[float]]:
        return [float(xy[0]), float(xy[1])]

    def real_to_mapping(
        self, pan_tilt: List[float], frame: SpotCoordFrame
    ) -> List[float]:
        return [float(pan_tilt[0]), float(pan_tilt[1])]


class RawCoordSystem:
    """Functional duplicate of PanTiltCoordSystem, kept distinct for
    naming clarity. Not registered in the default systems dict — used
    where callers explicitly want the raw label."""

    name = "raw"

    def mapping_to_real(
        self,
        xy: List[float],
        frame: SpotCoordFrame,
        current_real: Optional[List[float]] = None,
    ) -> Optional[List[float]]:
        return [float(xy[0]), float(xy[1])]

    def real_to_mapping(
        self, pan_tilt: List[float], frame: SpotCoordFrame
    ) -> List[float]:
        return [float(pan_tilt[0]), float(pan_tilt[1])]


# pylint: enable=unused-argument


class LatLonCoordSystem:
    """Treats the 16-bit XY input as latitude (X) and longitude (Y).

    Encoding:
      X axis 0..65535  <->  lat -90..+90 degrees
      Y axis 0..65535  <->  lon -180..+180 degrees

    Real pan/tilt is also 16-bit; converted to/from degrees via the
    frame's pan_range / tilt_range using value_map.
    """

    name = "latlon"

    def mapping_to_real(
        self,
        xy: List[float],
        frame: SpotCoordFrame,
        current_real: Optional[List[float]] = None,
    ) -> Optional[List[float]]:
        lat = value_map(xy[0], 0, SIXTEEN_BIT_MAX, *LAT_DEG_RANGE)
        lon = value_map(xy[1], 0, SIXTEEN_BIT_MAX, *LON_DEG_RANGE)
        current_deg = self._current_to_degrees(current_real, frame)
        result = latlon_to_pan_tilt(lat, lon, frame, current=current_deg)
        if result is None:
            return None
        pan_deg, tilt_deg = result
        return [
            constrain(
                value_map(
                    pan_deg,
                    frame.pan_range[0],
                    frame.pan_range[1],
                    0,
                    SIXTEEN_BIT_MAX,
                ),
                0,
                SIXTEEN_BIT_MAX,
            ),
            constrain(
                value_map(
                    tilt_deg,
                    frame.tilt_range[0],
                    frame.tilt_range[1],
                    0,
                    SIXTEEN_BIT_MAX,
                ),
                0,
                SIXTEEN_BIT_MAX,
            ),
        ]

    def real_to_mapping(
        self, pan_tilt: List[float], frame: SpotCoordFrame
    ) -> List[float]:
        pan_deg = value_map(
            pan_tilt[0],
            0,
            SIXTEEN_BIT_MAX,
            frame.pan_range[0],
            frame.pan_range[1],
        )
        tilt_deg = value_map(
            pan_tilt[1],
            0,
            SIXTEEN_BIT_MAX,
            frame.tilt_range[0],
            frame.tilt_range[1],
        )
        lat, lon = pan_tilt_to_latlon(pan_deg, tilt_deg, frame)
        return [
            value_map(lat, *LAT_DEG_RANGE, 0, SIXTEEN_BIT_MAX),
            value_map(lon, *LON_DEG_RANGE, 0, SIXTEEN_BIT_MAX),
        ]

    @staticmethod
    def _current_to_degrees(
        current_real: Optional[List[float]], frame: SpotCoordFrame
    ) -> Optional[tuple[float, float]]:
        if current_real is None:
            return None
        pan_deg = value_map(
            current_real[0],
            0,
            SIXTEEN_BIT_MAX,
            frame.pan_range[0],
            frame.pan_range[1],
        )
        tilt_deg = value_map(
            current_real[1],
            0,
            SIXTEEN_BIT_MAX,
            frame.tilt_range[0],
            frame.tilt_range[1],
        )
        return (pan_deg, tilt_deg)


def default_systems() -> Dict[str, CoordSystem]:
    """Build the default {name: CoordSystem} dict.

    CoordSystems are stateless — they receive the per-spot frame on each
    call, so a single instance is shared across all spots.
    """
    return {
        PanTiltCoordSystem.name: PanTiltCoordSystem(),
        LatLonCoordSystem.name: LatLonCoordSystem(),
    }
