import json
from pathlib import Path

from app.pipelines.questionnaire_logging import build_questionnaire_ranking_dataset, log_questionnaire_outcome
from app.pipelines.recommend_router import route_recommendation


def test_questionnaire_request_emits_full_trace_logs(tmp_path: Path) -> None:
    _write_dish_cache(
        tmp_path,
        [
            {
                "dish_id": "10",
                "ingredient": {"wheat": 1.0},
                "hard_flags": {},
                "meta": {"name": "Bread bowl", "restaurant": "gc", "category": "main"},
            },
            {
                "dish_id": "11",
                "ingredient": {"chicken": 1.0},
                "hard_flags": {},
                "meta": {"name": "Chicken bowl", "restaurant": "gc", "category": "main"},
            },
        ],
    )
    routed = route_recommendation(
        derived_dir=tmp_path,
        user_id=1,
        top_k=5,
        request_context={"venue": "gc"},
        questionnaire_raw={"dislikes": ["аллергия на глютен"]},
        explicit_mode="questionnaire_only",
        environ={"RECOMMENDER_DEFAULT_MODE": "questionnaire_only", "ALLOW_ORDER_FALLBACK": "false"},
    )
    request_id = routed.scoring_stats.request_id
    assert (tmp_path / "questionnaire_requests.jsonl").exists()
    assert (tmp_path / "questionnaire_profile_snapshots.jsonl").exists()
    assert (tmp_path / "questionnaire_candidates_prefilter.jsonl").exists()
    assert (tmp_path / "questionnaire_candidate_filter_decisions.jsonl").exists()
    assert (tmp_path / "questionnaire_candidates_scored.jsonl").exists()
    assert (tmp_path / "questionnaire_recommendations_presented.jsonl").exists()

    filter_rows = _read_jsonl(tmp_path / "questionnaire_candidate_filter_decisions.jsonl")
    blocked_ids = {row["dish_id"] for row in filter_rows if not bool(row.get("hard_filter_pass", False))}
    presented_rows = _read_jsonl(tmp_path / "questionnaire_recommendations_presented.jsonl")
    presented_ids = {row["dish_id"] for row in presented_rows}
    assert "10" in blocked_ids
    assert "10" not in presented_ids
    assert "11" in presented_ids

    scored_rows = _read_jsonl(tmp_path / "questionnaire_candidates_scored.jsonl")
    scored_ids = {row["dish_id"] for row in scored_rows if str(row["request_id"]) == str(request_id)}
    assert presented_ids.issubset(scored_ids)


def test_outcomes_join_and_dataset_rows_only_from_shown_candidates(tmp_path: Path) -> None:
    _write_dish_cache(
        tmp_path,
        [
            {
                "dish_id": "21",
                "ingredient": {"chicken": 1.0},
                "hard_flags": {},
                "meta": {"name": "Chicken bowl", "restaurant": "gc", "category": "main"},
            },
            {
                "dish_id": "22",
                "ingredient": {"rice": 1.0},
                "hard_flags": {},
                "meta": {"name": "Rice bowl", "restaurant": "gc", "category": "main"},
            },
        ],
    )
    routed = route_recommendation(
        derived_dir=tmp_path,
        user_id=3,
        top_k=2,
        request_context={"venue": "gc"},
        questionnaire_raw={"likes": ["люблю мясо"], "hunger_level": "полноценный прием пищи"},
        explicit_mode="questionnaire_only",
        environ={"RECOMMENDER_DEFAULT_MODE": "questionnaire_only", "ALLOW_ORDER_FALLBACK": "false"},
    )
    request_id = routed.scoring_stats.request_id
    presented_rows = [row for row in _read_jsonl(tmp_path / "questionnaire_recommendations_presented.jsonl") if row["request_id"] == request_id]
    assert len(presented_rows) == 2
    top_dish = presented_rows[0]["dish_id"]
    log_questionnaire_outcome(
        derived_dir=tmp_path,
        request_id=request_id,
        dish_id=top_dish,
        outcome_type="clicked",
        occurred_at=None,
        user_id_or_session_id="3",
        venue_normalized="gc",
    )
    log_questionnaire_outcome(
        derived_dir=tmp_path,
        request_id=request_id,
        dish_id=top_dish,
        outcome_type="purchased",
        occurred_at=None,
        user_id_or_session_id="3",
        venue_normalized="gc",
    )
    stats = build_questionnaire_ranking_dataset(tmp_path)
    assert stats["request_count"] >= 1
    dataset_rows = [row for row in _read_jsonl(tmp_path / "questionnaire_ranking_dataset_rows.jsonl") if row["request_id"] == request_id]
    assert len(dataset_rows) == len(presented_rows)
    row_by_dish = {row["dish_id"]: row for row in dataset_rows}
    assert bool(row_by_dish[top_dish]["was_clicked"]) is True
    assert bool(row_by_dish[top_dish]["was_purchased"]) is True


def test_logging_trace_is_deterministic_for_fixed_inputs(tmp_path: Path) -> None:
    _write_dish_cache(
        tmp_path,
        [
            {
                "dish_id": "31",
                "ingredient": {"chicken": 1.0},
                "hard_flags": {},
                "meta": {"name": "Chicken bowl", "restaurant": "gc", "category": "main"},
            }
        ],
    )
    first = route_recommendation(
        derived_dir=tmp_path,
        user_id=9,
        top_k=5,
        request_context={"venue": "gc"},
        questionnaire_raw={"likes": ["люблю мясо"]},
        explicit_mode="questionnaire_only",
        environ={"RECOMMENDER_DEFAULT_MODE": "questionnaire_only", "ALLOW_ORDER_FALLBACK": "false"},
    )
    second = route_recommendation(
        derived_dir=tmp_path,
        user_id=9,
        top_k=5,
        request_context={"venue": "gc"},
        questionnaire_raw={"likes": ["люблю мясо"]},
        explicit_mode="questionnaire_only",
        environ={"RECOMMENDER_DEFAULT_MODE": "questionnaire_only", "ALLOW_ORDER_FALLBACK": "false"},
    )
    assert first.scoring_stats is not None and second.scoring_stats is not None
    traces = _read_csv_rows(tmp_path / "questionnaire_request_trace_sample.csv")
    assert len(traces) >= 2
    assert all(int(row["after_filter_count"]) >= 1 for row in traces[-2:])
    assert traces[-1]["top_1_dish_id"] == traces[-2]["top_1_dish_id"]


def _write_dish_cache(base: Path, rows: list[dict]) -> None:
    (base / "dish_features_cache.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _read_csv_rows(path: Path) -> list[dict]:
    import csv

    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        return [dict(row) for row in csv.DictReader(file_obj)]
