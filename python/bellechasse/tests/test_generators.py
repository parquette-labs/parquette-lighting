from bellechasse.generators import *
import math
import random

def test_wave_gen_sin():
    wg = WaveGenerator(name="sin1", shape=WaveGenerator.Shape.SIN, amp=0.5, phase=247, period=1000, offset=0.5)
    assert wg.name == "sin1"
    assert math.isclose(wg.value(-247+0+random.randint(0, 100)*1000), 0.5)
    assert math.isclose(wg.value(-247+125+random.randint(0, 100)*1000), 0.5+0.5/2**(0.5))
    assert math.isclose(wg.value(-247+250+random.randint(0, 100)*1000), 1)
    assert math.isclose(wg.value(-247+500+random.randint(0, 100)*1000), 0.5)
    assert math.isclose(wg.value(-247+750+random.randint(0, 100)*1000), 0)

def test_wave_gen_tri():
    wg = WaveGenerator(name="tri1", shape=WaveGenerator.Shape.TRIANGLE, amp=0.5, phase=247, period=1000, offset=0.5)
    assert wg.name == "tri1"
    assert math.isclose(wg.value(-247+0+random.randint(0, 100)*1000), 0.5)
    assert math.isclose(wg.value(-247+125+random.randint(0, 100)*1000), 0.75)
    assert math.isclose(wg.value(-247+250+random.randint(0, 100)*1000), 1)
    assert math.isclose(wg.value(-247+375+random.randint(0, 100)*1000), 0.75)
    assert math.isclose(wg.value(-247+500+random.randint(0, 100)*1000), 0.5)
    assert math.isclose(wg.value(-247+625+random.randint(0, 100)*1000), 0.25)
    assert math.isclose(wg.value(-247+750+random.randint(0, 100)*1000), 0)

def test_wave_sq():
    wg = WaveGenerator(name="sq1", shape=WaveGenerator.Shape.SQUARE, amp=0.5, phase=247, period=1000, offset=0.5)
    assert wg.name == "sq1"
    assert math.isclose(wg.value(-247+0+random.randint(0, 100)*1000), 1)
    assert math.isclose(wg.value(-247+125+random.randint(0, 100)*1000), 1)
    assert math.isclose(wg.value(-247+250+random.randint(0, 100)*1000), 1)
    assert math.isclose(wg.value(-247+375+random.randint(0, 100)*1000), 1)
    assert math.isclose(wg.value(-247+500+random.randint(0, 100)*1000), 0)
    assert math.isclose(wg.value(-247+625+random.randint(0, 100)*1000), 0)
    assert math.isclose(wg.value(-247+750+random.randint(0, 100)*1000), 0)
