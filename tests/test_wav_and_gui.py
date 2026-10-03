"""WAV round-trip and the GUI piano demo, without a microphone."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vocal_harmonics.analysis import analyze_signal
from vocal_harmonics.audio import read_wav
from vocal_harmonics.synth import PIANO_MIDDLE_C, synthesize


SR = 44100


class WavTests(unittest.TestCase):
    def test_piano_wav_round_trip(self):
        signal = synthesize(PIANO_MIDDLE_C, sample_rate=SR, seconds=1.0)
        stereo = np.column_stack([signal, 0.5 * signal])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "piano.wav"
            _write_wav(path, stereo, SR)
            loaded, sample_rate = read_wav(str(path))
        self.assertEqual(sample_rate, SR)
        analysis = analyze_signal(loaded, sample_rate)
        self.assertEqual(len(analysis.fundamentals), 1)
        fundamental = analysis.fundamentals[0]
        self.assertEqual(fundamental.pitch.pitch_class_en, "C")
        self.assertEqual(fundamental.pitch.octave, 4)
        self.assertAlmostEqual(fundamental.frequency, 263.78, delta=2.0)


class GuiTests(unittest.TestCase):
    def test_piano_demo_fills_report_and_spectrum(self):
        if not os.environ.get("DISPLAY"):
            self.skipTest("no DISPLAY")
        import tkinter as tk

        from vocal_harmonics_analyzer import App

        root = tk.Tk()
        root.withdraw()
        captured: dict[str, str] = {}

        def finish() -> None:
            captured["text"] = app.report.get("1.0", "end")
            captured["items"] = str(len(app.canvas.find_all()))
            root.quit()

        try:
            app = App(root)
            root.after(100, app.show_piano_demo)
            root.after(250, finish)
            root.after(2000, root.quit)
            root.mainloop()
        finally:
            root.destroy()
        text = captured.get("text", "")
        self.assertIn("C4 (Do4)", text)
        self.assertIn("522.18", text)
        self.assertIn("stronger than the fundamental", text)
        self.assertGreater(int(captured.get("items", "0")), 10)
        self.assertIn("Piano demo", app.status.get())


def _write_wav(path: Path, signal: np.ndarray, sample_rate: int) -> None:
    clipped = np.clip(signal, -1.0, 1.0)
    if clipped.ndim == 1:
        clipped = clipped[:, None]
    pcm = (clipped * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(pcm.shape[1])
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


if __name__ == "__main__":
    unittest.main()
