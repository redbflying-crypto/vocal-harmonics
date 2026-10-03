"""Multi-pitch detection by harmonic series.

A sung or struck tone is a fundamental f0 plus integer partials 2·f0, 3·f0, …
On a piano the octave partial is often louder than f0. Ranking peaks by
loudness therefore reports the octave as the note. A peak is kept as a
fundamental only when no lower peak sits near f0/2, f0/3, … and when the
series it explains outranks octave duplicates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from vocal_harmonics.constants import (
    FRAME_SIZE,
    HARMONIC_TOLERANCE,
    HOP_SIZE,
    MAX_F0_HZ,
    MAX_FUNDAMENTALS,
    MAX_HARMONICS,
    MAX_PARTIAL_HZ,
    MIN_F0_HZ,
    MIN_F0_RATIO,
    MIN_INFERRED_PARTIALS,
    MIN_PEAK_RATIO,
    SAMPLE_RATE,
)
from vocal_harmonics.notes import Pitch, describe_pitch

__all__ = [
    "Analysis",
    "Fundamental",
    "Partial",
    "Peak",
    "Rejected",
    "analyze_frame",
    "analyze_signal",
    "find_subharmonic",
    "is_harmonic_of",
    "magnitude_spectrum",
]


@dataclass(frozen=True)
class Peak:
    frequency: float
    magnitude: float


@dataclass(frozen=True)
class Partial:
    multiple: int
    frequency: float
    magnitude: float
    pitch: Pitch | None


@dataclass(frozen=True)
class Rejected:
    frequency: float
    magnitude: float
    pitch: Pitch | None
    reason: str


@dataclass(frozen=True)
class Fundamental:
    frequency: float
    magnitude: float
    score: float
    inferred: bool
    pitch: Pitch | None
    partials: tuple[Partial, ...]

    @property
    def partial_count(self) -> int:
        return len(self.partials)


@dataclass(frozen=True)
class Analysis:
    fundamentals: tuple[Fundamental, ...]
    peaks: tuple[Peak, ...]
    rejected: tuple[Rejected, ...]
    sample_rate: int
    frequencies: np.ndarray = field(repr=False)
    magnitude: np.ndarray = field(repr=False)

    @property
    def loudest_peak(self) -> Peak | None:
        if not self.peaks:
            return None
        return max(self.peaks, key=lambda peak: peak.magnitude)


def is_harmonic_of(freq: float, fundamental: float, tolerance: float = HARMONIC_TOLERANCE) -> bool:
    """True when ``freq`` is an integer multiple k≥2 of ``fundamental``."""
    if fundamental <= 0.0 or freq <= 0.0:
        return False
    ratio = freq / fundamental
    nearest_int = round(ratio)
    if nearest_int < 2:
        return False
    return abs(ratio - nearest_int) / nearest_int < tolerance


def _as_frequency(peak: Peak | float) -> float:
    if isinstance(peak, Peak):
        return peak.frequency
    return float(peak)


def find_subharmonic(
    freq: float,
    peaks: list[Peak] | tuple[Peak, ...] | list[float],
    tolerance: float = HARMONIC_TOLERANCE,
    min_freq: float = MIN_F0_HZ,
) -> float | None:
    """Return the lower peak frequency that explains ``freq``, or None.

    Example: 522 Hz / 2 = 261 Hz. If a peak sits there, 522 Hz is a partial,
    not a second fundamental.
    """
    if freq <= 0.0:
        return None
    for divisor in (2, 3, 4, 5, 6):
        sub = freq / divisor
        if sub < min_freq:
            continue
        for peak in peaks:
            peak_freq = _as_frequency(peak)
            if abs(peak_freq - sub) / sub < tolerance:
                return peak_freq
    return None


def _frame_size_for(length: int) -> int:
    if length >= 16384:
        return 16384
    if length >= FRAME_SIZE:
        return FRAME_SIZE
    if length >= 4096:
        return 4096
    return max(length, 256)


def _fft_size(frame_size: int) -> int:
    padded = frame_size * 4
    power = 1 << (padded - 1).bit_length()
    return min(max(power, 16384), 131072)


def magnitude_spectrum(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    frame_size: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Hamming-windowed magnitude spectrum, zero-padded for peak interpolation."""
    samples = np.asarray(samples, dtype=np.float64)
    if frame_size is None:
        frame_size = _frame_size_for(len(samples))
    frame = _take_frame(samples, frame_size)
    frame = frame - float(np.mean(frame))
    window = np.hamming(frame_size)
    fft_size = _fft_size(frame_size)
    spectrum = np.fft.rfft(frame * window, n=fft_size)
    magnitude = np.abs(spectrum)
    frequencies = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)
    return frequencies, magnitude


def _take_frame(samples: np.ndarray, frame_size: int) -> np.ndarray:
    if len(samples) == frame_size:
        return samples
    if len(samples) < frame_size:
        padded = np.zeros(frame_size, dtype=np.float64)
        padded[: len(samples)] = samples
        return padded
    start = (len(samples) - frame_size) // 2
    return samples[start : start + frame_size]


def _refine_frequency(freqs: np.ndarray, magnitude: np.ndarray, index: int) -> float:
    """Sub-bin peak frequency from log-magnitude parabolic interpolation."""
    if index <= 0 or index >= len(magnitude) - 1:
        return float(freqs[index])
    alpha = math.log(float(magnitude[index - 1]) + 1e-20)
    beta = math.log(float(magnitude[index]) + 1e-20)
    gamma = math.log(float(magnitude[index + 1]) + 1e-20)
    denominator = alpha - 2.0 * beta + gamma
    if abs(denominator) < 1e-12:
        return float(freqs[index])
    delta = 0.5 * (alpha - gamma) / denominator
    delta = max(-0.5, min(0.5, delta))
    bin_hz = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 0.0
    return float(freqs[index]) + delta * bin_hz


def _find_peaks(
    freqs: np.ndarray,
    magnitude: np.ndarray,
    sample_rate: int,
    frame_size: int,
    fmin: float,
    fmax: float,
    min_ratio: float,
) -> list[Peak]:
    band = (freqs >= fmin) & (freqs <= fmax)
    if not np.any(band):
        return []
    loudest = float(np.max(magnitude[band]))
    if loudest <= 0.0:
        return []
    threshold = min_ratio * loudest
    min_separation = sample_rate / frame_size
    raw: list[Peak] = []
    for index in range(1, len(magnitude) - 1):
        frequency = float(freqs[index])
        if frequency < fmin or frequency > fmax:
            continue
        level = float(magnitude[index])
        if level < threshold:
            continue
        if level < float(magnitude[index - 1]) or level <= float(magnitude[index + 1]):
            continue
        raw.append(Peak(_refine_frequency(freqs, magnitude, index), level))
    raw.sort(key=lambda peak: peak.magnitude, reverse=True)
    kept: list[Peak] = []
    for peak in raw:
        if all(abs(peak.frequency - other.frequency) >= min_separation for other in kept):
            kept.append(peak)
    kept.sort(key=lambda peak: peak.frequency)
    return kept


def _allowed_hz(target: float, sample_rate: int, frame_size: int, tolerance: float) -> float:
    bin_hz = sample_rate / frame_size
    return min(max(tolerance * target, 1.25 * bin_hz), 0.055 * target)


def _match_partials(
    fundamental: float,
    peaks: list[Peak],
    sample_rate: int,
    frame_size: int,
    tolerance: float,
    max_partial_hz: float,
) -> list[tuple[int, Peak]]:
    matched: list[tuple[int, Peak]] = []
    used: set[int] = set()
    for multiple in range(1, MAX_HARMONICS + 1):
        target = multiple * fundamental
        if target > max_partial_hz:
            break
        allowed = _allowed_hz(target, sample_rate, frame_size, tolerance)
        best_index = None
        best_distance = None
        for index, peak in enumerate(peaks):
            if index in used:
                continue
            distance = abs(peak.frequency - target)
            if distance <= allowed and (best_distance is None or distance < best_distance):
                best_distance = distance
                best_index = index
        if best_index is not None:
            used.add(best_index)
            matched.append((multiple, peaks[best_index]))
    return matched


def _series_score(matched: list[tuple[int, Peak]]) -> float:
    if not matched:
        return 0.0
    multiples = [multiple for multiple, _peak in matched]
    energy = sum(peak.magnitude / math.sqrt(multiple) for multiple, peak in matched)
    score = energy * len(matched)
    if 1 not in multiples:
        # No energy at f0 itself: this may be a missing-fundamental hypothesis.
        score *= 0.55
    if all(multiple % 2 == 0 for multiple in multiples):
        # Only even partials: f0 is likely half the real period (octave error).
        score *= 0.45
    return score


def _candidate_frequencies(peaks: list[Peak], min_f0: float, max_f0: float, tolerance: float) -> list[float]:
    raw: list[float] = []
    for peak in peaks:
        if min_f0 <= peak.frequency <= max_f0:
            raw.append(peak.frequency)
        for divisor in (2, 3, 4, 5, 6):
            inferred = peak.frequency / divisor
            if min_f0 <= inferred <= max_f0:
                raw.append(inferred)
    if not raw:
        return []
    raw.sort()
    merged = [raw[0]]
    for frequency in raw[1:]:
        if abs(frequency - merged[-1]) / merged[-1] < tolerance * 0.5:
            merged[-1] = 0.5 * (merged[-1] + frequency)
        else:
            merged.append(frequency)
    # Prefer an observed peak frequency over a merged average.
    snapped: list[float] = []
    for frequency in merged:
        nearby = [
            peak.frequency
            for peak in peaks
            if abs(peak.frequency - frequency) / frequency < tolerance * 0.5
        ]
        snapped.append(nearby[0] if nearby else frequency)
    return snapped


def _nearest_peak(frequency: float, peaks: list[Peak], tolerance: float) -> Peak | None:
    best = None
    best_error = tolerance
    for peak in peaks:
        error = abs(peak.frequency - frequency) / frequency
        if error < best_error:
            best_error = error
            best = peak
    return best


def _reason_harmonic(frequency: float, keeper: float) -> str:
    ratio = frequency / keeper if frequency > keeper else keeper / frequency
    multiple = max(2, round(ratio))
    if frequency > keeper:
        return f"harmonic of {keeper:.2f} Hz (≈{multiple}×)"
    return f"sub-octave of {keeper:.2f} Hz (that note is ≈{multiple}× this candidate)"


def analyze_frame(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    frame_size: int | None = None,
    min_f0: float = MIN_F0_HZ,
    max_f0: float = MAX_F0_HZ,
    tolerance: float = HARMONIC_TOLERANCE,
) -> Analysis:
    """Detect fundamentals in one window of audio."""
    samples = np.asarray(samples, dtype=np.float64)
    if frame_size is None:
        frame_size = _frame_size_for(len(samples))
    frequencies, magnitude = magnitude_spectrum(samples, sample_rate, frame_size)
    peaks = _find_peaks(
        frequencies,
        magnitude,
        sample_rate,
        frame_size,
        fmin=min_f0 * 0.85,
        fmax=MAX_PARTIAL_HZ,
        min_ratio=MIN_PEAK_RATIO,
    )
    return _interpret_peaks(
        peaks,
        frequencies,
        magnitude,
        sample_rate,
        frame_size,
        min_f0,
        max_f0,
        tolerance,
    )


def analyze_signal(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    frame_size: int | None = None,
    min_f0: float = MIN_F0_HZ,
    max_f0: float = MAX_F0_HZ,
    tolerance: float = HARMONIC_TOLERANCE,
) -> Analysis:
    """Detect fundamentals from a longer recording.

    Uses the mean magnitude of the loudest windows so a sustained note is
    stable and leading or trailing silence does not dominate.
    """
    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim > 1:
        samples = np.mean(samples, axis=1)
    if frame_size is None:
        frame_size = _frame_size_for(len(samples))
    frames = _loud_frames(samples, frame_size, HOP_SIZE)
    fft_size = _fft_size(frame_size)
    window = np.hamming(frame_size)
    accumulator = np.zeros(fft_size // 2 + 1, dtype=np.float64)
    for frame in frames:
        centered = frame - float(np.mean(frame))
        accumulator += np.abs(np.fft.rfft(centered * window, n=fft_size))
    accumulator /= max(len(frames), 1)
    freqs = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)
    peaks = _find_peaks(
        freqs,
        accumulator,
        sample_rate,
        frame_size,
        fmin=min_f0 * 0.85,
        fmax=MAX_PARTIAL_HZ,
        min_ratio=MIN_PEAK_RATIO,
    )
    return _interpret_peaks(
        peaks,
        freqs,
        accumulator,
        sample_rate,
        frame_size,
        min_f0,
        max_f0,
        tolerance,
    )


def _loud_frames(samples: np.ndarray, frame_size: int, hop: int, limit: int = 8) -> list[np.ndarray]:
    if len(samples) <= frame_size:
        return [_take_frame(samples, frame_size)]
    starts = list(range(0, len(samples) - frame_size + 1, hop))
    if not starts:
        return [_take_frame(samples, frame_size)]
    loudness = []
    for start in starts:
        frame = samples[start : start + frame_size]
        loudness.append(float(np.sqrt(np.mean(frame * frame))))
    chosen = sorted(np.argsort(loudness)[-limit:])
    return [samples[starts[index] : starts[index] + frame_size] for index in chosen]


def _interpret_peaks(
    peaks: list[Peak],
    frequencies: np.ndarray,
    magnitude: np.ndarray,
    sample_rate: int,
    frame_size: int,
    min_f0: float,
    max_f0: float,
    tolerance: float,
) -> Analysis:
    loudest = max((peak.magnitude for peak in peaks), default=0.0)
    candidates = _candidate_frequencies(peaks, min_f0, max_f0, tolerance)
    scored: list[tuple[float, float, list[tuple[int, Peak]], bool]] = []
    for frequency in candidates:
        matched = _match_partials(
            frequency, peaks, sample_rate, frame_size, tolerance, MAX_PARTIAL_HZ
        )
        anchor = _nearest_peak(frequency, peaks, tolerance)
        inferred = anchor is None
        multiples = {multiple for multiple, _peak in matched}
        if inferred and (1 in multiples or len(matched) < MIN_INFERRED_PARTIALS):
            continue
        if not inferred and anchor is not None and anchor.magnitude < MIN_F0_RATIO * loudest:
            continue
        if not inferred and 1 not in multiples:
            continue
        # Re-anchor on the observed fundamental peak so cents use the real partial.
        if anchor is not None and 1 in multiples:
            frequency = anchor.frequency
            matched = _match_partials(
                frequency, peaks, sample_rate, frame_size, tolerance, MAX_PARTIAL_HZ
            )
        score = _series_score(matched)
        if score <= 0.0:
            continue
        scored.append((score, frequency, matched, inferred))

    scored.sort(key=lambda item: (-item[0], item[1]))
    accepted: list[tuple[float, float, list[tuple[int, Peak]], bool]] = []
    rejected: list[Rejected] = []
    for score, frequency, matched, inferred in scored:
        if len(accepted) >= MAX_FUNDAMENTALS:
            break
        veto = None if inferred else find_subharmonic(frequency, peaks, tolerance, min_f0)
        if veto is not None:
            multiple = max(2, round(frequency / veto))
            rejected.append(
                _rejection(frequency, peaks, f"harmonic of {veto:.2f} Hz (≈{multiple}×)")
            )
            continue
        blocked = False
        for kept_score, kept_freq, _kept_matched, _kept_inferred in accepted:
            if is_harmonic_of(frequency, kept_freq, tolerance):
                rejected.append(_rejection(frequency, peaks, _reason_harmonic(frequency, kept_freq)))
                blocked = True
                break
            if is_harmonic_of(kept_freq, frequency, tolerance):
                # A lower duplicate of a series we already accepted.
                if score <= kept_score:
                    rejected.append(
                        _rejection(frequency, peaks, _reason_harmonic(frequency, kept_freq))
                    )
                    blocked = True
                    break
            if abs(math.log2(frequency / kept_freq)) * 1200.0 < 50.0:
                rejected.append(_rejection(frequency, peaks, f"same note as {kept_freq:.2f} Hz"))
                blocked = True
                break
        if blocked:
            continue
        accepted.append((score, frequency, matched, inferred))

    best_score = accepted[0][0] if accepted else 1.0
    fundamentals = tuple(
        _build_fundamental(frequency, matched, inferred, score, best_score)
        for score, frequency, matched, inferred in accepted
    )
    return Analysis(
        fundamentals=fundamentals,
        peaks=tuple(peaks),
        rejected=tuple(rejected),
        sample_rate=sample_rate,
        frequencies=frequencies,
        magnitude=magnitude,
    )


def _rejection(frequency: float, peaks: list[Peak], reason: str) -> Rejected:
    peak = _nearest_peak(frequency, peaks, HARMONIC_TOLERANCE)
    magnitude = peak.magnitude if peak is not None else 0.0
    shown = peak.frequency if peak is not None else frequency
    return Rejected(shown, magnitude, describe_pitch(shown), reason)


def _build_fundamental(
    frequency: float,
    matched: list[tuple[int, Peak]],
    inferred: bool,
    score: float,
    best_score: float,
) -> Fundamental:
    anchor = next((peak for multiple, peak in matched if multiple == 1), None)
    magnitude = anchor.magnitude if anchor is not None else 0.0
    partials = tuple(
        Partial(
            multiple=multiple,
            frequency=peak.frequency,
            magnitude=peak.magnitude,
            pitch=describe_pitch(peak.frequency),
        )
        for multiple, peak in matched
    )
    return Fundamental(
        frequency=frequency,
        magnitude=magnitude,
        score=score / best_score if best_score else 0.0,
        inferred=inferred,
        pitch=describe_pitch(frequency),
        partials=partials,
    )
