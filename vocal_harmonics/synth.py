"""Stationary test tones. No audio device required."""

from __future__ import annotations

import numpy as np

# Upright-piano middle C as reported by the user.
# The octave partial is louder than the fundamental (54.2% vs 100%).
PIANO_MIDDLE_C = (
    (263.78, 0.542),
    (522.18, 1.000),
    (785.96, 0.400),
    (1055.13, 0.250),
)

# C4 E4 G4, each with a weaker octave. 3·C4 and 2·G4 land on the same partial.
C_MAJOR = (
    (261.63, 1.00),
    (329.63, 0.85),
    (392.00, 0.70),
    (523.25, 0.45),
    (659.25, 0.35),
    (783.99, 0.30),
)

# Overtone singing: the 4th harmonic carries the tone color.
DIPHONIC = (
    (150.0, 0.20),
    (300.0, 0.12),
    (450.0, 0.12),
    (600.0, 1.00),
)

PURE_A4 = ((440.0, 1.0),)


def synthesize(
    partials: tuple[tuple[float, float], ...],
    sample_rate: int = 44100,
    seconds: float = 1.0,
    noise: float = 0.0,
    seed: int = 0,
) -> np.ndarray:
    """Sum of sines, peak-normalized to [-1, 1]."""
    count = int(sample_rate * seconds)
    time = np.arange(count, dtype=np.float64) / sample_rate
    signal = np.zeros(count, dtype=np.float64)
    for frequency, amplitude in partials:
        signal += amplitude * np.sin(2.0 * np.pi * frequency * time)
    if noise > 0.0:
        rng = np.random.default_rng(seed)
        signal += noise * rng.standard_normal(count)
    peak = float(np.max(np.abs(signal)))
    if peak > 0.0:
        signal /= peak
    return signal
