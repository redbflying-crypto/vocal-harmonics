# Bug : l'octave du piano prise pour la fondamentale

Test sur un piano droit accordé, Do central (C4 ≈ 261,63 Hz). L'ancienne détection annonçait deux fondamentales, la plus forte en premier :

```text
FUNDAMENTAL #1:
  Note:      D#4
  Frequency: 522.18 Hz      ← 2e harmonique
  Deviation: -3 cents
  Strength:  100%

FUNDAMENTAL #2:
  Note:      D#4
  Frequency: 263.78 Hz      ← vraie fondamentale
  Deviation: +14 cents
  Strength:  54.2%
```

La v2.1 rapporte une seule fondamentale :

```text
FUNDAMENTAL #1
  Note             C4 (Do4)
  Frequency        263.77 Hz
  Deviation        +14 cents
  Peak level       54.2% of the loudest partial

  Loudest partial is 2× at 522.18 Hz (C5), stronger than the fundamental.
    1×  263.77 Hz   C4
    2×  522.18 Hz   C5
    3×  785.96 Hz   G5
    4× 1055.13 Hz   C6
```

522,18 Hz est à environ −3,5 cents de C5 (523,25 Hz), affiché −4 cents. 263,78 Hz est à environ +14 cents de C4.

## Deux erreurs distinctes

### 1. Le pic le plus fort n'est pas la cause

Série du Do joué :

| Ordre | Fréquence mesurée | Note juste | Rôle |
|---|---|---|---|
| 1× | 263,78 Hz | C4 | fondamentale |
| 2× | 522,18 Hz | C5 | octave |
| 3× | 785,96 Hz | G5 | quinte (une octave plus haut) |
| 4× | 1055,13 Hz | C6 | double octave |

Sur un piano, le partiel 2× est souvent **plus fort** que 1×. Trier les pics par amplitude, puis déclarer fondamentale le premier pic « qui a des multiples au-dessus de lui », désigne 522 Hz : 1055 Hz est proche de 2×522. Le pic à 264 Hz n'est pas un multiple de 522, donc il était gardé comme seconde fondamentale.

La direction à tester est l'autre : **est-ce qu'un pic plus grave explique celui-ci ?**

```python
def find_subharmonic(freq, peaks, tolerance=0.03, min_freq=75.0):
    """Return the lower peak that explains freq, or None.

    522 / 2 = 261. A peak near 261 means 522 is a partial, not a fundamental.
    """
    for divisor in (2, 3, 4, 5, 6):
        sub = freq / divisor
        if sub < min_freq:
            continue
        for peak in peaks:
            if abs(peak - sub) / sub < tolerance:
                return peak
    return None
```

522,18 / 2 = 261,09, à 1 % de 263,78. Le pic aigu est rejeté. 263,78 / 2 = 131,89 : aucun pic là, il reste candidat.

Le classement se fait ensuite par le nombre de partiels expliqués, pas par l'amplitude du seul pic. 264 Hz explique quatre pics ; 522 Hz n'en explique qu'une partie.

### 2. Le nom D#4

L'écart en cents était calculé contre la bonne note tempérée (−3 cents et +14 cents collent à C5 et C4). Le **nom** venait d'un autre calcul : le nombre de demi-tons depuis La4, utilisé comme index dans une liste qui commence à Do, avec une octave tronquée vers zéro.

```python
semitone = round(12 * log2(f / 440))   # 0 = A, pas C
octave = 4 + int(semitone / 12)        # int tronque vers 0 : int(-9/12) == 0
name = NOTES[semitone % 12]            # NOTES[0] == "C"  →  D# pour l'index 3
```

Pour 522,18 Hz, `semitone` vaut 3, donc `NOTES[3]` = D# et l'octave reste 4 : **D#4**.
Pour 263,78 Hz, `semitone` vaut −9. En Python `−9 % 12 == 3` (encore D#) et `int(−9/12) == 0`, donc l'octave reste 4 : **D#4** aussi. Deux octaves différentes, le même nom faux.

Le calcul retenu :

```python
midi = round(69 + 12 * log2(f / 440))  # MIDI 69 = A4, MIDI 60 = C4
name = NOTES[midi % 12]
octave = midi // 12 - 1
cents = 1200 * log2(f / (440 * 2 ** ((midi - 69) / 12)))
```

263,78 Hz → C4, +14 cents. 522,18 Hz → C5, −4 cents affichés.

## Ce que ça ne résout pas

Deux notes réellement à l'octave, sans harmonique propre de chaque côté (deux voix sur La3 et La4 purs), restent ambiguës : le La aigu est un multiple entier du La grave. Une tierce ou une quinte ne l'est pas. L'accord Do–Mi–Sol reste trois fondamentales.

## Vérifier

```bash
python vocal_analyzer_corrected.py --demo
python vocal_analyzer_corrected.py --self-test
```

Le test `test_piano_octave_is_not_the_fundamental` synthétise exactement 263,78 Hz, 522,18 Hz, 785,96 Hz et 1055,13 Hz avec les amplitudes 54 %, 100 %, 40 % et 25 %.
