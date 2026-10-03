"""Equal-tempered note names.

A4 is 440 Hz. The MIDI note number is

    midi = round(69 + 12 · log2(f / 440))

and the octave is ``midi // 12 - 1`` (MIDI 60 is C4). Cents measure the
distance to that nearest tempered pitch:

    cents = 1200 · log2(f / f_expected)

Indexing the semitone offset from A4 directly into a list that starts at C,
then truncating the octave toward zero, labels both 263.78 Hz and 522.18 Hz
as D#4. Those frequencies are C4 and C5.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EN_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FR_NAMES = ("Do", "Do#", "Ré", "Ré#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si")
EN_FLATS = {1: "Db", 3: "Eb", 6: "Gb", 8: "Ab", 10: "Bb"}
FR_FLATS = {1: "Réb", 3: "Mib", 6: "Solb", 8: "Lab", 10: "Sib"}

A4_HZ = 440.0
A4_MIDI = 69


@dataclass(frozen=True)
class Pitch:
    """Nearest equal-tempered pitch for a measured frequency."""

    frequency: float
    midi: int
    octave: int
    pitch_class_en: str
    pitch_class_fr: str
    name_en: str
    name_fr: str
    cents: float
    expected_hz: float

    def label(self) -> str:
        if self.name_en == self.name_fr:
            return self.name_en
        return f"{self.name_en} ({self.name_fr})"


def _spell(names: tuple[str, ...], flats: dict[int, str], index: int, octave: int) -> str:
    sharp = f"{names[index]}{octave}"
    flat = flats.get(index)
    if flat is None:
        return sharp
    return f"{sharp} / {flat}{octave}"


def describe_pitch(frequency: float) -> Pitch | None:
    """Map a positive frequency to the nearest tempered pitch, or None."""
    if frequency <= 0.0 or not math.isfinite(frequency):
        return None
    midi_float = A4_MIDI + 12.0 * math.log2(frequency / A4_HZ)
    midi = int(round(midi_float))
    index = midi % 12
    octave = midi // 12 - 1
    expected = A4_HZ * (2.0 ** ((midi - A4_MIDI) / 12.0))
    cents = 1200.0 * math.log2(frequency / expected)
    return Pitch(
        frequency=frequency,
        midi=midi,
        octave=octave,
        pitch_class_en=EN_NAMES[index],
        pitch_class_fr=FR_NAMES[index],
        name_en=_spell(EN_NAMES, EN_FLATS, index, octave),
        name_fr=_spell(FR_NAMES, FR_FLATS, index, octave),
        cents=cents,
        expected_hz=expected,
    )


def format_cents(cents: float) -> str:
    return f"{int(round(cents)):+d} cents"
