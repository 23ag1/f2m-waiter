from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from f2m_engine.pipelines.questionnaire_engine import recommend_questionnaire_only
from f2m_engine.pipelines.scoring_deterministic import ScoringStats, score_dishes_for_user

SUPPORTED_MODES = {"questionnaire_only", "orders_only", "auto"}
DEFAULT_MODE_ENV_KEY = "RECOMMENDER_DEFAULT_MODE"
ALLOW_ORDER_FALLBACK_ENV_KEY = "ALLOW_ORDER_FALLBACK"


class ModeResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ModeResolution:
    explicit_mode: str
    env_default_mode: str
    resolved_mode: str
    mode_resolution_source: str
    engine_selected: str
    fallback_used: bool
    resolution_reason: str


@dataclass(frozen=True)
class RoutedRecommendation:
    scoring_stats: ScoringStats | None
    mode_resolution: ModeResolution


def resolve_mode(
    explicit_mode: str | None,
    environ: Mapping[str, str] | None = None,
) -> ModeResolution:
    env = environ or os.environ
    env_default_mode = _normalize_mode(env.get(DEFAULT_MODE_ENV_KEY, "questionnaire_only"))
    if env_default_mode not in SUPPORTED_MODES:
        raise ModeResolutionError(
            f"{DEFAULT_MODE_ENV_KEY} must be one of {sorted(SUPPORTED_MODES)}; got: {env_default_mode}"
        )

    normalized_explicit_mode = _normalize_mode(explicit_mode) if explicit_mode is not None else ""
    if normalized_explicit_mode:
        if normalized_explicit_mode not in SUPPORTED_MODES:
            raise ModeResolutionError(
                f"explicit mode must be one of {sorted(SUPPORTED_MODES)}; got: {normalized_explicit_mode}"
            )
        resolved_mode = normalized_explicit_mode
        mode_resolution_source = "explicit_request_mode"
        resolution_reason = "explicit mode has highest priority"
    else:
        resolved_mode = env_default_mode
        mode_resolution_source = "env_default_mode"
        resolution_reason = "explicit mode is absent; env default applied"

    engine_selected, engine_reason = _select_engine_for_mode(resolved_mode)
    allow_order_fallback = _parse_bool(env.get(ALLOW_ORDER_FALLBACK_ENV_KEY, "false"))
    fallback_used = False
    if resolved_mode == "questionnaire_only" and allow_order_fallback:
        # Explicitly ignore fallback for questionnaire mode in Milestone 1.
        fallback_used = False
        engine_reason = f"{engine_reason}; order fallback disabled for questionnaire_only"

    return ModeResolution(
        explicit_mode=normalized_explicit_mode,
        env_default_mode=env_default_mode,
        resolved_mode=resolved_mode,
        mode_resolution_source=mode_resolution_source,
        engine_selected=engine_selected,
        fallback_used=fallback_used,
        resolution_reason=engine_reason if normalized_explicit_mode else f"{resolution_reason}; {engine_reason}",
    )


def route_recommendation(
    derived_dir: Path | str,
    user_id: int,
    top_k: int,
    request_context: dict[str, str] | None = None,
    questionnaire_raw: dict[str, Any] | None = None,
    explicit_mode: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> RoutedRecommendation:
    resolution = resolve_mode(explicit_mode=explicit_mode, environ=environ)
    base = Path(derived_dir)
    context = request_context or {}

    if resolution.engine_selected == "orders_engine":
        stats = score_dishes_for_user(
            derived_dir=base,
            user_id=user_id,
            top_k=top_k,
            request_context=context,
        )
        return RoutedRecommendation(scoring_stats=stats, mode_resolution=resolution)

    if resolution.engine_selected == "questionnaire_engine":
        stats = recommend_questionnaire_only(
            derived_dir=base,
            user_id=user_id,
            top_k=top_k,
            request_context=context,
            mode_resolution_source=resolution.mode_resolution_source,
            questionnaire_raw=questionnaire_raw,
        )
        return RoutedRecommendation(scoring_stats=stats, mode_resolution=resolution)

    raise ModeResolutionError(f"Unsupported engine_selected: {resolution.engine_selected}")


def _select_engine_for_mode(mode: str) -> tuple[str, str]:
    if mode == "questionnaire_only":
        return "questionnaire_engine", "mode=questionnaire_only routes to deterministic questionnaire normalization engine"
    if mode == "orders_only":
        return "orders_engine", "mode=orders_only routes to existing deterministic scorer"
    if mode == "auto":
        return "orders_engine", "mode=auto currently uses deterministic stub route to orders engine"
    raise ModeResolutionError(f"Unsupported mode: {mode}")


def _normalize_mode(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
