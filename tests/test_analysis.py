"""Regression tests for multi-pitch detection.

The piano case is the bug from the upright-piano recording: the octave
partial at 522 Hz was louder than middle C, and both were labeled D#4.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vocal_harmonics.analysis import analyze_frame, analyze_signal, find_subharmonic, is_harmonic_of
from vocal_harmonics.notes import describe_pitch
from vocal_harmonics.synth import C_MAJOR, DIPHONIC, PIANO_MIDDLE_C, PURE_A4, synthesize


SR = 44100


def _frame(partials, noise=0.0):
    signal = synthesize(partials, sample_rate=SR, seconds=16384 / SR, noise=noise)
    return analyze_frame(signal, SR)


class NoteNamingTests(unittest.TestCase):
    def test_piano_frequencies_are_c_not_d_sharp(self):
        low = describe_pitch(263.78)
        high = describe_pitch(522.18)
        self.assertIsNotNone(low)
        self.assertIsNotNone(high)
        assert low is not None and high is not None
        self.assertEqual(low.pitch_class_en, "C")
        self.assertEqual(low.octave, 4)
        self.assertEqual(high.pitch_class_en, "C")
        self.assertEqual(high.octave, 5)
        self.assertAlmostEqual(low.cents, 14.2, delta=1.0)
        self.assertAlmostEqual(high.cents, -3.5, delta=1.0)
        self.assertEqual(low.pitch_class_fr, "Do")
        self.assertEqual(describe_pitch(440.0).name_en, "A4")
        self.assertEqual(describe_pitch(440.0).name_fr, "La4")

    def test_black_keys_show_sharp_and_flat(self):
        pitch = describe_pitch(311.13)  # D#4 / Eb4
        self.assertIsNotNone(pitch)
        assert pitch is not None
        self.assertIn("D#4", pitch.name_en)
        self.assertIn("Eb4", pitch.name_en)
        self.assertIn("Ré#4", pitch.name_fr)
        self.assertIn("Mib4", pitch.name_fr)


class HarmonicRelationTests(unittest.TestCase):
    def test_is_harmonic_of(self):
        self.assertTrue(is_harmonic_of(522.18, 263.78))
        self.assertFalse(is_harmonic_of(263.78, 522.18))
        self.assertFalse(is_harmonic_of(392.00, 261.63))  # a fifth, not an integer partial
        self.assertTrue(is_harmonic_of(784.0, 392.0))

    def test_subharmonic_veto_on_the_loud_octave(self):
        peaks = [263.78, 522.18, 785.96, 1055.13]
        self.assertIsNotNone(find_subharmonic(522.18, peaks))
        self.assertIsNone(find_subharmonic(263.78, peaks))
        self.assertIsNotNone(find_subharmonic(785.96, peaks))
        self.assertIsNotNone(find_subharmonic(1055.13, peaks))


class DetectionTests(unittest.TestCase):
    def test_piano_octave_is_not_the_fundamental(self):
        analysis = _frame(PIANO_MIDDLE_C)
        self.assertEqual(len(analysis.fundamentals), 1, _dump(analysis))
        fundamental = analysis.fundamentals[0]
        self.assertAlmostEqual(fundamental.frequency, 263.78, delta=2.0)
        self.assertEqual(fundamental.pitch.pitch_class_en, "C")
        self.assertEqual(fundamental.pitch.octave, 4)
        self.assertGreater(fundamental.pitch.cents, 5)
        self.assertLess(fundamental.pitch.cents, 25)
        multiples = [partial.multiple for partial in fundamental.partials]
        self.assertEqual(multiples[:4], [1, 2, 3, 4])
        octave = fundamental.partials[1]
        self.assertAlmostEqual(octave.frequency, 522.18, delta=3.0)
        self.assertGreater(octave.magnitude, fundamental.magnitude)
        self.assertTrue(all(abs(item.frequency - 522.18) > 20 for item in analysis.fundamentals))

    def test_piano_signal_average_matches_the_frame(self):
        signal = synthesize(PIANO_MIDDLE_C, sample_rate=SR, seconds=1.2)
        analysis = analyze_signal(signal, SR)
        self.assertEqual(len(analysis.fundamentals), 1, _dump(analysis))
        self.assertEqual(analysis.fundamentals[0].pitch.pitch_class_en, "C")
        self.assertEqual(analysis.fundamentals[0].pitch.octave, 4)

    def test_pure_a4(self):
        analysis = _frame(PURE_A4)
        self.assertEqual(len(analysis.fundamentals), 1, _dump(analysis))
        fundamental = analysis.fundamentals[0]
        self.assertEqual(fundamental.pitch.name_en, "A4")
        self.assertAlmostEqual(fundamental.frequency, 440.0, delta=1.0)
        self.assertAlmostEqual(fundamental.pitch.cents, 0.0, delta=8.0)

    def test_c_major_keeps_three_fundamentals(self):
        analysis = _frame(C_MAJOR)
        classes = {(item.pitch.pitch_class_en, item.pitch.octave) for item in analysis.fundamentals}
        self.assertEqual(classes, {("C", 4), ("E", 4), ("G", 4)}, _dump(analysis))
        # The octave partials of the chord must not become extra fundamentals.
        self.assertEqual(len(analysis.fundamentals), 3)

    def test_diphonic_keeps_the_low_fundamental(self):
        analysis = _frame(DIPHONIC)
        self.assertEqual(len(analysis.fundamentals), 1, _dump(analysis))
        fundamental = analysis.fundamentals[0]
        self.assertAlmostEqual(fundamental.frequency, 150.0, delta=2.0)
        multiples = [partial.multiple for partial in fundamental.partials]
        self.assertIn(4, multiples)
        fourth = next(partial for partial in fundamental.partials if partial.multiple == 4)
        self.assertGreater(fourth.magnitude, fundamental.magnitude)

    def test_semitone_dyad_is_not_merged(self):
        analysis = _frame(((261.63, 1.0), (277.18, 0.9)))
        classes = {item.pitch.pitch_class_en for item in analysis.fundamentals}
        self.assertEqual(classes, {"C", "C#"}, _dump(analysis))

    def test_light_noise_does_not_invent_a_second_note(self):
        analysis = _frame(PIANO_MIDDLE_C, noise=0.01)
        self.assertEqual(len(analysis.fundamentals), 1, _dump(analysis))
        self.assertEqual(analysis.fundamentals[0].pitch.pitch_class_en, "C")


def _dump(analysis) -> str:
    lines = []
    for item in analysis.fundamentals:
        note = item.pitch.label() if item.pitch else "?"
        partials = ", ".join(f"{partial.multiple}×{partial.frequency:.1f}" for partial in item.partials)
        lines.append(f"{item.frequency:.2f} Hz {note} score={item.score:.2f} [{partials}]")
    if analysis.rejected:
        lines.append("rejected: " + "; ".join(f"{item.frequency:.1f} {item.reason}" for item in analysis.rejected))
    return "\n".join(lines)


if __name__ == "__main__":
    unittest.main()
