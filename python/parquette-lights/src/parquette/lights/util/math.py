from typing import Union


def value_map(
    value: Union[float, int],
    old_min: Union[float, int],
    old_max: Union[float, int],
    new_min: Union[float, int],
    new_max: Union[float, int],
) -> Union[float, int]:
    return (value - old_min) / (old_max - old_min) * (new_max - new_min) + new_min


def constrain(
    value: Union[float, int], minimum: Union[float, int], maximum: Union[float, int]
) -> Union[float, int]:
    if value < minimum:
        return minimum
    elif value > maximum:
        return maximum
    else:
        return value
