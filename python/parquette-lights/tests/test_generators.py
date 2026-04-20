import math
import random
from parquette.lights.category import Category
from parquette.lights.generators import *
from parquette.lights.generators.bpm_generator import BPMGenerator
from parquette.lights.osc import OSCManager
from parquette.lights.util.session_store import SessionStore

_test_osc = OSCManager()
_test_session = SessionStore("/tmp/test_session.pickle")
TEST_CAT = Category("test", _test_osc, _test_session)


def test_wave_gen_sin():
    wg = WaveGenerator(
        name="sin1",
        category=TEST_CAT,
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
        category=TEST_CAT,
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
        category=TEST_CAT,
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
        category=TEST_CAT,
        amp=2,
        offset=0.5,
        duty=300,
    )
    assert imp.name == "imp"
    assert math.isclose(imp.value(0), 2.5)
    assert math.isclose(imp.value(150), 2.5)
    assert math.isclose(imp.value(300), 0.5)
    assert math.isclose(imp.value(900), 0.5)


def test_noise():
    noise = NoiseGenerator(
        name="rand",
        category=TEST_CAT,
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
        category=TEST_CAT,
        amp=1,
        offset=0.5,
        subdivisions=20,
        memory_length=20,
    )


def test_bpm_valid_gates_output():
    bpm = BPMGenerator(
        name="bpm", category=TEST_CAT, amp=255, offset=0, duty=500, bpm=120
    )

    assert bpm.bpm_valid is False
    assert bpm.rms_valid is False
    assert bpm.value(0) == 0
    assert bpm.value(100) == 0

    bpm.rms_valid = True
    bpm.bpm_valid = True
    # At t=0 with phase_time=0 and duty=500ms, t=0 is within the pulse window
    assert bpm.value(0) == 255
