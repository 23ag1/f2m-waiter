from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


OUTCOME_TYPES = {
    "viewed_details",
    "added_to_cart",
    "removed_from_cart",
    "purchased",
    "dismissed",
    "expired",
}
REQUEST_BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def log_recommendation_request(
    derived_dir: Path | str,
    user_id: int,
    context_snapshot: dict[str, Any],
    user_profile_snapshot_id: str,
    profile_version: str,
    shown_candidates: list[dict[str, Any]],
    hard_filter_status_by_dish: dict[str, dict[str, Any]],
) -> str:
    base = Path(derived_dir)
    requests_path = base / "recommendation_requests.jsonl"
    candidates_path = base / "recommendation_candidates.jsonl"
    requests = _read_jsonl(requests_path)
    request_no = len(requests) + 1
    request_id = f"req_{request_no:06d}"
    occurred_at = (REQUEST_BASE_TIME + timedelta(minutes=request_no)).isoformat()

    request_row = {
        "recommendation_request_id": request_id,
        "user_id": int(user_id),
        "occurred_at": occurred_at,
        "context_snapshot": context_snapshot,
        "time_is_synthetic": True,
        "user_profile_snapshot_id": user_profile_snapshot_id,
        "profile_version": profile_version,
        "shown_candidates_count": len(shown_candidates),
    }
    requests.append(request_row)
    _write_jsonl(requests_path, requests)

    candidates = _read_jsonl(candidates_path)
    for idx, row in enumerate(shown_candidates, start=1):
        dish_id = str(row["dish_id"])
        status = hard_filter_status_by_dish.get(dish_id, {})
        candidates.append(
            {
                "recommendation_request_id": request_id,
                "user_id": int(user_id),
                "occurred_at": occurred_at,
                "context_snapshot": context_snapshot,
                "dish_id": dish_id,
                "rank_position": idx,
                "deterministic_score": float(row["score"]),
                "score_breakdown_snapshot": row["score_breakdown"],
                "hard_filter_excluded": bool(status.get("excluded", False)),
                "hard_filter_reasons": status.get("reasons", []),
                "compliance_unknown": bool(status.get("compliance_unknown", False)),
                "dish_feature_snapshot_id": row.get("dish_feature_snapshot_id"),
                "dish_feature_version": row.get("dish_feature_version", "runtime_v1"),
                "was_shown": True,
            }
        )
    _write_jsonl(candidates_path, candidates)
    return request_id


def log_recommendation_outcome(
    derived_dir: Path | str,
    request_id: str,
    dish_id: str,
    outcome_type: str,
    occurred_at: str | None = None,
    time_to_action_ms: int | None = None,
) -> dict[str, Any]:
    if outcome_type not in OUTCOME_TYPES:
        raise ValueError(f"Unsupported outcome_type={outcome_type}")
    base = Path(derived_dir)
    requests = _read_jsonl(base / "recommendation_requests.jsonl")
    request = next((row for row in requests if row["recommendation_request_id"] == request_id), None)
    if request is None:
        raise ValueError(f"request_id={request_id} not found")

    candidates = _read_jsonl(base / "recommendation_candidates.jsonl")
    candidate = next(
        (
            row
            for row in candidates
            if row["recommendation_request_id"] == request_id and str(row["dish_id"]) == str(dish_id)
        ),
        None,
    )
    if candidate is None:
        raise ValueError(f"dish_id={dish_id} not found in request_id={request_id}")

    outcomes_path = base / "recommendation_outcomes.jsonl"
    outcomes = _read_jsonl(outcomes_path)
    if not occurred_at:
        existing_for_request = [row for row in outcomes if row["recommendation_request_id"] == request_id]
        occurred_dt = datetime.fromisoformat(request["occurred_at"]) + timedelta(seconds=len(existing_for_request) + 1)
        occurred_at = occurred_dt.isoformat()
    outcome_row = {
        "recommendation_request_id": request_id,
        "user_id": int(request["user_id"]),
        "dish_id": str(dish_id),
        "outcome_type": outcome_type,
        "occurred_at": occurred_at,
        "time_to_action_ms": time_to_action_ms,
    }
    outcomes.append(outcome_row)
    outcomes.sort(key=lambda row: (row["recommendation_request_id"], row["dish_id"], row["occurred_at"], row["outcome_type"]))
    _write_jsonl(outcomes_path, outcomes)
    return outcome_row


def build_ranking_dataset(derived_dir: Path | str) -> dict[str, Any]:
    base = Path(derived_dir)
    audit_dir = base / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    requests = _read_jsonl(base / "recommendation_requests.jsonl")
    candidates = _read_jsonl(base / "recommendation_candidates.jsonl")
    outcomes = _read_jsonl(base / "recommendation_outcomes.jsonl")

    requests_by_id = {row["recommendation_request_id"]: row for row in requests}
    candidates_by_key = {
        (row["recommendation_request_id"], str(row["dish_id"])): row
        for row in candidates
    }
    outcomes_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in outcomes:
        outcomes_by_key.setdefault((row["recommendation_request_id"], str(row["dish_id"])), []).append(row)
    for key in outcomes_by_key:
        outcomes_by_key[key].sort(key=lambda row: (row.get("occurred_at", ""), row.get("outcome_type", "")))

    dataset_rows: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda row: (row["recommendation_request_id"], int(row["rank_position"]), str(row["dish_id"]))):
        if not candidate.get("was_shown", False):
            continue
        request_id = candidate["recommendation_request_id"]
        request = requests_by_id.get(request_id)
        if request is None:
            continue
        key = (request_id, str(candidate["dish_id"]))
        actions = outcomes_by_key.get(key, [])
        flags = _action_flags(actions)
        label = _label_from_flags(flags)
        time_to_action = _derive_time_to_action_ms(
            request_occurred_at=request["occurred_at"],
            actions=actions,
        )
        row = {
            "recommendation_request_id": request_id,
            "user_id": int(candidate["user_id"]),
            "dish_id": str(candidate["dish_id"]),
            "user_feature_snapshot_id": request["user_profile_snapshot_id"],
            "profile_version": request["profile_version"],
            "request_context_tags": _context_tags_from_snapshot(request.get("context_snapshot", {})),
            "dish_feature_snapshot_id": candidate.get("dish_feature_snapshot_id"),
            "dish_feature_version": candidate.get("dish_feature_version"),
            "deterministic_score": candidate["deterministic_score"],
            "score_components": candidate["score_breakdown_snapshot"],
            "rank_position": int(candidate["rank_position"]),
            "was_shown": True,
            "was_opened": flags["was_opened"],
            "was_added_to_cart": flags["was_added_to_cart"],
            "was_removed": flags["was_removed"],
            "was_purchased": flags["was_purchased"],
            "time_to_action_ms": time_to_action,
            "compliance_unknown": bool(candidate.get("compliance_unknown", False)),
            "label": label,
        }
        dataset_rows.append(row)

    dataset_rows.sort(key=lambda row: (row["recommendation_request_id"], row["rank_position"], row["dish_id"]))
    _write_jsonl(base / "ranking_dataset_rows.jsonl", dataset_rows)
    pairwise_rows = _build_pairwise_examples(dataset_rows)
    _write_pairwise_examples(audit_dir / "pairwise_examples.csv", pairwise_rows)
    _write_dataset_audits(
        audit_dir=audit_dir,
        requests=requests,
        candidates=candidates,
        outcomes=outcomes,
        dataset_rows=dataset_rows,
        pairwise_rows=pairwise_rows,
        requests_by_id=requests_by_id,
        candidates_by_key=candidates_by_key,
    )
    return {
        "requests": len(requests),
        "candidates": len(candidates),
        "dataset_rows": len(dataset_rows),
        "pairwise_rows": len(pairwise_rows),
    }


def show_ranking_group(derived_dir: Path | str, request_id: str) -> str:
    rows = _read_jsonl(Path(derived_dir) / "ranking_dataset_rows.jsonl")
    group = [row for row in rows if row["recommendation_request_id"] == request_id]
    if not group:
        return f"request_id={request_id} not found"
    group.sort(key=lambda row: (row["rank_position"], row["dish_id"]))
    lines = [f"request_id={request_id}", f"rows={len(group)}"]
    for row in group[:20]:
        lines.append(
            f"rank={row['rank_position']} dish_id={row['dish_id']} score={row['deterministic_score']} label={row['label']} purchased={row['was_purchased']} added={row['was_added_to_cart']} opened={row['was_opened']}"
        )
    return "\n".join(lines)


def _label_from_flags(flags: dict[str, bool]) -> str:
    if flags["was_purchased"]:
        return "purchase"
    if flags["was_added_to_cart"]:
        return "add_to_cart"
    if flags["was_opened"]:
        return "detail_view"
    return "shown_not_chosen"


def _action_flags(actions: list[dict[str, Any]]) -> dict[str, bool]:
    action_set = {row["outcome_type"] for row in actions}
    return {
        "was_opened": "viewed_details" in action_set,
        "was_added_to_cart": "added_to_cart" in action_set,
        "was_removed": "removed_from_cart" in action_set,
        "was_purchased": "purchased" in action_set,
    }


def _derive_time_to_action_ms(request_occurred_at: str, actions: list[dict[str, Any]]) -> int | None:
    non_terminal = [row for row in actions if row["outcome_type"] in {"viewed_details", "added_to_cart", "removed_from_cart", "purchased"}]
    if not non_terminal:
        return None
    explicit = next((row.get("time_to_action_ms") for row in non_terminal if row.get("time_to_action_ms") is not None), None)
    if explicit is not None:
        return int(explicit)
    request_dt = datetime.fromisoformat(request_occurred_at)
    first_dt = datetime.fromisoformat(non_terminal[0]["occurred_at"])
    return max(0, int((first_dt - request_dt).total_seconds() * 1000))


def _context_tags_from_snapshot(snapshot: dict[str, Any]) -> list[str]:
    tags = snapshot.get("request_context_tags", [])
    if isinstance(tags, list):
        return [str(tag) for tag in sorted(tags)]
    return []


def _build_pairwise_examples(dataset_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in dataset_rows:
        grouped.setdefault(row["recommendation_request_id"], []).append(row)

    label_priority = {"purchase": 3, "add_to_cart": 2, "detail_view": 1, "shown_not_chosen": 0}
    pairwise_rows: list[dict[str, Any]] = []
    for request_id in sorted(grouped):
        group = sorted(grouped[request_id], key=lambda x: (x["rank_position"], x["dish_id"]))
        for winner in group:
            for loser in group:
                if winner["dish_id"] == loser["dish_id"]:
                    continue
                if label_priority[winner["label"]] <= label_priority[loser["label"]]:
                    continue
                pairwise_rows.append(
                    {
                        "recommendation_request_id": request_id,
                        "winner_dish_id": winner["dish_id"],
                        "winner_label": winner["label"],
                        "loser_dish_id": loser["dish_id"],
                        "loser_label": loser["label"],
                    }
                )
    pairwise_rows.sort(
        key=lambda row: (
            row["recommendation_request_id"],
            row["winner_dish_id"],
            row["loser_dish_id"],
        )
    )
    return pairwise_rows


def _write_pairwise_examples(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["recommendation_request_id", "winner_dish_id", "winner_label", "loser_dish_id", "loser_label"])
        for row in rows:
            writer.writerow(
                [
                    row["recommendation_request_id"],
                    row["winner_dish_id"],
                    row["winner_label"],
                    row["loser_dish_id"],
                    row["loser_label"],
                ]
            )


def _write_dataset_audits(
    audit_dir: Path,
    requests: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    dataset_rows: list[dict[str, Any]],
    pairwise_rows: list[dict[str, Any]],
    requests_by_id: dict[str, dict[str, Any]],
    candidates_by_key: dict[tuple[str, str], dict[str, Any]],
) -> None:
    _write_summary(audit_dir / "ranking_dataset_summary.csv", requests, candidates, dataset_rows, pairwise_rows)
    _write_label_distribution(audit_dir / "ranking_label_distribution.csv", requests, dataset_rows)
    _write_join_quality(audit_dir / "ranking_join_quality.csv", requests_by_id, candidates_by_key, outcomes)


def _write_summary(path: Path, requests: list[dict[str, Any]], candidates: list[dict[str, Any]], dataset_rows: list[dict[str, Any]], pairwise_rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["requests_total", "candidates_total", "dataset_rows_total", "pairwise_rows_total"])
        writer.writerow([len(requests), len(candidates), len(dataset_rows), len(pairwise_rows)])


def _write_label_distribution(path: Path, requests: list[dict[str, Any]], dataset_rows: list[dict[str, Any]]) -> None:
    label_counts: dict[str, int] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in dataset_rows:
        label_counts[row["label"]] = label_counts.get(row["label"], 0) + 1
        grouped.setdefault(row["recommendation_request_id"], []).append(row)

    request_outcome_counts = {"purchase": 0, "add_to_cart": 0, "detail_view": 0, "no_action": 0}
    for request in requests:
        group = grouped.get(request["recommendation_request_id"], [])
        labels = {row["label"] for row in group}
        if "purchase" in labels:
            request_outcome_counts["purchase"] += 1
        elif "add_to_cart" in labels:
            request_outcome_counts["add_to_cart"] += 1
        elif "detail_view" in labels:
            request_outcome_counts["detail_view"] += 1
        else:
            request_outcome_counts["no_action"] += 1

    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["metric", "value"])
        for label in sorted(label_counts):
            writer.writerow([f"label_{label}", label_counts[label]])
        for key in ("purchase", "add_to_cart", "detail_view", "no_action"):
            writer.writerow([f"requests_with_{key}", request_outcome_counts[key]])


def _write_join_quality(
    path: Path,
    requests_by_id: dict[str, dict[str, Any]],
    candidates_by_key: dict[tuple[str, str], dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> None:
    outcomes_with_request = 0
    outcomes_with_candidate = 0
    for outcome in outcomes:
        req_id = outcome["recommendation_request_id"]
        if req_id in requests_by_id:
            outcomes_with_request += 1
        if (req_id, str(outcome["dish_id"])) in candidates_by_key:
            outcomes_with_candidate += 1
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "requests_total",
                "candidates_total",
                "outcomes_total",
                "outcomes_with_request",
                "outcomes_with_candidate",
                "orphan_outcomes_no_request",
                "orphan_outcomes_no_candidate",
            ]
        )
        writer.writerow(
            [
                len(requests_by_id),
                len(candidates_by_key),
                len(outcomes),
                outcomes_with_request,
                outcomes_with_candidate,
                len(outcomes) - outcomes_with_request,
                len(outcomes) - outcomes_with_candidate,
            ]
        )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    rows_sorted = sorted(rows, key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True))
    with path.open("w", encoding="utf-8") as file_obj:
        for row in rows_sorted:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows
