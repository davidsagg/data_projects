import pytest
from src.chord_engine.transposer import transpose_chord, transpose_bkcp, get_key_name
from src.chord_engine.parser import classify_line, merge_chord_lyric, extract_metadata

# ── Transposer — 14 testes ──────────────────────────────────────
@pytest.mark.parametrize("chord,semi,expected", [
    ("Am",     3,  "Cm"),    # subir 3 semitons: A(9)+3=0→C
    ("G7",    -2,  "F7"),    # descer 2 semitons
    ("G/B",    2,  "A/C#"),  # acorde com baixo
    ("Bbmaj7",-1, "Amaj7"), # flat → sharp
    ("C",     12,  "C"),    # oitava completa
    ("F#m",   -3,  "D#m"),  # sharp descendo: F#(6)-3=3→D#
    ("Cdim",   6, "F#dim"), # diminuto
    ("Dsus4",  2, "Esus4"), # sus4
    ("E",      1,  "F"),    # mi → fá
    ("B",      1,  "C"),    # si → dó
    ("Am7",    0, "Am7"),   # zero semitones
])
def test_transpose_chord(chord, semi, expected):
    assert transpose_chord(chord, semi) == expected


def test_transpose_bkcp_preserves_lyrics():
    bkcp = "{title: Test}\n[Verso]\n[Am]Letra aqui\nSó letra\n"
    result = transpose_bkcp(bkcp, 3)
    assert "[Cm]" in result        # acorde transposto: Am+3=Cm
    assert "Letra aqui" in result  # letra intacta
    assert "[Verso]" in result     # seção intacta
    assert "{title: Test}" in result  # meta intacto


def test_transpose_bkcp_zero_unchanged():
    bkcp = "[Am]Letra"
    assert transpose_bkcp(bkcp, 0) == bkcp


def test_get_key_name():
    assert get_key_name("Am", 3) == "Cm"
    assert get_key_name("F",  2) == "G"


# ── Parser — 8 testes ───────────────────────────────────────────
@pytest.mark.parametrize("line,expected", [
    ("Am  F  C G",          "chord"),
    ("Preciso me encontrar", "lyric"),
    ("",                    "empty"),
    ("Verso 1",             "section"),
    ("Refrão",              "section"),
    ("Intro",               "section"),
    ("Bridge",              "section"),
])
def test_classify_line(line, expected):
    assert classify_line(line) == expected


def test_merge_chord_lyric():
    result = merge_chord_lyric("Am        F", "Preciso me encontrar")
    assert "[Am]" in result
    assert "[F]" in result
    assert "Preciso" in result


def test_extract_metadata():
    lines = ["Garota de Ipanema", "Tom Jobim", "Tom: Fá", ""]
    meta = extract_metadata(lines)
    assert meta["title"] == "Garota de Ipanema"
    assert meta["artist"] == "Tom Jobim"
