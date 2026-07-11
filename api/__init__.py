"""Sobat Ngaji FastAPI backend.

Wraps the existing Quran ASR engine (``web/services``) behind the contract
defined in ``BackendRequirements.md``. The app boots without the ONNX model —
only the evaluation path loads it lazily.
"""

__version__ = "0.1.0"
