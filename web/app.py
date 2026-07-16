from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from flask import (
    Flask,
    render_template,
    request,
    send_from_directory,
)
from flask_socketio import SocketIO, emit

from web.config import (
    FEEDBACK_PATH,
    QARI_AUDIO_DIR,
    RESULTS_PATH,
    validate_required_files,
)
from web.services.asr_service import ASRService
from web.services.evaluation_service import (
    evaluate_prediction,
)
from web.services.letter_test_service import (
    LETTER_TESTS,
    get_letter_test,
)
from web.services.quran_service import (
    QuranService,
    normalize_phoneme,
)
from web.services.storage_service import (
    JSONLStorage,
)

validate_required_files()

app = Flask(__name__)
app.config["SECRET_KEY"] = "quran-asr-dev"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
)

asr_service = ASRService()
quran_service = QuranService()
storage = JSONLStorage()

sessions: dict[str, dict[str, Any]] = {}
last_results: dict[str, dict[str, Any]] = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route(
    "/audio-reference/<int:surah>/<int:ayah>"
)
def audio_reference(
    surah: int,
    ayah: int,
):
    filename = f"{surah:03d}{ayah:03d}.mp3"
    audio_path = QARI_AUDIO_DIR / filename

    if not audio_path.exists():
        return {
            "error": (
                "Audio referensi tidak ditemukan."
            )
        }, 404

    return send_from_directory(
        QARI_AUDIO_DIR,
        filename,
        mimetype="audio/mpeg",
    )


@socketio.on("connect")
def handle_connect():
    print(
        f"Browser terhubung: {request.sid}"
    )


@socketio.on("disconnect")
def handle_disconnect():
    sessions.pop(request.sid, None)
    last_results.pop(request.sid, None)

    print(
        f"Browser terputus: {request.sid}"
    )


@socketio.on("get_random_verse")
def handle_get_random_verse():
    try:
        verse = quran_service.get_random_verse()
        emit("random_verse", verse)

    except RuntimeError as exc:
        emit(
            "session_error",
            {"message": str(exc)},
        )


@socketio.on("get_letter_test")
def handle_get_letter_test(
    data: dict[str, Any] | None,
):
    try:
        index = int(
            (data or {}).get("index", 0)
        )

        emit(
            "letter_test",
            get_letter_test(index),
        )

    except (
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        emit(
            "letter_test_error",
            {"message": str(exc)},
        )


@socketio.on("start_recording")
def handle_start_recording(
    data: dict[str, Any],
):
    tester = str(
        data.get("tester") or "Anonim"
    ).strip()

    test_mode = str(
        data.get("test_mode")
        or "ayat_pilihan"
    ).strip()

    valid_modes = {
        "random",
        "ayat_pilihan",
        "uji_huruf",
    }

    if test_mode not in valid_modes:
        emit(
            "session_error",
            {
                "message": (
                    "Metode pengujian "
                    "tidak valid."
                )
            },
        )
        return

    if test_mode == "uji_huruf":
        try:
            letter_index = int(
                data.get("letter_index", 0)
            )

            letter_test = get_letter_test(
                letter_index
            )

        except (
            TypeError,
            ValueError,
            RuntimeError,
        ) as exc:
            emit(
                "session_error",
                {"message": str(exc)},
            )
            return

        sessions[request.sid] = {
            "stream": asr_service.create_stream(),
            "tester": tester,
            "test_mode": test_mode,
            "letter_index": (
                letter_test["index"]
            ),
            "target_letter": (
                letter_test["letter"]
            ),
            "letter_name": (
                letter_test["letter_name"]
            ),
            "harakat": (
                letter_test["harakat"]
            ),
            "latin_hint": (
                letter_test["latin_hint"]
            ),
            "warning": (
                letter_test["warning"]
            ),
            "surah": None,
            "ayah": None,
            "target_text": (
                letter_test["display"]
            ),
            "target_phoneme": (
                letter_test["target_phoneme"]
            ),
            "target_clean": normalize_phoneme(
                letter_test["target_phoneme"]
            ),
            "last_phoneme": "",
        }

        emit(
            "session_started",
            {
                "test_mode": test_mode,
                "letter_index": (
                    letter_test["index"]
                ),
                "target_letter": (
                    letter_test["letter"]
                ),
                "letter_name": (
                    letter_test["letter_name"]
                ),
                "harakat": (
                    letter_test["harakat"]
                ),
                "latin_hint": (
                    letter_test["latin_hint"]
                ),
                "warning": (
                    letter_test["warning"]
                ),
                "target_text": (
                    letter_test["display"]
                ),
                "target_phoneme": (
                    letter_test[
                        "target_phoneme"
                    ]
                ),
            },
        )

        return

    try:
        surah = int(data.get("surah"))
        ayah = int(data.get("ayah"))

        verse = quran_service.get_verse(
            surah,
            ayah,
        )

    except (
        TypeError,
        ValueError,
        KeyError,
    ) as exc:
        emit(
            "session_error",
            {"message": str(exc)},
        )
        return

    sessions[request.sid] = {
        "stream": asr_service.create_stream(),
        "tester": tester,
        "test_mode": test_mode,
        "letter_index": None,
        "target_letter": None,
        "letter_name": None,
        "harakat": None,
        "latin_hint": None,
        "warning": None,
        "surah": verse["surah"],
        "ayah": verse["ayah"],
        "target_text": verse["target_text"],
        "target_phoneme": (
            verse["target_phoneme"]
        ),
        "target_clean": normalize_phoneme(
            verse["target_phoneme"]
        ),
        "last_phoneme": "",
    }

    emit(
        "session_started",
        {
            "test_mode": test_mode,
            **verse,
        },
    )


@socketio.on("audio_chunk")
def handle_audio_chunk(audio_data):
    state = sessions.get(request.sid)

    if state is None:
        return

    partial_text = asr_service.accept_audio(
        state["stream"],
        audio_data,
    )

    if (
        partial_text
        and partial_text
        != state["last_phoneme"]
    ):
        state["last_phoneme"] = partial_text

        emit(
            "phoneme_result",
            {"text": partial_text},
        )


@socketio.on("recording_stopped")
def handle_recording_stopped():
    state = sessions.get(request.sid)

    if state is None:
        emit(
            "session_error",
            {
                "message": (
                    "Sesi rekaman belum dimulai."
                )
            },
        )
        return

    final_text = asr_service.finish_stream(
        state["stream"]
    )

    evaluation = evaluate_prediction(
        state["target_phoneme"],
        final_text,
    )

    result_payload = {
        "result_id": uuid4().hex,
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
        "tester": state["tester"],
        "test_mode": state["test_mode"],
        "letter_index": (
            state["letter_index"]
        ),
        "target_letter": (
            state["target_letter"]
        ),
        "letter_name": (
            state["letter_name"]
        ),
        "harakat": state["harakat"],
        "latin_hint": state["latin_hint"],
        "warning": state["warning"],
        "surah": state["surah"],
        "ayah": state["ayah"],
        "target_text": state["target_text"],
        "target_phoneme": (
            state["target_phoneme"]
        ),
        "raw_prediction": final_text,
        **evaluation,
    }
    result_payload["prediction"] = result_payload["prediction_clean"]

    storage.append(
        RESULTS_PATH,
        result_payload,
    )

    last_results[request.sid] = (
        result_payload
    )

    emit(
        "phoneme_final",
        result_payload,
    )

    sessions.pop(request.sid, None)


@socketio.on("submit_feedback")
def handle_submit_feedback(
    data: dict[str, Any],
):
    result = last_results.get(request.sid)

    if result is None:
        emit(
            "feedback_error",
            {
                "message": (
                    "Hasil pengujian terakhir "
                    "tidak ditemukan."
                )
            },
        )
        return

    status = str(
        data.get("status") or ""
    ).strip()

    if status not in {
        "sesuai",
        "tidak_sesuai",
    }:
        emit(
            "feedback_error",
            {
                "message": (
                    "Status feedback tidak valid."
                )
            },
        )
        return

    raw_issues = data.get("issues") or []

    if not isinstance(raw_issues, list):
        raw_issues = []

    issues = [
        str(issue).strip()
        for issue in raw_issues
        if str(issue).strip()
    ]

    note = str(
        data.get("note") or ""
    ).strip()

    feedback_payload = {
        "feedback_id": uuid4().hex,
        "result_id": result["result_id"],
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
        "tester": result["tester"],
        "test_mode": result["test_mode"],
        "letter_index": (
            result["letter_index"]
        ),
        "target_letter": (
            result["target_letter"]
        ),
        "letter_name": (
            result["letter_name"]
        ),
        "harakat": result["harakat"],
        "latin_hint": result["latin_hint"],
        "surah": result["surah"],
        "ayah": result["ayah"],
        "target_text": (
            result["target_text"]
        ),
        "target_phoneme": (
            result["target_phoneme"]
        ),
        "prediction": result["prediction"],
        "raw_prediction": result.get("raw_prediction", result["prediction"]),
        "similarity": (
            result["similarity"]
        ),
        "exact_match": (
            result["exact_match"]
        ),
        "model_differences": (
            result["differences"]
        ),
        "tajwid_feedback": (
            result["tajwid_feedback"]
        ),
        "feedback_status": status,
        "selected_issues": issues,
        "manual_feedback": note,
    }

    storage.append(
        FEEDBACK_PATH,
        feedback_payload,
    )

    response: dict[str, Any] = {
        "message": (
            "Feedback berhasil disimpan."
        ),
        "status": status,
        "test_mode": result["test_mode"],
    }

    if status == "tidak_sesuai":
        if result["test_mode"] == "uji_huruf":
            response["retry_letter_test"] = (
                get_letter_test(
                    result["letter_index"]
                )
            )

        else:
            response["retry_verse"] = {
                "surah": result["surah"],
                "ayah": result["ayah"],
                "target_text": (
                    result["target_text"]
                ),
                "target_phoneme": (
                    result["target_phoneme"]
                ),
            }

    elif result["test_mode"] == "uji_huruf":
        next_index = (
            result["letter_index"] + 1
        )

        if next_index < len(LETTER_TESTS):
            response["next_letter_test"] = (
                get_letter_test(next_index)
            )
        else:
            response[
                "letter_test_complete"
            ] = True

    elif result["test_mode"] == "random":
        try:
            response["next_verse"] = (
                quran_service.get_random_verse()
            )

        except RuntimeError as exc:
            emit(
                "feedback_error",
                {"message": str(exc)},
            )
            return

    last_results.pop(request.sid, None)

    emit(
        "feedback_saved",
        response,
    )


if __name__ == "__main__":
    socketio.run(
        app,
        host="127.0.0.1",
        port=5000,
        debug=True,
        allow_unsafe_werkzeug=True,
    )
