from quran_asr.inference_live import compute_text_metrics, format_correction


def test_compute_text_metrics_exact_match():
    metrics = compute_text_metrics("أَلَمْ نَشْرَحْ", "أَلَمْ نَشْرَحْ")
    assert metrics == {
        "wer": 0.0,
        "cer": 0.0,
        "wer_plain": 0.0,
        "cer_plain": 0.0,
    }


def test_compute_text_metrics_plain_ignores_harakat():
    metrics = compute_text_metrics("أَلَمْ", "ألم")
    assert metrics["wer"] > 0.0
    assert metrics["cer"] > 0.0
    assert metrics["wer_plain"] == 0.0
    assert metrics["cer_plain"] == 0.0


def test_format_correction_marks_missing_and_extra_words():
    diff = format_correction("أَلَمْ نَشْرَحْ", "أَلَمْ")
    assert "- نَشْرَحْ" in diff
