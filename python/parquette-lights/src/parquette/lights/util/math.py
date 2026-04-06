import math
from typing import Union


def fold_tempo(bpm: float, reference: float = 100.0) -> float:
    """Fold bpm to the nearest 2x/0.5x multiple of reference.

    Handles the common case where beat_track locks onto exactly half or double
    the true tempo. With the default reference of 100 BPM this normalises all
    tempos into a single canonical octave (roughly 67–133 BPM).
    """
    if reference <= 0 or bpm <= 0:
        return bpm
    while bpm < reference / 1.5:
        bpm *= 2
    while bpm > reference * 1.5:
        bpm /= 2
    return bpm


def fold_tempo_for_stability(bpm: float, reference: float) -> float:
    """Fold bpm for stability comparison, treating 2x and 1.5x multiples as equivalent.

    Steps reference up and down by both 2x and 1.5x to build a candidate set,
    then returns bpm normalised relative to whichever candidate is closest in
    log space. A beat tracker alternating between T and 1.5T (or 2T/3) will
    produce near-zero variance after folding.
    """
    if reference <= 0 or bpm <= 0:
        return bpm

    candidates = []
    for factor in (2.0, 1.5, 1.33):
        r = reference
        while r >= bpm / 3.0:
            candidates.append(r)
            r /= factor
        r = reference * factor
        while r <= bpm * 3.0:
            candidates.append(r)
            r *= factor

    closest = min(candidates, key=lambda c: abs(c - bpm))
    return bpm * (reference / closest)


# pylint: disable-next=too-many-positional-arguments
def value_map(
    value: Union[float, int],
    old_min: Union[float, int],
    old_max: Union[float, int],
    new_min: Union[float, int],
    new_max: Union[float, int],
    constrain_result: bool = False,
) -> Union[float, int]:
    result = (value - old_min) / (old_max - old_min) * (new_max - new_min) + new_min
    if constrain_result:
        return constrain(result, new_min, new_max)

    else:
        return result


def constrain(
    value: Union[float, int], minimum: Union[float, int], maximum: Union[float, int]
) -> Union[float, int]:
    if value < minimum:
        return minimum
    elif value > maximum:
        return maximum
    else:
        return value
