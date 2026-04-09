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
