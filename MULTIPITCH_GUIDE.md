# Multipitch harmonic analysis

A sustained tone is not one frequency. It is a fundamental f0 (the pitch you name) plus integer partials 2·f0, 3·f0, 4·f0, … that make the timbre.

Several fundamentals can be present at once:

- a chord, sung or played
- two singers
- overtone singing, where a high partial is louder than f0

The analyzer separates those fundamentals from their partials. Code and names below match `vocal_harmonics/analysis.py`.

## Spectrum

- Sample rate 44.1 kHz.
- Analysis window 8192 samples (about 186 ms) when the recording is long enough, 16384 samples for a file or a demo. Shorter clips fall back to 4096.
- Hamming window, then a zero-padded real FFT.
- The peak frequency is refined by parabolic interpolation on the log magnitude, so the cents figure is finer than one FFT bin.
- Peaks below 5% of the loudest partial are dropped. Partials are searched up to 5000 Hz.

## Which peaks are fundamentals?

```text
1. Find spectral peaks.
2. Candidate f0 values are the peaks between 75 Hz and 1200 Hz,
   plus f/2, f/3, … f/6 when that would explain a missing fundamental.
3. For each candidate, collect peaks near k·f0 for k = 1…12.
4. Score the series by how many partials it explains and how strong they are.
   Penalize a candidate with no energy at f0, and a candidate whose
   partials are all even (classic octave error).
5. Walk the candidates from the best score downward.
   Reject a peak when a lower peak already explains it:

       522 Hz / 2 ≈ 261 Hz, and 261 Hz is a peak
       → 522 Hz is a partial, not a second note.
```

```python
def is_harmonic_of(freq, fundamental, tolerance=0.03):
    ratio = freq / fundamental
    nearest_int = round(ratio)
    if nearest_int < 2:
        return False
    return abs(ratio - nearest_int) / nearest_int < tolerance


def find_subharmonic(freq, peaks, tolerance=0.03, min_freq=75.0):
    """Return the lower peak that explains freq, or None."""
    for divisor in (2, 3, 4, 5, 6):
        sub = freq / divisor
        if sub < min_freq:
            continue
        for peak in peaks:
            if abs(peak - sub) / sub < tolerance:
                return peak
    return None
```

Tolerance is 3% of the target frequency (about half a semitone), and never more than about one semitone. A fifth (ratio 1.5) is not an integer multiple, so C4 and G4 both stay.

## Pitch names

Equal temperament, A4 = 440 Hz.

```python
midi = round(69 + 12 * log2(f / 440))
cents = 1200 * log2(f / (440 * 2 ** ((midi - 69) / 12)))
```

Pitch classes: C C# D D# E F F# G G# A A# B.
Black keys are also spelled as flats: `D#4 / Eb4`.
French names are shown beside them: Do, Ré, Mi, Fa, Sol, La, Si.

| English | French | Octave 4 |
|---|---|---|
| C4 | Do4 | 261.63 Hz |
| D4 | Ré4 | 293.66 Hz |
| E4 | Mi4 | 329.63 Hz |
| F4 | Fa4 | 349.23 Hz |
| G4 | Sol4 | 392.00 Hz |
| A4 | La4 | 440.00 Hz |
| B4 | Si4 | 493.88 Hz |

## Examples

Single tone, or a piano note whose octave is louder:

```text
FUNDAMENTAL #1: 263.8 Hz  C4 (Do4)  +14 cents
  1×  263.8 Hz   C4
  2×  522.2 Hz   C5    ← louder, still not a fundamental
  3×  786.0 Hz   G5
  4× 1055.1 Hz   C6
```

C major chord:

```text
FUNDAMENTAL #1: 261.63 Hz  C4
FUNDAMENTAL #2: 329.63 Hz  E4
FUNDAMENTAL #3: 392.00 Hz  G4
```

Overtone singing, strong 4th partial:

```text
FUNDAMENTAL #1: 150 Hz  D3
  4×  600 Hz  D5   ← strongest partial, same fundamental
```

Run these three cases with no microphone:

```bash
python vocal_analyzer_corrected.py --demo
```

## Limits

- The window must be long enough to separate the partials. Very low semitones on a 4096-sample window can merge.
- Two pure tones exactly an octave apart collapse to the lower one. A third or a fifth does not.
- A missing fundamental is inferred only when at least three partials agree. If the spectrum contains only even partials, the reported pitch may be the octave.
- Inharmonicity (piano stretch) is absorbed by the 3% tolerance for the first partials. A very sharp high partial can fall outside the series.

## Troubleshooting

| What you see | What to check |
|---|---|
| No fundamental | Level too low, or f0 outside 75–1200 Hz. Try `--min-f0 40` for a low piano note. |
| Octave reported as the note | Should not happen when the lower peak exists. Run `--self-test`. |
| Extra fundamentals | Noise peaks above 10% of the loudest partial. `--verbose` lists rejected candidates. |
| `-9996` from PyAudio | No default device. `python audio_device_diagnostic.py` then `--device N`. |
| Note name looks shifted | Fixed in v2.1. Names come from the MIDI number, not from the raw offset to A4. |
