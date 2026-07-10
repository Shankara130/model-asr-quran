from __future__ import annotations

from typing import Any

import numpy as np
import sherpa_onnx

from web.config import MODEL_PATH, SAMPLE_RATE, TOKENS_PATH


def extract_text(result: Any) -> str:
    if isinstance(result, str):
        return result.strip()

    return str(result.text).strip()


class ASRService:
    def __init__(self) -> None:
        self.recognizer = (
            sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(
                tokens=str(TOKENS_PATH),
                model=str(MODEL_PATH),
                num_threads=2,
                provider="cpu",
                sample_rate=SAMPLE_RATE,
                feature_dim=80,
                decoding_method="greedy_search",
            )
        )

    def create_stream(self):
        return self.recognizer.create_stream()

    def accept_audio(
        self,
        stream,
        audio_data: bytes,
    ) -> str:
        samples = np.frombuffer(
            audio_data,
            dtype=np.float32,
        ).copy()

        if samples.size == 0:
            return ""

        stream.accept_waveform(
            SAMPLE_RATE,
            samples,
        )

        while self.recognizer.is_ready(stream):
            self.recognizer.decode_stream(stream)

        return extract_text(
            self.recognizer.get_result(stream)
        )

    def finish_stream(self, stream) -> str:
        stream.input_finished()

        while self.recognizer.is_ready(stream):
            self.recognizer.decode_stream(stream)

        return extract_text(
            self.recognizer.get_result(stream)
        )