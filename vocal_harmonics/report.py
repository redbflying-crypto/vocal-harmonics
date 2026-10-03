"""Text reports for a harmonic analysis."""

from __future__ import annotations

from vocal_harmonics.analysis import Analysis, Fundamental
from vocal_harmonics.notes import format_cents

_LABELS = {
    "en": {
        "none": "No fundamental detected.",
        "fundamental": "FUNDAMENTAL",
        "note": "Note",
        "frequency": "Frequency",
        "deviation": "Deviation",
        "peak_level": "Peak level",
        "of_loudest": "of the loudest partial",
        "partials": "Partials",
        "detected": "detected",
        "series": "Series",
        "inferred": "inferred — no spectral peak at the fundamental",
        "harmonic_series": "Harmonic series",
        "loudest": "loudest",
        "loudest_line": (
            "Loudest partial is {multiple}× at {freq:.2f} Hz ({note}), "
            "stronger than the fundamental."
        ),
        "rejected": "Not a separate fundamental",
    },
    "fr": {
        "none": "Aucune fondamentale détectée.",
        "fundamental": "FONDAMENTALE",
        "note": "Note",
        "frequency": "Fréquence",
        "deviation": "Déviation",
        "peak_level": "Niveau du pic",
        "of_loudest": "du partiel le plus fort",
        "partials": "Partiels",
        "detected": "détectés",
        "series": "Série",
        "inferred": "déduite — pas de pic spectral à la fondamentale",
        "harmonic_series": "Série harmonique",
        "loudest": "le plus fort",
        "loudest_line": (
            "Le partiel le plus fort est {multiple}× à {freq:.2f} Hz ({note}), "
            "plus fort que la fondamentale."
        ),
        "rejected": "Pas une fondamentale distincte",
    },
}


def format_report(analysis: Analysis, language: str = "en", verbose: bool = False) -> str:
    labels = _LABELS["fr" if language == "fr" else "en"]
    if not analysis.fundamentals:
        return labels["none"]
    loudest_magnitude = analysis.loudest_peak.magnitude if analysis.loudest_peak else 1.0
    blocks = [
        _format_fundamental(item, index, labels, loudest_magnitude, analysis)
        for index, item in enumerate(analysis.fundamentals, start=1)
    ]
    if verbose and analysis.rejected:
        lines = ["", labels["rejected"] + ":"]
        for item in analysis.rejected:
            note = item.pitch.label() if item.pitch else "?"
            level = 100.0 * item.magnitude / loudest_magnitude if loudest_magnitude else 0.0
            lines.append(f"  {item.frequency:8.2f} Hz  {note:<22} {level:5.1f}%  {item.reason}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def format_compact(analysis: Analysis) -> str:
    """One line, for the live readout."""
    if not analysis.fundamentals:
        return "—  (no fundamental)"
    parts = []
    for item in analysis.fundamentals:
        note = item.pitch.label() if item.pitch else "?"
        cents = format_cents(item.pitch.cents) if item.pitch else "?"
        parts.append(f"{note}  {item.frequency:.1f} Hz  {cents}  ({item.partial_count} partials)")
    return "   |   ".join(parts)


def _format_fundamental(
    item: Fundamental,
    index: int,
    labels: dict[str, str],
    loudest_magnitude: float,
    analysis: Analysis,
) -> str:
    note = item.pitch.label() if item.pitch else "?"
    cents = format_cents(item.pitch.cents) if item.pitch else "?"
    peak_level = 100.0 * item.magnitude / loudest_magnitude if loudest_magnitude else 0.0
    rows = [
        f"{labels['fundamental']} #{index}",
        f"  {labels['note']:<16} {note}",
        f"  {labels['frequency']:<16} {item.frequency:.2f} Hz",
        f"  {labels['deviation']:<16} {cents}",
    ]
    if item.inferred:
        rows.append(f"  {labels['peak_level']:<16} {labels['inferred']}")
    else:
        rows.append(
            f"  {labels['peak_level']:<16} {peak_level:.1f}% {labels['of_loudest']}"
        )
    rows.append(f"  {labels['partials']:<16} {item.partial_count} {labels['detected']}")
    rows.append(f"  {labels['series']:<16} {100.0 * item.score:.0f}%")
    warning = _loudest_partial_warning(item, analysis, labels)
    if warning:
        rows.append("")
        rows.append(f"  {warning}")
    rows.append("")
    rows.append(f"  {labels['harmonic_series']}:")
    for partial in item.partials:
        partial_note = partial.pitch.label() if partial.pitch else "?"
        partial_cents = format_cents(partial.pitch.cents) if partial.pitch else "?"
        level = 100.0 * partial.magnitude / loudest_magnitude if loudest_magnitude else 0.0
        marker = f"  {labels['loudest']}" if abs(partial.magnitude - loudest_magnitude) < 1e-9 else ""
        rows.append(
            f"    {partial.multiple:>2}×  {partial.frequency:8.2f} Hz"
            f"  {partial_note:<22} {partial_cents:>10}  {level:5.1f}%{marker}"
        )
    return "\n".join(rows)


def _loudest_partial_warning(
    item: Fundamental,
    analysis: Analysis,
    labels: dict[str, str],
) -> str | None:
    loudest = analysis.loudest_peak
    if loudest is None or item.magnitude <= 0.0:
        return None
    if loudest.magnitude <= item.magnitude * 1.02:
        return None
    for partial in item.partials:
        if abs(partial.frequency - loudest.frequency) / loudest.frequency < 0.02:
            if partial.multiple == 1:
                return None
            note = partial.pitch.label() if partial.pitch else "?"
            return labels["loudest_line"].format(
                multiple=partial.multiple,
                freq=partial.frequency,
                note=note,
            )
    return None
