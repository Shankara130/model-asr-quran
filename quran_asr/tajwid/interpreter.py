from __future__ import annotations

from typing import Any


ARABIC_LETTERS = set(
    "ابتثجحخدذرزسشصضطظعغفقكلمنهويءں"
)

HARAKAT = {
    "َ": "fathah",
    "ِ": "kasrah",
    "ُ": "dhammah",
}

HARAKAT_CHARACTERS = set(HARAKAT)

LONG_VOWELS = {"ا", "ي", "و", "ۦ", "ۥ"}
GHUNNAH_LETTERS = {"ن", "م", "ں"}


def remove_harakat(text: str) -> str:
    return "".join(
        character
        for character in text
        if character not in HARAKAT_CHARACTERS
    )


def contains_only_long_vowels(text: str) -> bool:
    cleaned = remove_harakat(text)

    return (
        bool(cleaned)
        and set(cleaned).issubset(LONG_VOWELS)
    )


def contains_only_ghunnah(text: str) -> bool:
    cleaned = remove_harakat(text)

    return (
        bool(cleaned)
        and set(cleaned).issubset(GHUNNAH_LETTERS)
    )


def interpret_difference(
    difference: dict[str, Any],
) -> dict[str, Any]:
    operation = str(difference.get("type") or "")
    target = str(difference.get("target") or "")
    detected = str(difference.get("detected") or "")

    if operation == "replace":
        if (
            len(target) == 1
            and len(detected) == 1
            and target in ARABIC_LETTERS
            and detected in ARABIC_LETTERS
        ):
            return {
                "category": "makhraj",
                "status": "warning",
                "target": target,
                "detected": detected,
                "message": (
                    f"Perhatikan makhraj huruf {target}. "
                    f"Bunyi terdeteksi seperti {detected}."
                ),
            }

        if (
            len(target) == 1
            and len(detected) == 1
            and target in HARAKAT
            and detected in HARAKAT
        ):
            return {
                "category": "harakat",
                "status": "warning",
                "target": target,
                "detected": detected,
                "message": (
                    f"Harakat {HARAKAT[target]} "
                    f"terdeteksi seperti "
                    f"{HARAKAT[detected]}."
                ),
            }

        if (
            contains_only_long_vowels(target)
            or contains_only_long_vowels(detected)
        ):
            return {
                "category": "mad",
                "status": "warning",
                "target": target,
                "detected": detected,
                "message": (
                    "Panjang bacaan mad pada bagian ini "
                    "perlu diperiksa."
                ),
            }

        if (
            contains_only_ghunnah(target)
            or contains_only_ghunnah(detected)
        ):
            return {
                "category": "ghunnah",
                "status": "warning",
                "target": target,
                "detected": detected,
                "message": (
                    "Dengung atau tahanan ghunnah pada "
                    "bagian ini perlu diperiksa."
                ),
            }

        return {
            "category": "phoneme",
            "status": "warning",
            "target": target,
            "detected": detected,
            "message": (
                f"Bunyi {target} terdeteksi "
                f"seperti {detected}."
            ),
        }

    if operation == "delete":
        if contains_only_long_vowels(target):
            return {
                "category": "mad",
                "status": "too_short",
                "target": target,
                "detected": "",
                "message": (
                    "Bacaan mad terdeteksi terlalu pendek."
                ),
            }

        if contains_only_ghunnah(target):
            return {
                "category": "ghunnah",
                "status": "too_short",
                "target": target,
                "detected": "",
                "message": (
                    "Dengung atau tahanan ghunnah "
                    "terdeteksi terlalu pendek."
                ),
            }

        return {
            "category": "missing",
            "status": "warning",
            "target": target,
            "detected": "",
            "message": (
                f"Bunyi {target} tidak terdeteksi."
            ),
        }

    if operation == "insert":
        if contains_only_long_vowels(detected):
            return {
                "category": "mad",
                "status": "too_long",
                "target": "",
                "detected": detected,
                "message": (
                    "Bacaan mad terdeteksi terlalu panjang."
                ),
            }

        if contains_only_ghunnah(detected):
            return {
                "category": "ghunnah",
                "status": "too_long",
                "target": "",
                "detected": detected,
                "message": (
                    "Dengung atau tahanan ghunnah "
                    "terdeteksi terlalu panjang."
                ),
            }

        return {
            "category": "extra",
            "status": "warning",
            "target": "",
            "detected": detected,
            "message": (
                f"Terdapat bunyi tambahan {detected}."
            ),
        }

    return {
        "category": "unknown",
        "status": "warning",
        "target": target,
        "detected": detected,
        "message": "Terdapat perbedaan bunyi.",
    }


def interpret_differences(
    differences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        interpret_difference(difference)
        for difference in differences
    ]