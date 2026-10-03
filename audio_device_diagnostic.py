#!/usr/bin/env python3
"""List PortAudio input devices and the default capture endpoint.

    python audio_device_diagnostic.py

Windows error -9996 ("no default output device") usually means PortAudio has
no usable default endpoint. Pick one of the indexes printed here and pass it
to vocal_analyzer_corrected.py --device N, or select it in the GUI.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vocal_harmonics.audio import AudioBackendError, list_input_devices


def main() -> int:
    print("Audio device diagnostic")
    print("=" * 40)
    try:
        devices = list_input_devices()
    except AudioBackendError as exc:
        print(exc, file=sys.stderr)
        return 1
    if not devices:
        print("No input device found.")
        print()
        print("Windows 11:")
        print("  Settings → Privacy & security → Microphone")
        print("  Turn on 'Microphone access' and 'Let desktop apps access your microphone'.")
        print("Then close programs that may already be using the device and run this again.")
        return 1
    default = [device for device in devices if device.is_default]
    if default:
        print(f"Default input: {default[0].label()}")
    else:
        print("No default input device. Pass --device N explicitly.")
        print("This is the situation behind PortAudio error -9996.")
    print()
    print(f"{len(devices)} input device(s):")
    for device in devices:
        print(f"  {device.label()}")
    print()
    print("Live analysis:")
    chosen = default[0].index if default else devices[0].index
    print(f"  python vocal_analyzer_corrected.py --device {chosen} -d 10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
