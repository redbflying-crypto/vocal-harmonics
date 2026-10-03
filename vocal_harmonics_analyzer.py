#!/usr/bin/env python3
"""Realtime harmonic analyzer with a device picker and a spectrum view.

The microphone needs PyAudio. Demo and Open WAV work without it.

    python vocal_harmonics_analyzer.py
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from vocal_harmonics.analysis import Analysis, analyze_frame, analyze_signal
from vocal_harmonics.audio import AudioBackendError, Microphone, list_input_devices, read_wav
from vocal_harmonics.constants import FRAME_SIZE, HOP_SIZE, SAMPLE_RATE
from vocal_harmonics.report import format_report
from vocal_harmonics.synth import PIANO_MIDDLE_C, synthesize

BG = "#14171c"
PANEL = "#1c2129"
FG = "#e7e4df"
MUTED = "#9aa3ad"
ACCENT = "#3dbea5"
HARMONIC = "#e0a45a"
GRID = "#2a313c"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Vocal Harmonics Analyzer")
        self.root.configure(bg=BG)
        self.root.geometry("920x760")
        self.language = tk.StringVar(value="en")
        self.status = tk.StringVar(value="Choose a microphone, open a WAV file, or run the piano demo.")
        self.events: queue.Queue = queue.Queue()
        self.running = False
        self.worker: threading.Thread | None = None
        self.devices: list = []
        self._build()
        self.refresh_devices()

    def _build(self) -> None:
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(bar, text="Device", bg=BG, fg=FG).pack(side="left")
        self.device_box = ttk.Combobox(bar, state="readonly", width=52)
        self.device_box.pack(side="left", padx=8)
        self._button(bar, "Refresh", self.refresh_devices).pack(side="left", padx=2)
        self.start_button = self._button(bar, "Start", self.start)
        self.start_button.pack(side="left", padx=2)
        self._button(bar, "Stop", self.stop).pack(side="left", padx=2)
        self._button(bar, "Open WAV", self.open_wav).pack(side="left", padx=2)
        self._button(bar, "Piano demo", self.show_piano_demo).pack(side="left", padx=2)

        lang = tk.Frame(self.root, bg=BG)
        lang.pack(fill="x", padx=12)
        tk.Label(lang, text="Labels", bg=BG, fg=MUTED).pack(side="left")
        tk.Radiobutton(
            lang, text="English", variable=self.language, value="en",
            command=self._relabel, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
        ).pack(side="left", padx=8)
        tk.Radiobutton(
            lang, text="Français", variable=self.language, value="fr",
            command=self._relabel, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
        ).pack(side="left")

        self.canvas = tk.Canvas(
            self.root, width=880, height=260, bg="#0e1116", highlightthickness=0
        )
        self.canvas.pack(fill="x", padx=12, pady=10)
        self.report = tk.Text(
            self.root, height=18, bg=PANEL, fg=FG, insertbackground=FG,
            relief="flat", wrap="none", font=("DejaVu Sans Mono", 11),
        )
        self.report.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        tk.Label(
            self.root, textvariable=self.status, anchor="w", bg=BG, fg=MUTED
        ).pack(fill="x", padx=12, pady=(0, 10))
        self._last_analysis: Analysis | None = None

    def _button(self, parent: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, bg="#2a313c", fg=FG,
            activebackground=ACCENT, activeforeground="#10211e", relief="flat", padx=10, pady=4,
        )

    def refresh_devices(self) -> None:
        try:
            self.devices = list_input_devices()
        except AudioBackendError as exc:
            self.devices = []
            self.device_box["values"] = []
            self.device_box.set("")
            self.status.set(str(exc).splitlines()[0])
            return
        labels = [device.label() for device in self.devices]
        self.device_box["values"] = labels
        if not labels:
            self.device_box.set("")
            self.status.set("No input device. Open a WAV file or run the piano demo.")
            return
        default = next((i for i, device in enumerate(self.devices) if device.is_default), 0)
        self.device_box.current(default)
        self.status.set("Ready.")

    def selected_device(self) -> int | None:
        index = self.device_box.current()
        if index < 0 or index >= len(self.devices):
            return None
        return self.devices[index].index

    def start(self) -> None:
        if self.running:
            return
        device = self.selected_device()
        if device is None and not self.devices:
            self.status.set("No microphone. Use Piano demo or Open WAV.")
            return
        self.running = True
        self.status.set("Listening…")
        self.worker = threading.Thread(target=self._capture, args=(device,), daemon=True)
        self.worker.start()
        self.root.after(80, self._poll)

    def stop(self) -> None:
        self.running = False
        if self.status.get().startswith("Listening"):
            self.status.set("Stopped.")

    def _capture(self, device: int | None) -> None:
        try:
            with Microphone(device, SAMPLE_RATE, HOP_SIZE) as mic:
                buffer = np.zeros(0, dtype=np.float64)
                while self.running:
                    chunk = mic.read(HOP_SIZE)
                    buffer = np.concatenate([buffer, chunk])
                    if len(buffer) > FRAME_SIZE:
                        buffer = buffer[-FRAME_SIZE:]
                    if len(buffer) >= FRAME_SIZE:
                        analysis = analyze_frame(buffer, SAMPLE_RATE, FRAME_SIZE)
                        self.events.put(("analysis", analysis))
        except AudioBackendError as exc:
            self.events.put(("error", str(exc)))
        finally:
            self.running = False
            self.events.put(("idle", None))

    def _poll(self) -> None:
        latest = None
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "analysis":
                latest = payload
            elif kind == "error":
                self.status.set(payload.splitlines()[0])
                self._set_report(payload)
            elif kind == "idle" and str(self.status.get()).startswith("Listening"):
                self.status.set("Stopped.")
        if latest is not None:
            self.show_analysis(latest)
        if self.running or not self.events.empty():
            self.root.after(80, self._poll)

    def open_wav(self) -> None:
        path = filedialog.askopenfilename(
            title="Open a WAV recording",
            filetypes=[("WAV", "*.wav"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            signal, sample_rate = read_wav(path)
        except (FileNotFoundError, AudioBackendError) as exc:
            self.status.set(str(exc))
            return
        self.show_analysis(analyze_signal(signal, sample_rate))
        self.status.set(Path(path).name)

    def show_piano_demo(self) -> None:
        signal = synthesize(PIANO_MIDDLE_C, sample_rate=SAMPLE_RATE, seconds=1.0)
        self.show_analysis(analyze_signal(signal, SAMPLE_RATE))
        self.status.set("Piano demo: middle C, with a louder octave partial.")

    def show_analysis(self, analysis: Analysis) -> None:
        self._last_analysis = analysis
        self._set_report(format_report(analysis, self.language.get()))
        self._draw(analysis)

    def _relabel(self) -> None:
        if self._last_analysis is not None:
            self.show_analysis(self._last_analysis)

    def _set_report(self, text: str) -> None:
        self.report.configure(state="normal")
        self.report.delete("1.0", "end")
        self.report.insert("1.0", text)
        self.report.configure(state="disabled")

    def _draw(self, analysis: Analysis) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 880)
        height = max(canvas.winfo_height(), 260)
        left, right, top, bottom = 48, width - 16, 16, height - 28
        plot_w = right - left
        plot_h = bottom - top
        fmax = 2000.0
        mask = (analysis.frequencies >= 0) & (analysis.frequencies <= fmax)
        freqs = analysis.frequencies[mask]
        magnitude = analysis.magnitude[mask]
        if len(freqs) < 2 or float(np.max(magnitude)) <= 0.0:
            canvas.create_text(width // 2, height // 2, text="No spectrum", fill=MUTED)
            return
        decibels = 20.0 * np.log10(magnitude / (float(np.max(magnitude)) + 1e-12) + 1e-12)
        decibels = np.clip(decibels, -60.0, 0.0)
        # Keep one point per pixel so the polyline stays readable.
        columns = max(int(plot_w), 2)
        edges = np.linspace(0, len(freqs), columns + 1)
        points: list[float] = []
        last = len(decibels) - 1
        for column in range(columns):
            start = min(int(edges[column]), last)
            end = min(len(decibels), max(int(edges[column + 1]), start + 1))
            level = float(np.max(decibels[start:end]))
            y = top + (0.0 - level) / 60.0 * plot_h
            points.extend((left + column, y))
        canvas.create_rectangle(left, top, right, bottom, outline=GRID)
        for db in (-12, -24, -36, -48):
            y = top + (0.0 - db) / 60.0 * plot_h
            canvas.create_line(left, y, right, y, fill=GRID)
            canvas.create_text(left - 6, y, text=str(db), fill=MUTED, anchor="e", font=("DejaVu Sans", 8))
        for tick in (500, 1000, 1500, 2000):
            x = left + tick / fmax * plot_w
            canvas.create_line(x, top, x, bottom, fill=GRID)
            canvas.create_text(x, bottom + 12, text=str(tick), fill=MUTED, font=("DejaVu Sans", 8))
        canvas.create_line(*points, fill="#7eb6ff", width=1.5)
        for fundamental in analysis.fundamentals:
            for partial in fundamental.partials:
                if partial.frequency > fmax:
                    continue
                x = left + partial.frequency / fmax * plot_w
                color = ACCENT if partial.multiple == 1 else HARMONIC
                canvas.create_line(x, top, x, bottom, fill=color, dash=(3, 3))
                label = partial.pitch.pitch_class_en if partial.pitch else ""
                canvas.create_text(
                    x, top + 10, text=f"{partial.multiple}× {label}", fill=color,
                    font=("DejaVu Sans", 8),
                )


def main() -> int:
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
