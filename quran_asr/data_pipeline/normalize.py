"""Text normalization for diacritized Quranic Arabic.

This is the highest-risk correctness piece of the project: if normalization
silently collapses harakat or breaks the round-trip ``decode(tokenize(x)) ==
normalize(x)``, training is wasted.

Policy (default) — verified against the full 6236-verse quran.com Uthmani corpus
(70 distinct codepoints):

  KEEP  — base letters + the *pronounced* harakat family. These carry the sound
          and let the model/aligner detect harakat errors:
            fatha/damma/kasra/sukun/shadda (U+064E,F,50,52,51)
            tanween fathatan/dammatan/kasratan (U+064B,C,D)
            maddah-above (U+0653)   — the Quran.com text spells آ as ا + ٓ
            hamza-above (U+0654)
            superscript alef (U+0670) — long /aː/, e.g. ٱلرَّحْمَٰنِ
            alef wasla (U+0671)
          Plus the hamza-carrier alef variants أ إ ؤ ئ kept DISTINCT.

  STRIP — characters with no discrete acoustic realization, which would only
          pollute CTC + forced alignment:
            tatweel (U+0640)                      — typographic stretch
            waqf pause marks (ۖۗۘۙۚٛۜ, U+06D6–06DC)   — stop instructions, not sounds
            tajweed annotations (۟ۢۧ…, U+06DF,E0,E2,E3,E5–E8,EA–ED)
                                                  — idgham/small-letter hints (Phase 2)
            structural (۞ rub-el-hizb, ۩ sajda)   — layout, not pronunciation

Everything is config-driven so a Phase-2 finer model can opt into keeping
tajweed/waqf marks.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Character classes (verified against the real corpus inventory)
# ---------------------------------------------------------------------------

# Base letters (Lo) — 36 codepoints. Hamza-carrier variants kept distinct.
LETTERS: str = (
    "ءأؤإئا"  # ء أ ؤ إ ئ ا
    "بةتثجحخدذرز"
    "سشصضطظعغ"
    "فقكلمنهوىي"
    "ٱ"  # ٱ alef wasla
)

# Pronounced harakat / diacritics (Mn) — 11 codepoints. These are the tokens
# that make harakat-level error detection possible.
DIACRITICS: str = (
    "ًٌٍ"  # tanween: fathatan, dammatan, kasratan
    "َُِ"  # fatha, damma, kasra
    "ّْ"        # shadda, sukun
    "ٓٔ"        # maddah above, hamza above
    "ٰ"              # superscript alef
)

TATWEEL: str = "ـ"

# Waqf (pause) marks — recitation stop instructions, no sound.
WAQF: str = "ۖۗۘۙۚۛۜ"

# Tajweed annotation marks — idgham / small-letter hints (Phase-2 territory).
TAJWEED: str = "ۣ۟۠ۢۥۦ۪ۭۧۨ۫۬"

# Structural / layout symbols — not pronunciation.
STRUCTURAL: str = "۞۩"  # rub el hizb, place of sajdah

SPACE: str = " "


@dataclass(frozen=True)
class NormalizePolicy:
    """Controls which optional character classes are retained."""

    strip_tatweel: bool = True
    keep_waqf: bool = False
    keep_tajweed_marks: bool = False
    keep_structural: bool = False
    collapse_spaces: bool = True

    def keep_set(self) -> frozenset[str]:
        chars = LETTERS + DIACRITICS + SPACE
        if not self.strip_tatweel:
            chars += TATWEEL
        if self.keep_waqf:
            chars += WAQF
        if self.keep_tajweed_marks:
            chars += TAJWEED
        if self.keep_structural:
            chars += STRUCTURAL
        return frozenset(chars)


DEFAULT_POLICY = NormalizePolicy()


def normalize(text: str, policy: NormalizePolicy = DEFAULT_POLICY) -> str:
    """Apply the normalization policy: keep letters + pronounced harakat,
    drop everything else, collapse whitespace."""
    keep = policy.keep_set()
    out = [ch for ch in text if ch in keep]
    result = "".join(out)
    if policy.collapse_spaces:
        result = " ".join(result.split())
    return result


def strip_diacritics(text: str, policy: NormalizePolicy = DEFAULT_POLICY) -> str:
    """Return the consonantal skeleton (letters + space only).

    Used for the ``text_plain`` baseline WER/CER metric. Light normalization by
    design — only the pronounced harakat family is removed; a stronger alef/
    teh-marbuta normalization can be added later if the plain metric needs it.
    """
    diac = frozenset(DIACRITICS)
    # normalize first (so optional marks are gone), then drop harakat
    normed = normalize(text, policy)
    return " ".join("".join(ch for ch in w if ch not in diac) for w in normed.split())


def char_classes() -> dict[str, str]:
    """Expose the classes (useful for vocab building and debugging)."""
    return {
        "letters": LETTERS,
        "diacritics": DIACRITICS,
        "tatweel": TATWEEL,
        "waqf": WAQF,
        "tajweed": TAJWEED,
        "structural": STRUCTURAL,
    }
