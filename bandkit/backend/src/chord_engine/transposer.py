import re

CHROMATIC_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
CHROMATIC_FLAT  = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
ENHARMONIC_MAP  = {
    "Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#",
    "C#": "Db", "D#": "Eb", "F#": "Gb", "G#": "Ab", "A#": "Bb",
}

_CHORD_RE = re.compile(
    r"^([A-G][#b]?)"                          # root
    r"(m|maj|min|dim|aug|sus[24]?|add\d?|M)?" # quality
    r"(\d*)"                                   # extension
    r"((?:/[A-G][#b]?)?)$"                    # bass note
)


def normalize_root(root: str) -> str:
    return ENHARMONIC_MAP.get(root, root) if root in CHROMATIC_FLAT and root not in CHROMATIC_SHARP else root


def transpose_root(root: str, semitones: int, prefer_flat: bool = False) -> str:
    sharp_root = normalize_root(root)
    try:
        idx = CHROMATIC_SHARP.index(sharp_root)
    except ValueError:
        return root
    new_idx = (idx + semitones) % 12
    return CHROMATIC_FLAT[new_idx] if prefer_flat else CHROMATIC_SHARP[new_idx]


def transpose_chord(chord: str, semitones: int, prefer_flat: bool = False) -> str:
    m = _CHORD_RE.match(chord)
    if not m:
        return chord
    root, quality, ext, bass = m.groups()
    new_root = transpose_root(root, semitones, prefer_flat)
    new_bass = ""
    if bass:
        new_bass = "/" + transpose_root(bass[1:], semitones, prefer_flat)
    return new_root + (quality or "") + (ext or "") + new_bass


def transpose_bkcp(content: str, semitones: int, prefer_flat: bool = False) -> str:
    if semitones == 0:
        return content
    def _replace(m: re.Match) -> str:
        return "[" + transpose_chord(m.group(1), semitones, prefer_flat) + "]"
    return re.sub(r"\[([^\]]+)\]", _replace, content)


def get_key_name(original_key: str, semitones: int) -> str:
    m = re.match(r"^([A-G][#b]?)(.*)$", original_key)
    if not m:
        return original_key
    root, suffix = m.groups()
    prefer_flat = "b" in suffix or any(
        c in suffix for c in ("Db", "Eb", "Gb", "Ab", "Bb")
    )
    return transpose_root(root, semitones, prefer_flat) + suffix
