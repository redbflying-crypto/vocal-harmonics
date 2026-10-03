"""Microphone capture and WAV loading.

Live input uses PyAudio and is optional. WAV files and the built-in demos
use only NumPy and the standard library.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vocal_harmonics.constants import SAMPLE_RATE

INSTALL_HINT = (
    "PyAudio is not installed, so the microphone is unavailable.\n"
    "  Linux:   sudo apt install portaudio19-dev && pip install pyaudio\n"
    "  Windows: pip install pyaudio\n"
    "A WAV file still works:  python vocal_analyzer_corrected.py --wav note.wav\n"
    "The piano regression too: python vocal_analyzer_corrected.py --demo"
)


class AudioBackendError(RuntimeError):
    """The microphone backend is missing or the device could not be opened."""


@dataclass(frozen=True)
class InputDevice:
    index: int
    name: str
    channels: int
    default_sample_rate: float
    is_default: bool

    def label(self) -> str:
        mark = " (default)" if self.is_default else ""
        return f"[{self.index}] {self.name}  {self.channels} ch @ {self.default_sample_rate:.0f} Hz{mark}"


def _pyaudio():
    try:
        import pyaudio
    except ImportError as exc:
        raise AudioBackendError(INSTALL_HINT) from exc
    return pyaudio


def list_input_devices() -> list[InputDevice]:
    """Return input-capable PortAudio devices. Raises AudioBackendError if PyAudio is missing."""
    pyaudio = _pyaudio()
    audio = pyaudio.PyAudio()
    try:
        default_index = None
        try:
            default_index = int(audio.get_default_input_device_info()["index"])
        except (OSError, IOError):
            default_index = None
        devices: list[InputDevice] = []
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            channels = int(info.get("maxInputChannels", 0))
            if channels < 1:
                continue
            devices.append(
                InputDevice(
                    index=index,
                    name=str(info.get("name", "unknown")),
                    channels=channels,
                    default_sample_rate=float(info.get("defaultSampleRate", SAMPLE_RATE)),
                    is_default=index == default_index,
                )
            )
        return devices
    finally:
        audio.terminate()


def device_error_message(exc: BaseException, device_index: int | None) -> str:
    chosen = "the default input device" if device_index is None else f"device {device_index}"
    return (
        f"Could not open {chosen}: {exc}\n"
        "PortAudio error -9996 (invalid device / no default output device) means "
        "Windows has no usable default endpoint, even for a capture-only stream.\n"
        "  1. python audio_device_diagnostic.py\n"
        "  2. python vocal_analyzer_corrected.py --device N\n"
        "  3. Windows: Settings → Privacy → Microphone → allow desktop apps.\n"
        "     Close any other program that is holding the microphone."
    )


def read_wav(path: str) -> tuple[np.ndarray, int]:
    """Load a PCM WAV file as a mono float array in [-1, 1]."""
    import wave

    try:
        handle = wave.open(path, "rb")
    except FileNotFoundError:
        raise
    except (wave.Error, OSError) as exc:
        raise AudioBackendError(f"Could not read {path}: {exc}") from exc
    with handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frame_count = handle.getnframes()
        payload = handle.readframes(frame_count)
    samples = _decode_pcm(payload, sample_width)
    if channels > 1:
        usable = len(samples) - (len(samples) % channels)
        samples = samples[:usable].reshape(-1, channels).mean(axis=1)
    return samples, sample_rate


def _decode_pcm(payload: bytes, sample_width: int) -> np.ndarray:
    if sample_width == 1:
        return (np.frombuffer(payload, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    if sample_width == 2:
        return np.frombuffer(payload, dtype="<i2").astype(np.float64) / 32768.0
    if sample_width == 3:
        raw = np.frombuffer(payload, dtype=np.uint8)
        if len(raw) % 3 != 0:
            raise AudioBackendError("Truncated 24-bit WAV file.")
        triples = raw.reshape(-1, 3).astype(np.int32)
        values = triples[:, 0] | (triples[:, 1] << 8) | (triples[:, 2] << 16)
        values = np.where(values >= 0x800000, values - 0x1000000, values)
        return values.astype(np.float64) / 8388608.0
    if sample_width == 4:
        return np.frombuffer(payload, dtype="<i4").astype(np.float64) / 2147483648.0
    raise AudioBackendError(
        f"Unsupported WAV sample width ({sample_width} bytes). Export 16-bit PCM."
    )


class Microphone:
    """Input-only PortAudio stream. Use as a context manager."""

    def __init__(self, device_index: int | None, sample_rate: int, frame_size: int):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self._audio = None
        self._stream = None
        self._pyaudio_module = None

    def __enter__(self) -> "Microphone":
        pyaudio = _pyaudio()
        self._pyaudio_module = pyaudio
        self._audio = pyaudio.PyAudio()
        try:
            self._stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.frame_size,
            )
        except (OSError, IOError) as exc:
            self._audio.terminate()
            self._audio = None
            raise AudioBackendError(device_error_message(exc, self.device_index)) from exc
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except (OSError, IOError):
                pass
            self._stream = None
        if self._audio is not None:
            self._audio.terminate()
            self._audio = None

    def read(self, frame_count: int) -> np.ndarray:
        if self._stream is None:
            raise AudioBackendError("The microphone is not open.")
        payload = self._stream.read(frame_count, exception_on_overflow=False)
        return np.frombuffer(payload, dtype="<i2").astype(np.float64) / 32768.0
