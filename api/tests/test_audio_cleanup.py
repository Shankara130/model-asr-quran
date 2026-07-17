from api.services.evaluation_pipeline import _delete_audio_file


def test_delete_audio_file_removes_only_files_inside_audio_root(tmp_path):
    audio_root = tmp_path / "audio"
    session_dir = audio_root / "session"
    session_dir.mkdir(parents=True)
    recording = session_dir / "recording.wav"
    recording.write_bytes(b"audio")
    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"keep")

    assert _delete_audio_file(recording, audio_root) is True
    assert recording.exists() is False
    assert session_dir.exists() is False
    assert _delete_audio_file(outside, audio_root) is False
    assert outside.exists() is True
