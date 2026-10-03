#!/usr/bin/env python3
"""Harmonic analyzer, v2.1.

A louder octave partial is not reported as the fundamental. See BUG_ANALYSIS.md.

    python vocal_analyzer_corrected.py --demo
    python vocal_analyzer_corrected.py --wav note.wav
    python vocal_analyzer_corrected.py -d 20
    python vocal_analyzer_corrected.py --list-devices
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vocal_harmonics.analysis import analyze_frame, analyze_signal
from vocal_harmonics.audio import AudioBackendError, Microphone, list_input_devices, read_wav
from vocal_harmonics.constants import FRAME_SIZE, HOP_SIZE, MAX_F0_HZ, MIN_F0_HZ, SAMPLE_RATE
from vocal_harmonics.report import format_compact, format_report
from vocal_harmonics.synth import C_MAJOR, DIPHONIC, PIANO_MIDDLE_C, PURE_A4, synthesize


DEMOS = (
    (
        "Piano middle C — the octave is louder than the fundamental",
        "Do central au piano — l'octave est plus forte que la fondamentale",
        PIANO_MIDDLE_C,
    ),
    (
        "C major (Do majeur) — three fundamentals",
        "Accord de do majeur — trois fondamentales",
        C_MAJOR,
    ),
    (
        "Diphonic tone — the 4th harmonic is the strongest partial",
        "Chant diphonique — le 4e harmonique est le partiel le plus fort",
        DIPHONIC,
    ),
    (
        "Pure A4 (La4)",
        "La4 pur",
        PURE_A4,
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decompose a sustained tone into its harmonics.")
    parser.add_argument("-d", "--duration", type=float, default=8.0, help="Seconds of live input.")
    parser.add_argument("--device", type=int, default=None, help="Input device index.")
    parser.add_argument("--list-devices", action="store_true", help="Print input devices and exit.")
    parser.add_argument("--wav", help="Analyse a PCM WAV file instead of the microphone.")
    parser.add_argument("--demo", action="store_true", help="Analyse built-in tones, including the piano bug.")
    parser.add_argument("--self-test", action="store_true", help="Run the regression tests.")
    parser.add_argument("--lang", choices=("en", "fr"), default="en")
    parser.add_argument("--verbose", action="store_true", help="List peaks rejected as harmonics.")
    parser.add_argument("--min-f0", type=float, default=MIN_F0_HZ, help="Lowest fundamental, in Hz.")
    parser.add_argument("--max-f0", type=float, default=MAX_F0_HZ, help="Highest fundamental, in Hz.")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()
    if args.list_devices:
        return _print_devices()
    if args.demo and args.wav:
        print("Pass either --demo or --wav, not both.", file=sys.stderr)
        return 2
    if args.demo:
        _print_demos(args.lang, args.verbose, args.min_f0, args.max_f0)
        return 0
    if args.wav:
        return _analyze_file(args.wav, args.lang, args.verbose, args.min_f0, args.max_f0)
    return _analyze_live(
        args.device, args.duration, args.lang, args.verbose, args.min_f0, args.max_f0
    )


def _self_test() -> int:
    import unittest

    root = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def _print_devices() -> int:
    try:
        devices = list_input_devices()
    except AudioBackendError as exc:
        print(exc, file=sys.stderr)
        return 1
    if not devices:
        print("No input device found.")
        print("Windows: Settings → Privacy → Microphone → allow desktop apps.")
        return 1
    for device in devices:
        print(device.label())
    return 0


def _print_demos(language: str, verbose: bool, min_f0: float, max_f0: float) -> None:
    for title_en, title_fr, partials in DEMOS:
        print("=" * 72)
        print(title_fr if language == "fr" else title_en)
        print("=" * 72)
        signal = synthesize(partials, sample_rate=SAMPLE_RATE, seconds=1.0)
        analysis = analyze_signal(signal, SAMPLE_RATE, min_f0=min_f0, max_f0=max_f0)
        print(format_report(analysis, language, verbose))
        print()


def _analyze_file(path: str, language: str, verbose: bool, min_f0: float, max_f0: float) -> int:
    try:
        signal, sample_rate = read_wav(path)
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        return 1
    except AudioBackendError as exc:
        print(exc, file=sys.stderr)
        return 1
    if len(signal) < 1024:
        print("The recording is too short to analyse.", file=sys.stderr)
        return 1
    analysis = analyze_signal(signal, sample_rate, min_f0=min_f0, max_f0=max_f0)
    print(format_report(analysis, language, verbose))
    return 0


def _analyze_live(
    device: int | None,
    duration: float,
    language: str,
    verbose: bool,
    min_f0: float,
    max_f0: float,
) -> int:
    if duration <= 0:
        print("Duration must be positive.", file=sys.stderr)
        return 2
    print(f"Listening for {duration:.1f}s at {SAMPLE_RATE} Hz. Ctrl+C stops early.")
    collected = []
    try:
        with Microphone(device, SAMPLE_RATE, HOP_SIZE) as mic:
            buffer = np.zeros(0, dtype=np.float64)
            started = time.monotonic()
            next_print = 0.0
            while time.monotonic() - started < duration:
                chunk = mic.read(HOP_SIZE)
                collected.append(chunk)
                buffer = np.concatenate([buffer, chunk])[-FRAME_SIZE:]
                if len(buffer) < FRAME_SIZE:
                    continue
                elapsed = time.monotonic() - started
                if elapsed >= next_print:
                    analysis = analyze_frame(
                        buffer, SAMPLE_RATE, FRAME_SIZE, min_f0=min_f0, max_f0=max_f0
                    )
                    print(f"{elapsed:6.2f}s  {format_compact(analysis)}")
                    next_print = elapsed + 0.25
    except KeyboardInterrupt:
        print("\nStopped.")
    except AudioBackendError as exc:
        print(exc, file=sys.stderr)
        return 1
    if not collected:
        print("No audio was captured.", file=sys.stderr)
        return 1
    signal = np.concatenate(collected)
    print()
    analysis = analyze_signal(signal, SAMPLE_RATE, min_f0=min_f0, max_f0=max_f0)
    print(format_report(analysis, language, verbose))
    return 0


if __name__ == "__main__":
    sys.exit(main())
