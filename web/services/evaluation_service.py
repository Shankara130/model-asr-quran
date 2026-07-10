from __future__ import annotations

from functools import lru_cache
from typing import Any

from quran_asr.tajwid.interpreter import interpret_differences


def normalize_phoneme(text: str) -> str:
    return "".join(str(text).split())


def levenshtein_alignment(
    reference: str,
    hypothesis: str,
) -> tuple[int, list[dict[str, Any]]]:
    rows = len(reference) + 1
    cols = len(hypothesis) + 1

    matrix = [[0] * cols for _ in range(rows)]

    for row in range(rows):
        matrix[row][0] = row

    for column in range(cols):
        matrix[0][column] = column

    for row in range(1, rows):
        for column in range(1, cols):
            replace_cost = (
                0
                if reference[row - 1] == hypothesis[column - 1]
                else 1
            )

            matrix[row][column] = min(
                matrix[row - 1][column] + 1,
                matrix[row][column - 1] + 1,
                matrix[row - 1][column - 1] + replace_cost,
            )

    operations: list[dict[str, Any]] = []

    row = len(reference)
    column = len(hypothesis)

    while row > 0 or column > 0:
        if (
            row > 0
            and column > 0
            and reference[row - 1] == hypothesis[column - 1]
            and matrix[row][column]
            == matrix[row - 1][column - 1]
        ):
            operations.append({
                "type": "equal",
                "target": reference[row - 1],
                "detected": hypothesis[column - 1],
                "target_index": row - 1,
                "prediction_index": column - 1,
            })

            row -= 1
            column -= 1

        elif (
            row > 0
            and column > 0
            and matrix[row][column]
            == matrix[row - 1][column - 1] + 1
        ):
            operations.append({
                "type": "replace",
                "target": reference[row - 1],
                "detected": hypothesis[column - 1],
                "target_index": row - 1,
                "prediction_index": column - 1,
            })

            row -= 1
            column -= 1

        elif (
            row > 0
            and matrix[row][column]
            == matrix[row - 1][column] + 1
        ):
            operations.append({
                "type": "delete",
                "target": reference[row - 1],
                "detected": "",
                "target_index": row - 1,
                "prediction_index": column,
            })

            row -= 1

        else:
            operations.append({
                "type": "insert",
                "target": "",
                "detected": hypothesis[column - 1],
                "target_index": row,
                "prediction_index": column - 1,
            })

            column -= 1

    operations.reverse()

    return matrix[-1][-1], operations


def compact_differences(
    operations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for operation in operations:
        if operation["type"] == "equal":
            current = None
            continue

        if (
            current is None
            or current["type"] != operation["type"]
        ):
            current = {
                "type": operation["type"],
                "target": operation["target"],
                "detected": operation["detected"],
                "target_index": operation["target_index"],
                "prediction_index": operation["prediction_index"],
            }

            differences.append(current)

        else:
            current["target"] += operation["target"]
            current["detected"] += operation["detected"]

    return differences


def edit_distance(reference: str, hypothesis: str) -> int:
    distance, _ = levenshtein_alignment(
        reference,
        hypothesis,
    )
    return distance


def split_prediction_by_words(
    target_words: list[str],
    prediction: str,
) -> list[str]:
    """
    Membagi prediksi tanpa spasi menjadi segmen yang paling cocok
    terhadap setiap kata fonem target.
    """

    word_count = len(target_words)
    prediction_length = len(prediction)

    @lru_cache(maxsize=None)
    def solve(
        word_index: int,
        prediction_index: int,
    ) -> tuple[int, tuple[str, ...]]:
        if word_index == word_count:
            remaining = prediction[prediction_index:]

            return (
                len(remaining),
                tuple(),
            )

        target_word = target_words[word_index]
        remaining_words = word_count - word_index - 1

        minimum_remaining = remaining_words

        maximum_end = (
            prediction_length - minimum_remaining
        )

        expected_length = len(target_word)

        minimum_length = max(
            0,
            expected_length - 4,
        )

        maximum_length = expected_length + 5

        best_cost: int | None = None
        best_segments: tuple[str, ...] = tuple()

        for segment_length in range(
            minimum_length,
            maximum_length + 1,
        ):
            end_index = (
                prediction_index + segment_length
            )

            if end_index > maximum_end:
                continue

            segment = prediction[
                prediction_index:end_index
            ]

            local_cost = edit_distance(
                target_word,
                segment,
            )

            next_cost, next_segments = solve(
                word_index + 1,
                end_index,
            )

            total_cost = local_cost + next_cost

            if (
                best_cost is None
                or total_cost < best_cost
            ):
                best_cost = total_cost
                best_segments = (
                    segment,
                    *next_segments,
                )

        if best_cost is None:
            segment = prediction[prediction_index:]

            return (
                edit_distance(
                    target_word,
                    segment,
                ),
                (segment,),
            )

        return best_cost, best_segments

    _, segments = solve(0, 0)

    result = list(segments)

    while len(result) < len(target_words):
        result.append("")

    return result


def build_word_results(
    target_phoneme: str,
    prediction: str,
) -> list[dict[str, Any]]:
    target_words = [
        normalize_phoneme(word)
        for word in target_phoneme.split()
        if normalize_phoneme(word)
    ]

    prediction_clean = normalize_phoneme(prediction)

    detected_words = split_prediction_by_words(
        target_words,
        prediction_clean,
    )

    word_results: list[dict[str, Any]] = []

    for index, target_word in enumerate(target_words):
        detected_word = (
            detected_words[index]
            if index < len(detected_words)
            else ""
        )

        edit_count, operations = levenshtein_alignment(
            target_word,
            detected_word,
        )

        cer = (
            edit_count / len(target_word)
            if target_word
            else 0.0
        )

        similarity = max(
            0.0,
            1.0 - cer,
        ) * 100

        differences = compact_differences(
            operations
        )

        word_results.append({
            "word_index": index,
            "target": target_word,
            "detected": detected_word,
            "edit_count": edit_count,
            "cer": round(cer, 6),
            "similarity": round(similarity, 2),
            "exact_match": (
                target_word == detected_word
            ),
            "differences": differences,
            "tajwid_feedback": interpret_differences(
                differences
            ),
        })

    return word_results


def evaluate_prediction(
    target_phoneme: str,
    prediction: str,
) -> dict[str, Any]:
    target_clean = normalize_phoneme(
        target_phoneme
    )

    prediction_clean = normalize_phoneme(
        prediction
    )

    edit_count, operations = levenshtein_alignment(
        target_clean,
        prediction_clean,
    )

    cer = (
        edit_count / len(target_clean)
        if target_clean
        else 0.0
    )

    similarity = max(
        0.0,
        1.0 - cer,
    ) * 100

    differences = compact_differences(
        operations
    )

    word_results = build_word_results(
        target_phoneme,
        prediction,
    )

    return {
        "target_clean": target_clean,
        "prediction_clean": prediction_clean,
        "edit_count": edit_count,
        "cer": round(cer, 6),
        "similarity": round(similarity, 2),
        "exact_match": (
            target_clean == prediction_clean
        ),
        "differences": differences,
        "tajwid_feedback": interpret_differences(
            differences
        ),
        "word_results": word_results,
    }