# Analyseur d'harmoniques vocales

Programme Python qui décompose un son tenu (voix chantée, piano, accord) en fondamentales et en harmoniques, par transformée de Fourier rapide (FFT).

La version ici est la **v2.1 corrigée**. Un partiel d'octave plus fort que la fondamentale — cas typique du piano — n'est plus annoncé comme la note. Le détail est dans [BUG_ANALYSIS.md](BUG_ANALYSIS.md). Le fonctionnement de la détection multi-fondamentales est dans [MULTIPITCH_GUIDE_FR.md](MULTIPITCH_GUIDE_FR.md).

## Lancer sans microphone

Le cas du piano droit (Do central, octave plus forte) est intégré :

```bash
cd vocal-harmonics
pip install -r requirements.txt
python vocal_analyzer_corrected.py --demo
python vocal_analyzer_corrected.py --demo --lang fr
python vocal_analyzer_corrected.py --self-test
```

PyAudio n'est pas nécessaire pour `--demo`, `--self-test`, ni pour un fichier WAV.

## Fichier WAV

PCM 8, 16, 24 ou 32 bits, mono ou stéréo. Le stéréo est ramené en mono.

```bash
python vocal_analyzer_corrected.py --wav note.wav
python vocal_analyzer_corrected.py --wav note.wav --lang fr --verbose
```

## Microphone

```bash
python audio_device_diagnostic.py
python vocal_analyzer_corrected.py --list-devices
python vocal_analyzer_corrected.py --device 1 -d 20
python vocal_harmonics_analyzer.py
```

L'interface graphique laisse choisir le périphérique, ouvrir un WAV, et lancer la démo piano (spectre + série harmonique).

Sous Windows, si PortAudio renvoie `OSError: [Errno -9996] Invalid input device (no default output device)` :

1. Paramètres → Confidentialité et sécurité → Microphone.
2. Activer l'accès au microphone pour les applications de bureau.
3. Fermer tout logiciel qui garde déjà le micro.
4. Choisir un index affiché par `audio_device_diagnostic.py`.

Le flux ouvert est **en entrée seule** (`output=False`), ce qui évite d'exiger une sortie audio par défaut.

## Ce que le programme affiche

Pour le Do central du cas piano (fondamentale réelle à 263,78 Hz, octave à 522,18 Hz plus forte) :

```text
FUNDAMENTAL #1
  Note             C4 (Do4)
  Frequency        263.77 Hz
  Deviation        +14 cents
  Peak level       54.2% of the loudest partial
  Partials         4 detected

  Loudest partial is 2× at 522.18 Hz (C5 (Do5)), stronger than the fundamental.
```

Les 12 classes de hauteur du tempérament égal sont reconnues, avec le bémol des touches noires : `D#4 / Eb4` (`Ré#4 / Mib4`). Le diapason est La4 = 440 Hz.

```text
n     = 12 · log2(f / 440)
cents = 1200 · log2(f / f_attendue)
```

## Périmètre

- Sons tenus. Une mélodie qui bouge vite est suivie image par image en direct (fenêtre de 8192 échantillons, environ 186 ms), puis résumée sur l'ensemble de la prise.
- Fondamentales cherchées entre 75 Hz et 1200 Hz. Partiels suivis jusqu'à 5000 Hz.
- Un unisson à l'octave (deux chanteurs à exactement une octave, sans harmoniques propres) est ambigu : le pic aigu est traité comme un harmonique du grave. Une quinte ou une tierce reste une fondamentale distincte.
- Si la fondamentale est absente du spectre et que seuls des harmoniques pairs sont là, la note rapportée peut être l'octave. Le cas du piano, où le grave est présent mais plus faible, est couvert.

## Fichiers

| Fichier | Rôle |
|---|---|
| `vocal_analyzer_corrected.py` | Ligne de commande |
| `vocal_harmonics_analyzer.py` | Fenêtre (spectre + texte) |
| `audio_device_diagnostic.py` | Liste des micros |
| `vocal_harmonics/` | FFT, notes, lecture audio, rapport |
| `tests/` | Régression, dont le Do de piano |
