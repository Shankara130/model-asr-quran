from hashlib import sha256

from api.services.asr_provider import _sha256


def test_model_fingerprint_hashes_file_contents(tmp_path):
    artifact = tmp_path / "model.onnx"
    artifact.write_bytes(b"onnx-model-bytes")

    assert _sha256(artifact) == sha256(b"onnx-model-bytes").hexdigest()
