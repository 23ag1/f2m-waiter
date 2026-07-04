from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from f2m_engine.pipelines.dish_constraints import (
    HardFilterResult,
    apply_questionnaire_hard_filter,
    build_dish_constraints,
    select_prefilter_candidates,
    write_questionnaire_filter_runtime_artifacts,
)
from f2m_engine.pipelines.questionnaire_logging import (
    build_questionnaire_ranking_dataset,
    next_questionnaire_request_id,
    write_filter_decisions,
    write_prefilter_candidates,
    write_presented_candidates,
    write_questionnaire_profile_snapshot,
    write_questionnaire_request,
    write_scored_candidates,
)
from f2m_engine.pipelines.questionnaire_normalizer import (
    NormalizedQuestionnaireProfile,
    QuestionnaireNormalizationError,
    normalize_questionnaire,
)
from f2m_engine.pipelines.questionnaire_scoring import score_questionnaire_candidates
from f2m_engine.pipelines.scoring_deterministic import ScoringStats

@dataclass(frozen=True)
class QuestionnaireScoringNotReady(Exception):
    message: str
    mode: str
    engine_selected: str
    mode_resolution_source: str
    fallback_used: bool
    normalized_profile_preview: dict[str, Any]
    candidate_filter_summary: dict[str, Any]

    def to_metadata(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "engine_selected": self.engine_selected,
            "mode_resolution_source": self.mode_resolution_source,
            "fallback_used": self.fallback_used,
            "normalized_profile_preview": self.normalized_profile_preview,
            "candidate_filter_summary": self.candidate_filter_summary,
        }


@dataclass(frozen=True)
class QuestionnaireNoSafeCandidates(Exception):
    message: str
    mode: str
    engine_selected: str
    mode_resolution_source: str
    fallback_used: bool
    blocked_reasons_summary: dict[str, int]
    candidate_count_before: int
    candidate_count_after: int

    def to_metadata(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "engine_selected": self.engine_selected,
            "mode_resolution_source": self.mode_resolution_source,
            "fallback_used": self.fallback_used,
            "blocked_reasons_summary": self.blocked_reasons_summary,
            "candidate_count_before": self.candidate_count_before,
            "candidate_count_after": self.candidate_count_after,
        }


def recommend_questionnaire_only(
    derived_dir: Path | str,
    user_id: int,
    top_k: int,
    request_context: dict[str, str] | None,
    mode_resolution_source: str,
    questionnaire_raw: dict[str, Any] | None,
) -> ScoringStats:
    base = Path(derived_dir)
    base.mkdir(parents=True, exist_ok=True)
    if not isinstance(questionnaire_raw, dict) or not questionnaire_raw:
        raise QuestionnaireNormalizationError(
            "questionnaire_only mode requires non-empty questionnaire_raw input for normalization"
        )
    normalized_profile = normalize_questionnaire(
        raw_questionnaire=questionnaire_raw,
        request_context=request_context or {},
        questionnaire_version="v1",
        profile_version="questionnaire_profile_v1",
    )
    constraints = build_dish_constraints(base)
    venue = str((request_context or {}).get("venue", "") or (request_context or {}).get("store_id", "") or "")
    prefilter_candidates = select_prefilter_candidates(dish_constraints=constraints, venue=venue)
    request_id, occurred_at = next_questionnaire_request_id(base)
    profile_snapshot_id = write_questionnaire_profile_snapshot(
        derived_dir=base,
        request_id=request_id,
        mode="questionnaire_only",
        user_id_or_session_id=str(user_id),
        normalized_profile=normalized_profile,
    )
    write_questionnaire_request(
        derived_dir=base,
        row={
            "request_id": request_id,
            "mode": "questionnaire_only",
            "engine_selected": "questionnaire_engine",
            "occurred_at": occurred_at,
            "venue_raw": venue,
            "venue_normalized": venue,
            "questionnaire_version": normalized_profile["request_context"].get("questionnaire_version", "v1"),
            "profile_version": normalized_profile["normalization_meta"].get("profile_version", "questionnaire_profile_v1"),
            "scoring_version": "questionnaire_scoring_v1",
            "constraint_version": "dish_constraints_v1",
            "top_k_requested": int(top_k),
            "questionnaire_raw_json": questionnaire_raw,
            "normalized_profile_json": normalized_profile,
            "normalization_meta": normalized_profile["normalization_meta"],
            "mode_resolution_source": mode_resolution_source,
            "fallback_used": False,
            "questionnaire_profile_snapshot_id": profile_snapshot_id,
            "user_id_or_session_id": str(user_id),
            "scenario_label": str((request_context or {}).get("scenario_label", "") or ""),
        },
    )
    write_prefilter_candidates(
        derived_dir=base,
        request_id=request_id,
        mode="questionnaire_only",
        venue_normalized=venue,
        rows=prefilter_candidates,
    )
    filter_result = apply_questionnaire_hard_filter(
        request_id=request_id,
        venue=venue,
        normalized_profile=normalized_profile,
        dish_constraints=constraints,
    )
    write_filter_decisions(
        derived_dir=base,
        request_id=request_id,
        mode="questionnaire_only",
        venue_normalized=venue,
        rows=filter_result.filter_decision_rows,
    )
    write_questionnaire_filter_runtime_artifacts(derived_dir=base, result=filter_result)
    _write_questionnaire_debug_outputs(
        derived_dir=base,
        request_id=request_id,
        user_id=user_id,
        normalized_profile=normalized_profile,
        filter_result=filter_result,
    )
    if filter_result.zero_safe_candidates_flag:
        raise QuestionnaireNoSafeCandidates(
            message="No safe candidates remain after questionnaire hard filtering.",
            mode="questionnaire_only",
            engine_selected="questionnaire_engine",
            mode_resolution_source=mode_resolution_source,
            fallback_used=False,
            blocked_reasons_summary=filter_result.blocked_reasons_summary,
            candidate_count_before=filter_result.candidate_count_before,
            candidate_count_after=filter_result.candidate_count_after,
        )
    ranked_rows, rank_trace = score_questionnaire_candidates(
        request_id=request_id,
        user_id=user_id,
        normalized_profile=normalized_profile,
        safe_candidates=filter_result.safe_dishes,
        request_context={
            **(request_context or {}),
            "candidate_count_before_filter": filter_result.candidate_count_before,
            "candidate_count_after_filter": filter_result.candidate_count_after,
            "venue": venue,
        },
        top_k=top_k,
    )
    write_scored_candidates(derived_dir=base, rows=ranked_rows)
    write_presented_candidates(derived_dir=base, top_rows=ranked_rows[: int(top_k)])
    _write_questionnaire_scoring_outputs(
        derived_dir=base,
        ranked_rows=ranked_rows,
        rank_trace=rank_trace,
    )
    build_questionnaire_ranking_dataset(base)
    return ScoringStats(
        user_id=int(user_id),
        request_id=request_id,
        survivors=len(ranked_rows),
        excluded=filter_result.blocked_count,
        top_k=min(int(top_k), len(ranked_rows)),
    )


def _write_questionnaire_debug_outputs(
    derived_dir: Path,
    request_id: str,
    user_id: int,
    normalized_profile: NormalizedQuestionnaireProfile,
    filter_result: HardFilterResult,
) -> None:
    audit_dir = derived_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    debug_path = audit_dir / "questionnaire_normalized_profile_debug.json"
    debug_payload = {
        "request_id": request_id,
        "user_id": int(user_id),
        "normalized_profile": normalized_profile,
        "candidate_filter_summary": {
            "candidate_count_before": filter_result.candidate_count_before,
            "candidate_count_after": filter_result.candidate_count_after,
            "blocked_count": filter_result.blocked_count,
            "zero_safe_candidates_flag": filter_result.zero_safe_candidates_flag,
            "blocked_reasons_summary": filter_result.blocked_reasons_summary,
        },
    }
    debug_path.write_text(json.dumps(debug_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    unmapped_path = audit_dir / "questionnaire_unmapped_answers_runtime.csv"
    unmapped_answers = normalized_profile["normalization_meta"].get("unmapped_answers", [])
    with unmapped_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["request_id", "raw_field_name", "raw_answer_value", "reason"])
        for row in unmapped_answers:
            writer.writerow(
                [
                    request_id,
                    row.get("raw_field_name", ""),
                    row.get("raw_answer_value", ""),
                    row.get("reason", ""),
                ]
            )


def _write_questionnaire_scoring_outputs(
    derived_dir: Path,
    ranked_rows: list[dict[str, Any]],
    rank_trace: dict[str, Any],
) -> None:
    top_rows = ranked_rows[:10]
    with (derived_dir / "recommendation_scores.jsonl").open("w", encoding="utf-8") as file_obj:
        for row in ranked_rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    with (derived_dir / "questionnaire_recommendations_sample.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["request_id", "rank", "dish_id", "dish_name", "final_score", "explanation"])
        for row in top_rows:
            writer.writerow(
                [
                    row["request_id"],
                    row["rank"],
                    row["dish_id"],
                    row["dish_name"],
                    row["final_score"],
                    row["explanation"],
                ]
            )

    with (derived_dir / "questionnaire_score_debug_sample.csv").open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "request_id",
                "dish_id",
                "dish_name",
                "hard_filter_pass",
                "blocked_reasons",
                "desired_content_match",
                "satiety_match",
                "nutrition_match",
                "cuisine_match",
                "familiarity_novelty_match",
                "soft_negative_penalty",
                "diversity_bonus",
                "venue_boost",
                "final_score",
                "explanation",
                "rank",
            ]
        )
        for row in ranked_rows[:300]:
            writer.writerow(
                [
                    row["request_id"],
                    row["dish_id"],
                    row["dish_name"],
                    row["hard_filter_pass"],
                    "|".join(row.get("blocked_reasons", [])),
                    row["desired_content_match"],
                    row["satiety_match"],
                    row["nutrition_match"],
                    row["cuisine_match"],
                    row["familiarity_novelty_match"],
                    row["soft_negative_penalty"],
                    row["diversity_bonus"],
                    row["venue_boost"],
                    row["final_score"],
                    row["explanation"],
                    row["rank"],
                ]
            )

    trace_path = derived_dir / "questionnaire_candidate_rank_trace.csv"
    exists = trace_path.exists() and trace_path.stat().st_size > 0
    with trace_path.open("a", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        if not exists:
            writer.writerow(
                [
                    "request_id",
                    "candidate_count_before_filter",
                    "candidate_count_after_filter",
                    "ranked_candidate_count",
                    "top_1_dish_id",
                    "top_1_score",
                    "top_5_ids",
                ]
            )
        writer.writerow(
            [
                rank_trace["request_id"],
                rank_trace["candidate_count_before_filter"],
                rank_trace["candidate_count_after_filter"],
                rank_trace["ranked_candidate_count"],
                rank_trace["top_1_dish_id"],
                rank_trace["top_1_score"],
                rank_trace["top_5_ids"],
            ]
        )
