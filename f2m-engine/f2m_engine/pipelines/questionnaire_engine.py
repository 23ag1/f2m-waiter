from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from f2m_engine.domain.recommendation_settings import load_recommendation_settings
from f2m_engine.pipelines.dish_constraints import (
    HardFilterResult,
    apply_questionnaire_hard_filter,
    build_dish_constraints,
    evaluate_questionnaire_block_reason,
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
    recommendation_settings = load_recommendation_settings(base)
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
            "recommendation_settings_version": recommendation_settings.get("settings_version"),
            "recommendation_settings_source": recommendation_settings.get("source"),
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
    menu_appendix_items = _build_menu_appendix_items(
        request_id=request_id,
        constraints=constraints,
        venue=venue,
        normalized_profile=normalized_profile,
        limit=80,
    )
    _write_questionnaire_menu_appendix_items(derived_dir=base, rows=menu_appendix_items)
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
        recommendation_settings=recommendation_settings,
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
    conflict_rows = normalized_profile["normalization_meta"].get("conflict_audit", []) or []
    conflict_path = audit_dir / "questionnaire_profile_conflict_audit.csv"
    with conflict_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "request_id",
                "raw_signal",
                "normalized_target",
                "bucket_before",
                "bucket_after",
                "conflict_type",
                "resolution_rule",
                "warning",
            ]
        )
        for row in conflict_rows:
            writer.writerow(
                [
                    request_id,
                    row.get("raw_signal", ""),
                    row.get("normalized_target", ""),
                    row.get("bucket_before", ""),
                    row.get("bucket_after", ""),
                    row.get("conflict_type", ""),
                    row.get("resolution_rule", ""),
                    row.get("warning", ""),
                ]
            )

    soft_neg_conflicts_path = audit_dir / "questionnaire_soft_negative_conflicts.csv"
    with soft_neg_conflicts_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["request_id", "normalized_target", "conflict_type", "resolution_rule", "warning"])
        for row in conflict_rows:
            if "soft_negative" not in str(row.get("conflict_type", "")):
                continue
            writer.writerow(
                [
                    request_id,
                    row.get("normalized_target", ""),
                    row.get("conflict_type", ""),
                    row.get("resolution_rule", ""),
                    row.get("warning", ""),
                ]
            )

    precedence_matrix_path = audit_dir / "questionnaire_precedence_matrix.md"
    precedence_matrix_path.write_text(
        "\n".join(
            [
                "# Questionnaire Precedence Matrix",
                "",
                "- hard_constraint > dietary_rule > soft_negative > soft_positive > neutral",
                "- hard keys are removed from all soft buckets.",
                "- dietary forbidden keys are removed from soft_positive.",
                "- overlap between soft_positive and soft_negative is resolved in favor of soft_negative.",
            ]
        ),
        encoding="utf-8",
    )

    parser_coverage_path = audit_dir / "questionnaire_parser_phrase_coverage.csv"
    with parser_coverage_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["request_id", "metric", "value"])
        writer.writerow([request_id, "mapped_fields_count", len(normalized_profile["normalization_meta"].get("source_fields_used", []))])
        writer.writerow([request_id, "unmapped_answers_count", len(unmapped_answers)])
        writer.writerow([request_id, "want_now_count", len(normalized_profile["request_context"].get("want_now", []))])
        writer.writerow([request_id, "session_tags_count", len(normalized_profile["request_context"].get("session_tags", []))])
        writer.writerow([request_id, "satiety_value", normalized_profile["request_context"].get("satiety", "")])

    hygiene_path = audit_dir / "questionnaire_candidate_hygiene_after_block1.csv"
    with hygiene_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["request_id", "candidate_count_after_hard_filter", "non_recommendable_in_safe_set", "status"])
        leaked = len([row for row in filter_result.safe_dishes if not _is_recommendable_for_questionnaire(row)])
        writer.writerow(
            [
                request_id,
                filter_result.candidate_count_after,
                leaked,
                "pass" if leaked == 0 else "fail",
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
                "temperature_match",
                "soft_negative_penalty",
                "soft_negative_hit_key",
                "soft_negative_hit_keys",
                "soft_negative_rank_group",
                "warning_tags",
                "display_tags",
                "diversity_bonus",
                "intent_coverage_bonus",
                "venue_boost",
                "sweet_signal",
                "serving_temperature",
                "active_signal_count",
                "constant_components_neutralized",
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
                    row.get("temperature_match", 0.0),
                    row["soft_negative_penalty"],
                    row.get("soft_negative_hit_key", ""),
                    "|".join(row.get("soft_negative_hit_keys", [])),
                    row.get("soft_negative_rank_group", 0),
                    "|".join(row.get("warning_tags", [])),
                    json.dumps(row.get("display_tags", []), ensure_ascii=False, sort_keys=True),
                    row["diversity_bonus"],
                    row.get("intent_coverage_bonus", 0.0),
                    row["venue_boost"],
                    row.get("sweet_signal", 0.0),
                    row.get("serving_temperature", ""),
                    row.get("active_signal_count", 0),
                    row.get("constant_components_neutralized", ""),
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


def _build_menu_appendix_items(
    request_id: str,
    constraints: list[dict[str, Any]],
    venue: str,
    normalized_profile: NormalizedQuestionnaireProfile,
    limit: int,
) -> list[dict[str, Any]]:
    venue_norm = _norm_text(venue)
    candidates = [
        row
        for row in constraints
        if _venue_matches(row=row, venue_norm=venue_norm) and _is_menu_appendix_candidate(row)
    ]
    rows: list[dict[str, Any]] = []
    for row in sorted(candidates, key=lambda item: (str(item.get("category", "")), str(item.get("dish_name", "")), str(item.get("dish_id", "")))):
        blocked_reason = evaluate_questionnaire_block_reason(dish=row, normalized_profile=normalized_profile)
        if blocked_reason is not None:
            continue
        rows.append(
            {
                "request_id": request_id,
                "mode": "questionnaire_only",
                "menu_section": "menu_appendix_items",
                "appendix_kind": _appendix_kind(row),
                "dish_id": str(row.get("dish_id", "")),
                "dish_name": str(row.get("dish_name", "")),
                "category": str(row.get("category", "")),
                "venue": str(row.get("venue", "")),
                "rank": len(rows) + 1,
                "hard_filter_pass": True,
                "blocked_reasons": [],
                "reason": "non_food_menu_item_excluded_from_food_scoring",
            }
        )
        if len(rows) >= int(limit):
            break
    return rows


def _write_questionnaire_menu_appendix_items(derived_dir: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path = derived_dir / "questionnaire_menu_appendix_items.jsonl"
    with path.open("a", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _venue_matches(row: dict[str, Any], venue_norm: str) -> bool:
    if not venue_norm:
        return True
    return venue_norm in _norm_text(str(row.get("venue", "")))


def _is_menu_appendix_candidate(row: dict[str, Any]) -> bool:
    category = _norm_text(str(row.get("category", "")))
    name = _norm_text(str(row.get("dish_name", "")))
    merged = f"{category} {name}"
    blocked_non_appendix = (
        "service",
        "сервис",
        "ingredient",
        "ингредиент",
        "addon",
        "add-on",
        "добавк",
        "соус",
        "sauce",
        "condiment",
    )
    if any(token in merged for token in blocked_non_appendix):
        return False
    appendix_tokens = (
        "drink",
        "beverage",
        "напит",
        "кофе",
        "coffee",
        "чай",
        "tea",
        "сок",
        "juice",
        "лимонад",
        "lemonade",
        "вода",
        "water",
        "cola",
        "fanta",
        "sprite",
        "tonic",
        "тоник",
        "смузи",
        "smoothie",
        "коктейл",
        "cocktail",
        "пиво",
        "beer",
        "вино",
        "wine",
        "алког",
        "alcohol",
    )
    return any(token in merged for token in appendix_tokens)


def _appendix_kind(row: dict[str, Any]) -> str:
    merged = _norm_text(f"{row.get('category', '')} {row.get('dish_name', '')}")
    if any(token in merged for token in ("кофе", "coffee", "espresso", "americano", "cappuccino", "латте", "raf", "раф")):
        return "coffee"
    if any(token in merged for token in ("чай", "tea")):
        return "tea"
    if any(token in merged for token in ("алког", "alcohol", "beer", "пиво", "wine", "вино", "водка", "vodka")):
        return "alcohol"
    return "drink"


def _norm_text(value: str) -> str:
    return str(value or "").lower().replace("ё", "е").strip()


def _is_recommendable_for_questionnaire(dish: dict[str, Any]) -> bool:
    category = str(dish.get("category", "")).lower().replace("ё", "е").strip()
    name = str(dish.get("dish_name", "")).lower().replace("ё", "е").strip()
    merged = f"{category} {name}"
    banned_tokens = (
        "ingredient",
        "ингредиент",
        "semi_finished",
        "полуфабрикат",
        "service",
        "сервис",
        "addon",
        "add-on",
        "добавк",
        "соус",
        "sauce",
        "condiment",
        "drink",
        "beverage",
        "напит",
        "alcohol",
        "алког",
        "tonic",
        "energy",
        "энергет",
    )
    return not any(token in merged for token in banned_tokens)
