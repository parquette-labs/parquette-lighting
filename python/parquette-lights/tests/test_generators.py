import math
import random
from bellechasse.generators import *


def test_wave_gen_sin():
    wg = WaveGenerator(
        name="sin1",
        amp=0.5,
        offset=0.5,
        period=1000,
        phase=247,
        shape=WaveGenerator.Shape.SIN,
    )
    assert wg.name == "sin1"
    assert math.isclose(wg.value(-247 + 0 + random.randint(0, 100) * 1000), 0.5)
    assert math.isclose(
        wg.value(-247 + 125 + random.randint(0, 100) * 1000), 0.5 + 0.5 / 2 ** (0.5)
    )
    assert math.isclose(wg.value(-247 + 250 + random.randint(0, 100) * 1000), 1)
    assert math.isclose(wg.value(-247 + 500 + random.randint(0, 100) * 1000), 0.5)
    assert math.isclose(wg.value(-247 + 750 + random.randint(0, 100) * 1000), 0)


def test_wave_gen_tri():
    wg = WaveGenerator(
        name="tri1",
        amp=0.5,
        offset=0.5,
        phase=247,
        period=1000,
        shape=WaveGenerator.Shape.TRIANGLE,
    )
    assert wg.name == "tri1"
    assert math.isclose(wg.value(-247 + 0 + random.randint(0, 100) * 1000), 0.5)
    assert math.isclose(wg.value(-247 + 125 + random.randint(0, 100) * 1000), 0.75)
    assert math.isclose(wg.value(-247 + 250 + random.randint(0, 100) * 1000), 1)
    assert math.isclose(wg.value(-247 + 375 + random.randint(0, 100) * 1000), 0.75)
    assert math.isclose(wg.value(-247 + 500 + random.randint(0, 100) * 1000), 0.5)
    assert math.isclose(wg.value(-247 + 625 + random.randint(0, 100) * 1000), 0.25)
    assert math.isclose(wg.value(-247 + 750 + random.randint(0, 100) * 1000), 0)


def test_wave_sq():
    wg = WaveGenerator(
        name="sq1",
        amp=0.5,
        offset=0.5,
        phase=247,
        period=1000,
        shape=WaveGenerator.Shape.SQUARE,
    )
    assert wg.name == "sq1"
    assert math.isclose(wg.value(-247 + 0 + random.randint(0, 100) * 1000), 1)
    assert math.isclose(wg.value(-247 + 125 + random.randint(0, 100) * 1000), 1)
    assert math.isclose(wg.value(-247 + 250 + random.randint(0, 100) * 1000), 1)
    assert math.isclose(wg.value(-247 + 375 + random.randint(0, 100) * 1000), 1)
    assert math.isclose(wg.value(-247 + 500 + random.randint(0, 100) * 1000), 0)
    assert math.isclose(wg.value(-247 + 625 + random.randint(0, 100) * 1000), 0)
    assert math.isclose(wg.value(-247 + 750 + random.randint(0, 100) * 1000), 0)


def test_imp():
    imp = ImpulseGenerator(
        name="imp",
        amp=2,
        offset=0.5,
        period=1000,
        echo=2,
        echo_decay=0.75,
        duty=300,
    )
    assert imp.name == "imp"
    assert math.isclose(imp.value(0), 2.5)
    assert math.isclose(imp.value(150), 2.5)
    assert math.isclose(imp.value(300), 0.5)
    assert math.isclose(imp.value(900), 0.5)
    assert math.isclose(imp.value(1000 + 0), 2)
    assert math.isclose(imp.value(1000 + 150), 2)
    assert math.isclose(imp.value(1000 + 300), 0.5)
    assert math.isclose(imp.value(1000 + 900), 0.5)
    assert math.isclose(imp.value(2000 + 0), 0.5)
    assert math.isclose(imp.value(2000 + 150), 0.5)
    assert math.isclose(imp.value(2000 + 300), 0.5)
    assert math.isclose(imp.value(2000 + 900), 0.5)


def test_noise():
    noise = NoiseGenerator(
        name="rand",
        amp=1,
        offset=0.5,
        period=1000,
    )
    assert noise.name == "rand"
    assert noise.value(0) == noise.value(600)
    assert noise.value(0) != noise.value(1100)
    assert noise.value(1200) == noise.value(1100)


def test_fft():
    fft = FFTGenerator(
        name="fft",
        amp=1,
        offset=0.5,
        subdivisions=20,
        memory_length=20,
    )
