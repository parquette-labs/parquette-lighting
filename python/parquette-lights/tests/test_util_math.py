from bellechasse.util.math import *


def test_constrain():
    assert constrain(-1, 0, 100) == 0
    assert constrain(2, 0, 100) == 2
    assert constrain(102, 0, 100) == 100
    assert constrain(-1, -5, 100) == -1
    assert constrain(-6, -5, 100) == -5
    assert constrain(-150, -200, -100) == -150
    assert constrain(-250, -200, -100) == -200
    assert constrain(-80, -200, -100) == -100
    assert constrain(5, 100, 0) == 100


def test_map():
    assert value_map(10, 5, 15, 10, 30) == 20
    assert value_map(2, 0, 10, 0, 100) == 20
    assert value_map(-1.5, -1, -2.5, -8, -20) == -12
    assert value_map(-1.5, -1, -2.5, 0, 60) == 20
