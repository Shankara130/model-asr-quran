# Repeat-Aware Retry Implementation Plan

**For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) superpowers:executing-plans implement plan task-by-task. Steps use checkbox (`- [ ]`) syntax tracking.

**Goal:** Add latest-attempt response metadata and repeat-aware prediction selection so self-retry uses the newest valid reading.

**Architecture:** Keep the first implementation migration-free. Attempt metadata is derived from existing `evaluation_results`, while repeat-aware logic lives in the pure Python evaluator before result mapping.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, pytest, existing Quran ASR evaluation helpers.

---

### Task 1: Add Repeat-Aware Prediction Selection

**Files:**

- Modify: `web/services/evaluation_service.py`
- Test: `tests/test_repeat_aware_retry.py`

- [ ] **Step 1: Write failing tests**

Create tests that call `evaluate_prediction` with simple phoneme strings:

```python
from web.services.evaluation_service import evaluate_prediction


def test_self_retry_uses_latest_correct_candidate():
    result = evaluate_prediction("abc", "axcabc")
    assert result["prediction_clean"] == "abc"
    assert result["similarity"] == 100.0
    assert result["self_corrections"][0]["type"] == "prefix_superseded"


def test_plain_prediction_has_no_self_corrections():
    result = evaluate_prediction("abc", "abc")
    assert result["prediction_clean"] == "abc"
    assert result["self_corrections"] == []
```

- [ ] **Step 2: Run focused test and verify failure**

Run:

```bash
rtk pytest tests/test_repeat_aware_retry.py -q
```

Expected: tests fail because the new file or `self_corrections` behavior does not exist yet.

- [ ] **Step 3: Implement candidate selector**

Add a helper in `web/services/evaluation_service.py`:

```python
def select_repeat_aware_prediction(target_clean: str, prediction_clean: str) -> tuple[str, list[dict[str, Any]]]:
    if not target_clean or len(prediction_clean) <= len(target_clean) + 1:
        return prediction_clean, []

    target_len = len(target_clean)
    slack = min(6, max(2, target_len // 3))
    min_len = max(1, target_len - slack)
    max_len = min(len(prediction_clean), target_len + slack)
    best: tuple[int, int, str] | None = None

    for start in range(0, len(prediction_clean)):
        for end in range(start + min_len, min(len(prediction_clean), start + max_len) + 1):
            candidate = prediction_clean[start:end]
            distance = edit_distance(target_clean, candidate)
            score = (distance, -start, candidate)
            if best is None or score < best:
                best = score

    if best is None:
        return prediction_clean, []

    _, neg_start, selected = best
    start = -neg_start
    if start == 0 and len(selected) == len(prediction_clean):
        return prediction_clean, []

    return selected, [{
        "type": "prefix_superseded",
        "detected": prediction_clean[:start],
        "selected": selected,
        "note": "Bacaan awal diabaikan karena ada pengulangan yang lebih cocok.",
    }]
```

Then call it from `evaluate_prediction` before alignment and include `self_corrections` in the returned dict.

- [ ] **Step 4: Run focused test and verify pass**

Run:

```bash
rtk pytest tests/test_repeat_aware_retry.py -q
```

Expected: PASS.

### Task 2: Surface Self-Corrections in API Mapping

**Files:**

- Modify: `api/services/result_mapper.py`
- Modify: `api/services/evaluation_pipeline.py`
- Modify: `api/schemas/evaluate.py`
- Modify: `api/routers/evaluate.py`

- [ ] **Step 1: Preserve self-correction metadata**

In `result_mapper.map_result`, pass through `raw.get("self_corrections") or []`.

- [ ] **Step 2: Store correction metadata in result recommendation**

Because there is no DB column yet, keep storage unchanged and return `self_corrections` directly in the response path when available. If result is fetched later, default to `[]`.

- [ ] **Step 3: Add response fields**

Add Pydantic model `SelfCorrectionOut` and optional fields:

```python
self_corrections: list[SelfCorrectionOut] = Field(default_factory=list)
attempt_number: int = Field(default=1)
is_latest: bool = Field(default=True)
```

- [ ] **Step 4: Compute attempt metadata in `get_result`**

Query all results for the session ordered by `created_at`, compute `attemptNumber` and `isLatest`, and include them in `EvaluationResultOut`.

### Task 3: Link Evaluation Results to Audio Attempts

**Files:**

- Modify: `api/services/evaluation_pipeline.py`

- [ ] **Step 1: Set `audio_upload_id` when creating a result**

When creating `EvaluationResult`, set `audio_upload_id=upload.id`. This makes each retry traceable to the audio used.

- [ ] **Step 2: Keep latest retry behavior**

Do not block evaluation for completed sessions. Only cancelled sessions remain invalid.

### Task 4: Verification

**Files:**

- Test: `tests/test_repeat_aware_retry.py`

- [ ] **Step 1: Run focused tests**

```bash
rtk pytest tests/test_repeat_aware_retry.py -q
```

- [ ] **Step 2: Run existing lightweight tests likely to cover evaluator behavior**

```bash
rtk pytest tests/test_corrector.py tests/test_normalize.py -q
```

- [ ] **Step 3: Inspect git diff**

```bash
rtk git diff -- docs/superpowers/specs/2026-07-16-repeat-aware-retry-design.md docs/superpowers/plans/2026-07-16-repeat-aware-retry.md web/services/evaluation_service.py api/services/result_mapper.py api/services/evaluation_pipeline.py api/schemas/evaluate.py api/routers/evaluate.py tests/test_repeat_aware_retry.py
```

Expected: only intended files changed. `uv.lock` remains untouched.
