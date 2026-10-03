"""Shared signal-processing defaults for the vocal harmonics analyzer."""

SAMPLE_RATE = 44100
# Analysis window. 8192 samples is ~186 ms at 44.1 kHz: long enough for
# partials a semitone apart in the vocal range, short enough to follow a melody.
FRAME_SIZE = 8192
HOP_SIZE = 4096
# Peaks are searched up to this frequency; sung fundamentals sit much lower.
MAX_PARTIAL_HZ = 5000.0
MIN_F0_HZ = 75.0
MAX_F0_HZ = 1200.0
# Relative frequency tolerance for "this partial is k times the fundamental".
# 3% is about half a semitone, so neighboring notes are not merged.
HARMONIC_TOLERANCE = 0.03
# Peaks quieter than this fraction of the loudest partial are ignored.
MIN_PEAK_RATIO = 0.05
# A peak may seed a fundamental only if it reaches this fraction.
MIN_F0_RATIO = 0.10
MAX_HARMONICS = 12
MAX_FUNDAMENTALS = 6
# An inferred fundamental (no peak at f0 itself) needs this many partials.
MIN_INFERRED_PARTIALS = 3
