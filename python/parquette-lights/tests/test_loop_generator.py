import pytest

from parquette.lights.generators.loop_generator import LoopGenerator


def test_empty_buffer_returns_offset():
    gen = LoopGenerator(name="test", offset=42.0)
    assert gen.value(0.0) == 42.0
    assert gen.value(5000.0) == 42.0


def test_record_and_playback():
    gen = LoopGenerator(name="test", amp=1.0, offset=0.0, max_samples=100)

    # Record 5 samples over 100ms (20ms ticks)
    gen.set_recording(True, ts_ms=0.0)
    for i in range(5):
        gen.record_sample(float(i * 50))  # 0, 50, 100, 150, 200
    gen.set_recording(False, ts_ms=100.0)

    assert gen.loop_length == 5
    assert gen.period == 100.0

    # Playback at start of loop should return first sample
    assert gen.value(100.0) == pytest.approx(0.0)

    # Playback at end of first tick interval (20% through)
    # position = (20/100) * 5 = 1.0 → samples[1] = 50
    assert gen.value(120.0) == pytest.approx(50.0)


def test_loop_wrapping():
    gen = LoopGenerator(name="test", max_samples=100)
    gen.set_recording(True, ts_ms=0.0)
    gen.record_sample(100.0)
    gen.record_sample(200.0)
    gen.set_recording(False, ts_ms=40.0)

    # period=40ms, loop_length=2
    # At ts=40 (start): position=0 → 100
    assert gen.value(40.0) == pytest.approx(100.0)
    # At ts=60 (half): position=1 → 200
    assert gen.value(60.0) == pytest.approx(200.0)
    # At ts=80 (full loop): wraps to position=0 → 100
    assert gen.value(80.0) == pytest.approx(100.0)
    # Second loop: ts=100 → position=0 again
    assert gen.value(120.0) == pytest.approx(100.0)


def test_linear_interpolation():
    gen = LoopGenerator(name="test", max_samples=100)
    gen.set_recording(True, ts_ms=0.0)
    gen.record_sample(0.0)
    gen.record_sample(100.0)
    gen.set_recording(False, ts_ms=40.0)

    # period=40, loop_length=2
    # At ts=10 (25% through): position = (10/40)*2 = 0.5
    # interp: samples[0]*(1-0.5) + samples[1]*0.5 = 0 + 50 = 50
    assert gen.value(10.0) == pytest.approx(50.0)


def test_max_samples_cap():
    gen = LoopGenerator(name="test", max_samples=3)
    gen.set_recording(True, ts_ms=0.0)
    for i in range(10):
        gen.record_sample(float(i))
    # Should have auto-stopped at 3 samples
    assert gen.recording is False
    assert gen.loop_length == 3
    assert gen.samples == [0.0, 1.0, 2.0]


def test_empty_recording_noop():
    gen = LoopGenerator(name="test", max_samples=100)
    gen.set_recording(True, ts_ms=0.0)
    gen.set_recording(False, ts_ms=100.0)
    # No samples recorded, should stay empty
    assert gen.loop_length == 0
    assert gen.value(200.0) == gen.offset


def test_amp_and_offset():
    gen = LoopGenerator(name="test", amp=2.0, offset=10.0, max_samples=100)
    gen.set_recording(True, ts_ms=0.0)
    gen.record_sample(50.0)
    gen.set_recording(False, ts_ms=20.0)

    # Single sample loops forever: 50 * 2.0 + 10.0 = 110
    assert gen.value(20.0) == pytest.approx(110.0)
    assert gen.value(100.0) == pytest.approx(110.0)


def test_record_sample_ignored_when_not_recording():
    gen = LoopGenerator(name="test", max_samples=100)
    gen.record_sample(42.0)
    assert gen.loop_length == 0


def test_load_samples():
    gen = LoopGenerator(name="test", max_samples=100)
    gen.load_samples([10.0, 20.0, 30.0])
    assert gen.loop_length == 3
    assert gen.samples == [10.0, 20.0, 30.0]
