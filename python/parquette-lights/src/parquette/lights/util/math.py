from typing import Union


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
