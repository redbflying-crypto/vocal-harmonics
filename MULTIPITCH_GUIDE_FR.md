# Analyse harmonique multi-fondamentales

Un son tenu n'est pas une seule fréquence. C'est une fondamentale f0 (la hauteur qu'on nomme) plus des partiels entiers 2·f0, 3·f0, 4·f0, … qui font le timbre.

Plusieurs fondamentales peuvent sonner ensemble :

- un accord, chanté ou joué
- deux chanteurs
- le chant diphonique, où un partiel aigu est plus fort que f0

L'analyseur sépare ces fondamentales de leurs harmoniques. Le code ci-dessous est celui de `vocal_harmonics/analysis.py`. Les identifiants restent en anglais.

## Spectre

- Échantillonnage à 44,1 kHz.
- Fenêtre de 8192 échantillons (environ 186 ms) dès que l'enregistrement est assez long, 16384 pour un fichier ou une démo. Les extraits plus courts redescendent à 4096.
- Fenêtre de Hamming, puis FFT réelle avec zéro-padding.
- La fréquence du pic est affinée par interpolation parabolique sur le logarithme de l'amplitude : les cents sont plus fins qu'un seul bin de FFT.
- Les pics inférieurs à 5 % du partiel le plus fort sont écartés. Les partiels sont cherchés jusqu'à 5000 Hz.

## Quels pics sont des fondamentales ?

```text
1. Repérer les pics du spectre.
2. Les candidats f0 sont les pics entre 75 Hz et 1200 Hz,
   plus f/2, f/3, … f/6 si cela peut expliquer une fondamentale absente.
3. Pour chaque candidat, rassembler les pics proches de k·f0, k = 1…12.
4. Noter la série selon le nombre de partiels expliqués et leur force.
   Pénaliser un candidat sans énergie en f0, et un candidat dont
   tous les partiels sont pairs (erreur d'octave classique).
5. Parcourir les candidats du meilleur score au moins bon.
   Rejeter un pic lorsqu'un pic plus grave l'explique déjà :

       522 Hz / 2 ≈ 261 Hz, et 261 Hz est un pic
       → 522 Hz est un partiel, pas une seconde note.
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

La tolérance est de 3 % de la fréquence visée (environ un demi-ton), et ne dépasse pas un ton voisin. Une quinte (rapport 1,5) n'est pas un multiple entier : Do4 et Sol4 restent deux fondamentales.

## Noms des notes

Tempérament égal, La4 = 440 Hz.

```python
midi = round(69 + 12 * log2(f / 440))
cents = 1200 * log2(f / (440 * 2 ** ((midi - 69) / 12)))
```

Classes : C, C#, D, D#, E, F, F#, G, G#, A, A#, B.
Les touches noires sont aussi écrites en bémol : `D#4 / Eb4`.
Le nom français est affiché à côté : Do, Ré, Mi, Fa, Sol, La, Si.

| Anglais | Français | Octave 4 |
|---|---|---|
| C4 | Do4 | 261,63 Hz |
| D4 | Ré4 | 293,66 Hz |
| E4 | Mi4 | 329,63 Hz |
| F4 | Fa4 | 349,23 Hz |
| G4 | Sol4 | 392,00 Hz |
| A4 | La4 | 440,00 Hz |
| B4 | Si4 | 493,88 Hz |

## Exemples

Note seule, ou note de piano dont l'octave est plus forte :

```text
FONDAMENTALE #1 : 263,8 Hz  C4 (Do4)  +14 cents
  1×  263,8 Hz   Do4
  2×  522,2 Hz   Do5    ← plus fort, et pourtant pas une fondamentale
  3×  786,0 Hz   Sol5
  4× 1055,1 Hz   Do6
```

Accord de do majeur :

```text
FONDAMENTALE #1 : 261,63 Hz  Do4
FONDAMENTALE #2 : 329,63 Hz  Mi4
FONDAMENTALE #3 : 392,00 Hz  Sol4
```

Chant diphonique, 4e partiel très fort :

```text
FONDAMENTALE #1 : 150 Hz  Ré3
  4×  600 Hz  Ré5   ← partiel le plus fort, même fondamentale
```

Ces trois cas, sans microphone :

```bash
python vocal_analyzer_corrected.py --demo --lang fr
```

## Limites

- La fenêtre doit être assez longue pour séparer les partiels. Deux demi-tons très graves sur une fenêtre de 4096 échantillons peuvent fusionner.
- Deux sons purs exactement à l'octave se rabattent sur le plus grave. Une tierce ou une quinte, non.
- Une fondamentale absente n'est déduite que si au moins trois partiels concordent. Si le spectre ne contient que des partiels pairs, la hauteur annoncée peut être l'octave.
- L'inharmonicité du piano (les partiels un peu trop aigus) est absorbée par la tolérance de 3 % sur les premiers rangs. Un partiel très aigu et très étiré peut sortir de la série.

## Dépannage

| Ce que vous voyez | Quoi vérifier |
|---|---|
| Aucune fondamentale | Niveau trop faible, ou f0 hors de 75–1200 Hz. Essayer `--min-f0 40` pour une note grave de piano. |
| L'octave annoncée comme la note | Ne doit plus arriver quand le pic grave existe. Lancer `--self-test`. |
| Fondamentales en trop | Pics de bruit au-dessus de 10 % du partiel le plus fort. `--verbose` liste les candidats rejetés. |
| `-9996` de PyAudio | Pas de périphérique par défaut. `python audio_device_diagnostic.py` puis `--device N`. |
| Nom de note décalé | Corrigé en v2.1. Le nom vient du numéro MIDI, pas du décalage brut depuis La4. Voir BUG_ANALYSIS.md. |
