import json
from pathlib import Path

from app.pipelines.recommendation_dataset import (
    build_ranking_dataset,
    log_recommendation_outcome,
    log_recommendation_request,
    show_ranking_group,
)


def test_build_ranking_dataset_only_from_shown_candidates(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    req_id = log_recommendation_request(
        derived_dir=derived,
        user_id=1,
        context_snapshot={"request_context_tags": ["lunch"]},
        user_profile_snapshot_id="u_snapshot",
        profile_version="runtime_v1",
        shown_candidates=[
            {
                "dish_id": "10",
                "score": 0.9,
                "score_breakdown": {"score": 0.9},
                "dish_feature_snapshot_id": "d10",
                "dish_feature_version": "runtime_v1",
            },
            {
                "dish_id": "11",
                "score": 0.3,
                "score_breakdown": {"score": 0.3},
                "dish_feature_snapshot_id": "d11",
                "dish_feature_version": "runtime_v1",
            },
        ],
        hard_filter_status_by_dish={
            "10": {"excluded": False, "reasons": [], "compliance_unknown": False},
            "11": {"excluded": False, "reasons": [], "compliance_unknown": False},
        },
    )
    log_recommendation_outcome(derived_dir=derived, request_id=req_id, dish_id="10", outcome_type="purchased")
    log_recommendation_outcome(derived_dir=derived, request_id=req_id, dish_id="11", outcome_type="viewed_details")
    stats = build_ranking_dataset(derived_dir=derived)
    assert stats["requests"] == 1
    assert stats["candidates"] == 2
    assert stats["dataset_rows"] == 2
    assert stats["pairwise_rows"] == 1

    rows = [json.loads(line) for line in (derived / "ranking_dataset_rows.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    labels = {row["dish_id"]: row["label"] for row in rows}
    assert labels["10"] == "purchase"
    assert labels["11"] == "detail_view"
    assert "request_id=req_000001" in show_ranking_group(derived_dir=derived, request_id="req_000001")
