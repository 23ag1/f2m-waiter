from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

QUESTIONNAIRE_REQUEST_BASE_TIME = datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc)
QUESTIONNAIRE_OUTCOME_TYPES = {
    "shown",
    "opened",
    "clicked",
    "added_to_cart",
    "removed_from_cart",
    "purchased",
    "dismissed",
    "expired",
}


def next_questionnaire_request_id(derived_dir: Path | str) -> tuple[str, str]:
    base = Path(derived_dir)
    requests = _read_jsonl(base / "questionnaire_requests.jsonl")
    request_no = len(requests) + 1
    request_id = f"qreq_{request_no:06d}"
    occurred_at = (QUESTIONNAIRE_REQUEST_BASE_TIME + timedelta(minutes=request_no)).isoformat()
    return request_id, occurred_at


def write_questionnaire_request(
    derived_dir: Path | str,
    row: dict[str, Any],
) -> None:
    _append_jsonl(Path(derived_dir) / "questionnaire_requests.jsonl", row)


def write_questionnaire_profile_snapshot(
    derived_dir: Path | str,
    request_id: str,
    mode: str,
    user_id_or_session_id: str,
    normalized_profile: dict[str, Any],
) -> str:
    snapshot_payload = json.dumps(normalized_profile, ensure_ascii=False, sort_keys=True)
    snapshot_id = hashlib.sha256(snapshot_payload.encode("utf-8")).hexdigest()[:16]
    row = {
        "request_id": request_id,
        "mode": mode,
        "user_id_or_session_id": user_id_or_session_id,
        "questionnaire_profile_snapshot_id": snapshot_id,
        "normalized_profile_json": normalized_profile,
        "normalization_meta": normalized_profile.get("normalization_meta", {}),
    }
    _append_jsonl(Path(derived_dir) / "questionnaire_profile_snapshots.jsonl", row)
    return snapshot_id


def write_prefilter_candidates(
    derived_dir: Path | str,
    request_id: str,
    mode: str,
    venue_normalized: str,
    rows: list[dict[str, Any]],
) -> None:
    path = Path(derived_dir) / "questionnaire_candidates_prefilter.jsonl"
    for row in rows:
        _append_jsonl(
            path,
            {
                "request_id": request_id,
                "mode": mode,
                "venue_normalized": venue_normalized,
                "dish_id": str(row.get("dish_id", "")),
                "dish_name": str(row.get("dish_name", "")),
                "parse_confidence": float(row.get("parse_confidence", 0.0)),
                "review_required": bool(row.get("review_required", False)),
            },
        )


def write_filter_decisions(
    derived_dir: Path | str,
    request_id: str,
    mode: str,
    venue_normalized: str,
    rows: list[dict[str, Any]],
) -> None:
    path = Path(derived_dir) / "questionnaire_candidate_filter_decisions.jsonl"
    for row in rows:
        _append_jsonl(
            path,
            {
                "request_id": request_id,
                "mode": mode,
                "venue_normalized": venue_normalized,
                "dish_id": str(row.get("dish_id", "")),
                "dish_name": str(row.get("dish_name", "")),
                "hard_filter_pass": bool(row.get("hard_filter_pass", False)),
                "blocked_reasons": row.get("blocked_reasons", []),
                "blocked_reason_type": str(row.get("blocked_reason_type", "")),
                "parse_confidence": float(row.get("parse_confidence", 0.0)),
                "review_required": bool(row.get("review_required", False)),
                "survived": bool(row.get("survived", False)),
            },
        )


def write_scored_candidates(
    derived_dir: Path | str,
    rows: list[dict[str, Any]],
) -> None:
    path = Path(derived_dir) / "questionnaire_candidates_scored.jsonl"
    for row in rows:
        _append_jsonl(path, row)


def write_presented_candidates(
    derived_dir: Path | str,
    top_rows: list[dict[str, Any]],
) -> None:
    path = Path(derived_dir) / "questionnaire_recommendations_presented.jsonl"
    for row in top_rows:
        _append_jsonl(
            path,
            {
                "request_id": row["request_id"],
                "mode": "questionnaire_only",
                "dish_id": row["dish_id"],
                "rank": int(row["rank"]),
                "final_score": float(row["final_score"]),
                "explanation": row["explanation"],
                "desired_content_match": float(row["desired_content_match"]),
                "satiety_match": float(row["satiety_match"]),
                "nutrition_match": float(row["nutrition_match"]),
                "cuisine_match": float(row["cuisine_match"]),
                "familiarity_novelty_match": float(row["familiarity_novelty_match"]),
                "soft_negative_penalty": float(row["soft_negative_penalty"]),
                "diversity_bonus": float(row["diversity_bonus"]),
                "venue_boost": float(row["venue_boost"]),
                "hard_filter_pass": True,
            },
        )


def log_questionnaire_outcome(
    derived_dir: Path | str,
    request_id: str,
    dish_id: str,
    outcome_type: str,
    occurred_at: str | None,
    user_id_or_session_id: str,
    venue_normalized: str,
) -> dict[str, Any]:
    canonical_outcome = _canonical_outcome(outcome_type)
    if canonical_outcome not in QUESTIONNAIRE_OUTCOME_TYPES:
        raise ValueError(f"Unsupported questionnaire outcome_type={outcome_type}")
    path = Path(derived_dir) / "questionnaire_outcomes.jsonl"
    outcomes = _read_jsonl(path)
    if not occurred_at:
        occurred_at = (QUESTIONNAIRE_REQUEST_BASE_TIME + timedelta(seconds=len(outcomes) + 1)).isoformat()
    row = {
        "request_id": request_id,
        "mode": "questionnaire_only",
        "user_id_or_session_id": user_id_or_session_id,
        "dish_id": str(dish_id),
        "outcome_type": canonical_outcome,
        "occurred_at": occurred_at,
        "venue_normalized": venue_normalized,
    }
    _append_jsonl(path, row)
    return row


def build_questionnaire_ranking_dataset(derived_dir: Path | str) -> dict[str, int]:
    base = Path(derived_dir)
    requests = _read_jsonl(base / "questionnaire_requests.jsonl")
    prefilter = _read_jsonl(base / "questionnaire_candidates_prefilter.jsonl")
    filter_rows = _read_jsonl(base / "questionnaire_candidate_filter_decisions.jsonl")
    scored = _read_jsonl(base / "questionnaire_candidates_scored.jsonl")
    presented = _read_jsonl(base / "questionnaire_recommendations_presented.jsonl")
    outcomes = _read_jsonl(base / "questionnaire_outcomes.jsonl")
    profile_snapshots = _read_jsonl(base / "questionnaire_profile_snapshots.jsonl")
    profile_by_request = {str(row.get("request_id", "")): row for row in profile_snapshots}

    shown_keys = {(str(row["request_id"]), str(row["dish_id"])) for row in presented}
    scored_by_key = {(str(row["request_id"]), str(row["dish_id"])): row for row in scored}
    filter_by_key = {(str(row["request_id"]), str(row["dish_id"])): row for row in filter_rows}
    outcomes_by_key: dict[tuple[str, str], set[str]] = {}
    for row in outcomes:
        key = (str(row.get("request_id", "")), str(row.get("dish_id", "")))
        outcomes_by_key.setdefault(key, set()).add(str(row.get("outcome_type", "")))

    dataset_rows: list[dict[str, Any]] = []
    for request_id, dish_id in sorted(shown_keys):
        scored_row = scored_by_key.get((request_id, dish_id))
        if scored_row is None:
            continue
        filter_row = filter_by_key.get((request_id, dish_id), {})
        outcome_set = outcomes_by_key.get((request_id, dish_id), set())
        req = next((row for row in requests if str(row.get("request_id")) == request_id), {})
        snapshot = profile_by_request.get(request_id, {})
        dataset_rows.append(
            {
                "request_id": request_id,
                "mode": "questionnaire_only",
                "user_id_or_session_id": req.get("user_id_or_session_id", ""),
                "venue_normalized": req.get("venue_normalized", ""),
                "questionnaire_profile_snapshot_id": snapshot.get("questionnaire_profile_snapshot_id", ""),
                "dish_id": dish_id,
                "hard_filter_pass": bool(scored_row.get("hard_filter_pass", True)),
                "blocked_reasons_summary": "|".join(filter_row.get("blocked_reasons", [])),
                "desired_content_match": scored_row.get("desired_content_match", 0.0),
                "satiety_match": scored_row.get("satiety_match", 0.0),
                "nutrition_match": scored_row.get("nutrition_match", 0.0),
                "cuisine_match": scored_row.get("cuisine_match", 0.0),
                "familiarity_novelty_match": scored_row.get("familiarity_novelty_match", 0.0),
                "soft_negative_penalty": scored_row.get("soft_negative_penalty", 0.0),
                "diversity_bonus": scored_row.get("diversity_bonus", 0.0),
                "venue_boost": scored_row.get("venue_boost", 0.0),
                "final_score": scored_row.get("final_score", 0.0),
                "rank": scored_row.get("rank", 0),
                "was_shown": True,
                "was_opened": "opened" in outcome_set,
                "was_clicked": "clicked" in outcome_set,
                "was_added_to_cart": "added_to_cart" in outcome_set,
                "was_removed": "removed_from_cart" in outcome_set,
                "was_purchased": "purchased" in outcome_set,
                "was_dismissed": "dismissed" in outcome_set,
                "was_expired": "expired" in outcome_set,
            }
        )
    _write_jsonl(base / "questionnaire_ranking_dataset_rows.jsonl", dataset_rows)
    pairwise = _build_pairwise(dataset_rows)
    _write_pairwise(base / "questionnaire_pairwise_examples.csv", pairwise)
    _write_dataset_summary(base, requests, prefilter, filter_rows, scored, presented, outcomes, dataset_rows)
    _write_label_distribution(base, presented, outcomes)
    _write_filter_reason_distribution(base, filter_rows)
    _write_request_trace_sample(base, requests, prefilter, filter_rows, presented, scored)
    return {
        "request_count": len(requests),
        "dataset_rows_count": len(dataset_rows),
        "pairwise_rows_count": len(pairwise),
    }


def _canonical_outcome(value: str) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "viewed_details": "opened",
        "opened": "opened",
        "clicked": "clicked",
        "added_to_cart": "added_to_cart",
        "removed_from_cart": "removed_from_cart",
        "purchased": "purchased",
        "dismissed": "dismissed",
        "expired": "expired",
        "shown": "shown",
    }
    return mapping.get(raw, raw)


def _build_pairwise(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["request_id"]), []).append(row)
    priority = {"was_purchased": 4, "was_added_to_cart": 3, "was_clicked": 2, "was_opened": 1, "was_shown": 0}
    result: list[dict[str, Any]] = []
    for request_id, group in sorted(grouped.items()):
        for winner in group:
            for loser in group:
                if winner["dish_id"] == loser["dish_id"]:
                    continue
                if _label_priority(winner, priority) <= _label_priority(loser, priority):
                    continue
                result.append(
                    {
                        "request_id": request_id,
                        "winner_dish_id": winner["dish_id"],
                        "loser_dish_id": loser["dish_id"],
                        "winner_rank": winner["rank"],
                        "loser_rank": loser["rank"],
                    }
                )
    result.sort(key=lambda row: (row["request_id"], row["winner_dish_id"], row["loser_dish_id"]))
    return result


def _label_priority(row: dict[str, Any], priority: dict[str, int]) -> int:
    for key, value in sorted(priority.items(), key=lambda item: -item[1]):
        if bool(row.get(key, False)):
            return value
    return 0


def _write_pairwise(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["request_id", "winner_dish_id", "loser_dish_id", "winner_rank", "loser_rank"])
        for row in rows:
            writer.writerow([row["request_id"], row["winner_dish_id"], row["loser_dish_id"], row["winner_rank"], row["loser_rank"]])


def _write_dataset_summary(
    base: Path,
    requests: list[dict[str, Any]],
    prefilter: list[dict[str, Any]],
    filter_rows: list[dict[str, Any]],
    scored: list[dict[str, Any]],
    presented: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    dataset_rows: list[dict[str, Any]],
) -> None:
    filtered_out = len([row for row in filter_rows if not bool(row.get("hard_filter_pass", False))])
    with (base / "questionnaire_dataset_summary.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "request_count",
                "prefilter_candidate_count",
                "filtered_out_count",
                "scored_candidate_count",
                "presented_count",
                "outcomes_count",
                "dataset_rows_count",
            ]
        )
        writer.writerow([len(requests), len(prefilter), filtered_out, len(scored), len(presented), len(outcomes), len(dataset_rows)])


def _write_label_distribution(base: Path, presented: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> None:
    counts = {
        "shown": len(presented),
        "opened": 0,
        "clicked": 0,
        "added_to_cart": 0,
        "removed": 0,
        "purchased": 0,
        "dismissed": 0,
        "expired": 0,
    }
    for row in outcomes:
        outcome = str(row.get("outcome_type", ""))
        if outcome == "opened":
            counts["opened"] += 1
        elif outcome == "clicked":
            counts["clicked"] += 1
        elif outcome == "added_to_cart":
            counts["added_to_cart"] += 1
        elif outcome == "removed_from_cart":
            counts["removed"] += 1
        elif outcome == "purchased":
            counts["purchased"] += 1
        elif outcome == "dismissed":
            counts["dismissed"] += 1
        elif outcome == "expired":
            counts["expired"] += 1
    with (base / "questionnaire_label_distribution.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["label", "count"])
        for key in ("shown", "opened", "clicked", "added_to_cart", "removed", "purchased", "dismissed", "expired"):
            writer.writerow([key, counts[key]])


def _write_filter_reason_distribution(base: Path, rows: list[dict[str, Any]]) -> None:
    type_counts: dict[str, int] = {}
    key_counts: dict[str, int] = {}
    for row in rows:
        if bool(row.get("hard_filter_pass", False)):
            continue
        reason_type = str(row.get("blocked_reason_type", ""))
        reason_key = "|".join(row.get("blocked_reasons", [])) or "unknown"
        type_counts[reason_type] = type_counts.get(reason_type, 0) + 1
        key_counts[reason_key] = key_counts.get(reason_key, 0) + 1
    with (base / "questionnaire_filter_reason_distribution.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["distribution_type", "key", "count"])
        for key, value in sorted(type_counts.items()):
            writer.writerow(["blocked_reason_type", key, value])
        for key, value in sorted(key_counts.items()):
            writer.writerow(["blocked_reason_key", key, value])


def _write_request_trace_sample(
    base: Path,
    requests: list[dict[str, Any]],
    prefilter: list[dict[str, Any]],
    filter_rows: list[dict[str, Any]],
    presented: list[dict[str, Any]],
    scored: list[dict[str, Any]],
) -> None:
    pre_by_request = _count_by_request(prefilter)
    presented_by_request = _count_by_request(presented)
    scored_by_request = _count_by_request(scored)
    blocked_by_request = {}
    after_filter_by_request = {}
    top_by_request: dict[str, tuple[str, float]] = {}
    for row in filter_rows:
        request_id = str(row.get("request_id", ""))
        if bool(row.get("hard_filter_pass", False)):
            after_filter_by_request[request_id] = after_filter_by_request.get(request_id, 0) + 1
        else:
            blocked_by_request[request_id] = blocked_by_request.get(request_id, 0) + 1
    for row in scored:
        request_id = str(row.get("request_id", ""))
        rank = int(row.get("rank", 10**9))
        if rank == 1:
            top_by_request[request_id] = (str(row.get("dish_id", "")), float(row.get("final_score", 0.0)))

    with (base / "questionnaire_request_trace_sample.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "request_id",
                "venue",
                "prefilter_count",
                "after_filter_count",
                "shown_count",
                "top_1_dish_id",
                "top_1_score",
                "blocked_count",
                "zero_safe_candidates_flag",
            ]
        )
        for req in sorted(requests, key=lambda row: str(row.get("request_id", "")))[:200]:
            request_id = str(req.get("request_id", ""))
            top = top_by_request.get(request_id, ("", 0.0))
            after_filter = int(after_filter_by_request.get(request_id, 0))
            writer.writerow(
                [
                    request_id,
                    req.get("venue_normalized", ""),
                    int(pre_by_request.get(request_id, 0)),
                    after_filter,
                    int(presented_by_request.get(request_id, 0)),
                    top[0],
                    top[1],
                    int(blocked_by_request.get(request_id, 0)),
                    after_filter == 0,
                ]
            )


def _count_by_request(rows: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        request_id = str(row.get("request_id", ""))
        result[request_id] = result.get(request_id, 0) + 1
    return result


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    rows = _read_jsonl(path)
    rows.append(row)
    _write_jsonl(path, rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    rows_sorted = sorted(rows, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    with path.open("w", encoding="utf-8") as file_obj:
        for row in rows_sorted:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    result: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            stripped = line.strip()
            if stripped:
                result.append(json.loads(stripped))
    return result
