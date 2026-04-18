"""Run the server for a fixed duration and print a timing summary table.

Usage: poetry run poe bench-timing
       poetry run poe bench-timing -- --tick-ms 10
"""

import re
import subprocess
import sys
import signal
import time
import threading


DURATION_S = 70
SERVER_CMD = [
    "poetry", "run", "server", "--local-ip", "127.0.0.1",
    "--boot-art-net", "--debug", "--audio-interface", "Loopback audio",
]


def main() -> None:
    extra_args = sys.argv[1:]
    cmd = SERVER_CMD + extra_args

    print("Starting server for {}s: {}".format(DURATION_S, " ".join(cmd)))
    print()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    lines: list[str] = []

    def reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line)

    read_thread = threading.Thread(target=reader, daemon=True)
    read_thread.start()

    time.sleep(DURATION_S)

    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    read_thread.join(timeout=2)

    tick_compute: list[float] = []
    tick_wall: list[float] = []
    tick_target: float = 0

    audio_process: list[float] = []
    audio_wall: list[float] = []
    audio_expected: float = 0

    fft_avg: list[float] = []
    fft_expected: float = 0

    beat_avg: list[float] = []

    tick_re = re.compile(
        r"DEBUG tick: compute_avg=([\d.]+)ms wall_avg=([\d.]+)ms target=(\d+)ms"
    )
    audio_re = re.compile(
        r"DEBUG audio capture tick \d+: process_avg=([\d.]+)ms "
        r"wall_avg=([\d.]+)ms expected=([\d.]+)ms"
    )
    fft_re = re.compile(
        r"DEBUG FFT tick \d+: fft_avg=([\d.]+)ms "
        r"beat_avg=([\d.]+)ms \(target=(\d+)ms\) "
        r"expected=([\d.]+)ms"
    )

    for line in lines:
        m = tick_re.search(line)
        if m:
            tick_compute.append(float(m.group(1)))
            tick_wall.append(float(m.group(2)))
            tick_target = float(m.group(3))
            continue
        m = audio_re.search(line)
        if m:
            audio_process.append(float(m.group(1)))
            audio_wall.append(float(m.group(2)))
            audio_expected = float(m.group(3))
            continue
        m = fft_re.search(line)
        if m:
            fft_avg.append(float(m.group(1)))
            beat_avg.append(float(m.group(2)))
            fft_expected = float(m.group(4))
            continue

    def fmt(values: list[float]) -> str:
        if not values:
            return "—"
        lo, hi = min(values), max(values)
        avg = sum(values) / len(values)
        if abs(lo - hi) < 0.05:
            return "{:.1f}ms".format(avg)
        return "{:.1f}–{:.1f}ms (avg {:.1f})".format(lo, hi, avg)

    def pct(value: float, target: float) -> str:
        if target <= 0 or value <= 0:
            return "—"
        return "{:.0f}%".format((1.0 - value / target) * 100)

    print()
    print("=" * 78)
    print("TIMING REPORT ({}s run)".format(DURATION_S))
    print("=" * 78)
    print()
    print("{:<22} {:<30} {:<12} {:<12}".format(
        "Loop", "Measured", "Target", "Headroom"
    ))
    print("-" * 78)

    if tick_compute:
        avg_c = sum(tick_compute) / len(tick_compute)
        print("{:<22} {:<30} {:<12} {:<12}".format(
            "Main tick compute", fmt(tick_compute),
            "{:.0f}ms".format(tick_target), pct(avg_c, tick_target),
        ))

    if tick_wall:
        avg_w = sum(tick_wall) / len(tick_wall)
        hz = 1000 / avg_w if avg_w > 0 else 0
        print("{:<22} {:<30} {:<12} {:<12}".format(
            "Main tick wall", fmt(tick_wall),
            "{:.0f}ms ({:.0f}Hz)".format(tick_target, 1000 / tick_target),
            "{:.0f}Hz actual".format(hz),
        ))

    if audio_process:
        avg_p = sum(audio_process) / len(audio_process)
        print("{:<22} {:<30} {:<12} {:<12}".format(
            "Audio capture process", fmt(audio_process),
            "{:.1f}ms".format(audio_expected), pct(avg_p, audio_expected),
        ))

    if audio_wall:
        print("{:<22} {:<30} {:<12} {:<12}".format(
            "Audio capture wall", fmt(audio_wall),
            "{:.1f}ms".format(audio_expected), "hw-paced",
        ))

    if fft_avg:
        avg_f = sum(fft_avg) / len(fft_avg)
        print("{:<22} {:<30} {:<12} {:<12}".format(
            "FFT forward", fmt(fft_avg),
            "{:.1f}ms".format(fft_expected), pct(avg_f, fft_expected),
        ))

    if beat_avg:
        nonzero = [b for b in beat_avg if b > 0]
        if nonzero:
            avg_b = sum(nonzero) / len(nonzero)
            print("{:<22} {:<30} {:<12} {:<12}".format(
                "Beat track", fmt(nonzero), "200ms", pct(avg_b, 200),
            ))
        else:
            print("{:<22} {:<30} {:<12} {:<12}".format(
                "Beat track", "never fired", "200ms", "—",
            ))

    print("-" * 78)

    if not tick_compute and not audio_process and not fft_avg:
        print("\nNo timing data collected. Is --debug set? Is audio connected?")


if __name__ == "__main__":
    main()
