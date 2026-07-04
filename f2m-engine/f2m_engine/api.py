from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from f2m_engine.domain.cvp import build_cvp_profile
from f2m_engine.domain.models import Event, EventItem, UserConstraint, UserFeatureValue
from f2m_engine.domain.recommendation_settings import (
    load_recommendation_settings,
    normalize_recommendation_settings,
    RECOMMENDATION_SETTINGS_FILENAME,
)
from f2m_engine.pipelines.profile_rebuild import rebuild_profiles
from f2m_engine.pipelines.questionnaire_normalizer import QuestionnaireNormalizationError
from f2m_engine.pipelines.questionnaire_engine import QuestionnaireNoSafeCandidates, QuestionnaireScoringNotReady
from f2m_engine.pipelines.questionnaire_logging import build_questionnaire_ranking_dataset, log_questionnaire_outcome
from f2m_engine.pipelines.recommendation_dataset import build_ranking_dataset, log_recommendation_outcome
from f2m_engine.pipelines.recommend_router import ModeResolutionError, route_recommendation
from f2m_engine.services.cache import RecommendationCache
from f2m_engine.repositories.postgres_repository import PostgresRepository
from f2m_engine.services.repository_sync import export_postgres_to_derived, import_derived_to_postgres


VENDOR_TAXONOMY_PATH = Path(__file__).resolve().parent / "data" / "taxonomy.json"

import threading as _threading
_score_lock = _threading.Lock()  # prevent concurrent requests from overwriting each other's scores file


class EventIngestRequest(BaseModel):
    source_system: str
    event_uuid: str
    user_id: int
    event_type: str
    object_type: str = "dish"
    object_id: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str | None = None
    item: dict[str, Any] | None = None


class QuestionnaireSubmitRequest(BaseModel):
    user_id: int
    questionnaire_type: str = "manual"
    raw_answers_json: dict[str, Any]
    extracted_json: dict[str, Any] = Field(default_factory=dict)
    hard_constraints: list[dict[str, Any]] = Field(default_factory=list)
    explicit_features: list[dict[str, Any]] = Field(default_factory=list)


class ScoreRequest(BaseModel):
    user_id: int
    top_k: int = 10
    context: dict[str, str] = Field(default_factory=dict)
    mode: str | None = None
    questionnaire_raw: dict[str, Any] | None = None


class OutcomeRequest(BaseModel):
    dish_id: str
    outcome: str
    occurred_at: str | None = None
    time_to_action_ms: int | None = None


class RecommendationSettingsPatch(BaseModel):
    manual_tag_overrides: list[dict[str, Any]] | None = None
    priority_dish_ids: list[str] | None = None
    priority_ingredients: list[str] | None = None
    stop_list_dish_ids: list[str] | None = None
    priority_boost: float | None = None
    max_priority_boosted_items: int | None = None
    allow_alcohol: bool | None = None
    business_goals: dict[str, Any] | None = None


def create_app(dsn: str, derived_dir: str = "data/derived") -> FastAPI:
    app = FastAPI(title="Food2Mood MVP API")
    repo = PostgresRepository(dsn=dsn)
    derived = Path(derived_dir)
    derived.mkdir(parents=True, exist_ok=True)
    cache = RecommendationCache()

    # ─── Config endpoints ────────────────────────────────────────────

    @app.get("/config/settings")
    def get_config_settings() -> dict[str, Any]:
        return load_recommendation_settings(derived)

    @app.patch("/config/settings")
    def patch_config_settings(payload: RecommendationSettingsPatch) -> dict[str, Any]:
        settings = load_recommendation_settings(derived)
        if payload.manual_tag_overrides is not None:
            settings["manual_tag_overrides"] = list(payload.manual_tag_overrides)
        if payload.priority_dish_ids is not None:
            settings["priority_dish_ids"] = sorted(set(str(x) for x in payload.priority_dish_ids))
        if payload.priority_ingredients is not None:
            settings["priority_ingredients"] = sorted(set(str(x) for x in payload.priority_ingredients))
        if payload.stop_list_dish_ids is not None:
            settings["stop_list_dish_ids"] = sorted(set(str(x) for x in payload.stop_list_dish_ids))
        if payload.priority_boost is not None:
            settings["priority_boost"] = payload.priority_boost
        if payload.max_priority_boosted_items is not None:
            settings["max_priority_boosted_items"] = payload.max_priority_boosted_items
        if payload.allow_alcohol is not None:
            settings["allow_alcohol"] = payload.allow_alcohol
        if payload.business_goals is not None:
            current = dict(settings.get("business_goals") or {})
            current.update(payload.business_goals)
            settings["business_goals"] = current
        settings = normalize_recommendation_settings(settings)
        path = derived / RECOMMENDATION_SETTINGS_FILENAME
        path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        cache.invalidate_all()
        return settings

    # ─── Events ──────────────────────────────────────────────────────

    @app.post("/events/ingest")
    def ingest_event(payload: EventIngestRequest) -> dict[str, Any]:
        event = Event(
            source_system=payload.source_system,
            event_uuid=payload.event_uuid,
            user_id=payload.user_id,
            event_type=payload.event_type,
            object_type=payload.object_type,
            object_id=payload.object_id,
            payload_json=payload.payload_json,
            occurred_at=payload.occurred_at,
        )
        repo.upsert_event(event)
        if payload.item:
            item = EventItem(
                source_system=payload.source_system,
                event_uuid=payload.event_uuid,
                line_no=int(payload.item.get("line_no", 1)),
                dish_name=str(payload.item.get("dish_name", "")),
                qty=int(payload.item.get("qty", 1)),
                modifiers_json=payload.item.get("modifiers_json", {}),
            )
            repo.upsert_event_item(item)
        if payload.event_type == "purchase_paid":
            cache.invalidate_user(payload.user_id)
        return {"status": "ok", "event_uuid": payload.event_uuid}

    @app.post("/questionnaire/submit")
    def submit_questionnaire(payload: QuestionnaireSubmitRequest) -> dict[str, Any]:
        repo.upsert_json_entity(
            table="users",
            key_columns=["user_id"],
            row={"user_id": int(payload.user_id)},
        )
        repo.write_questionnaire_submission(
            {
                "user_id": payload.user_id,
                "questionnaire_type": payload.questionnaire_type,
                "raw_answers_json": payload.raw_answers_json,
                "extracted_json": payload.extracted_json,
            }
        )
        for row in payload.hard_constraints:
            repo.upsert_user_constraint(
                UserConstraint(
                    user_id=payload.user_id,
                    constraint_key=row["constraint_key"],
                    scope=row.get("scope", "hard"),
                    source=row.get("source", "api"),
                    reason_text=row.get("reason_text"),
                    confidence=row.get("confidence"),
                )
            )
        for row in payload.explicit_features:
            repo.upsert_user_feature(
                UserFeatureValue(
                    user_id=payload.user_id,
                    profile_layer="explicit",
                    axis=row["axis"],
                    feature_key=row["feature_key"],
                    weight=float(row["weight"]),
                    source=row.get("source", "api"),
                    confidence=row.get("confidence"),
                ),
                source_is_event=False,
            )
        cache.invalidate_user(payload.user_id)
        return {"status": "ok", "user_id": payload.user_id}

    @app.post("/profiles/rebuild")
    def rebuild_profiles_endpoint() -> dict[str, Any]:
        export_postgres_to_derived(derived, dsn=dsn)
        stats = rebuild_profiles(derived_dir=derived, taxonomy_path=VENDOR_TAXONOMY_PATH)
        import_derived_to_postgres(derived, dsn=dsn)
        cache.invalidate_all()
        return {"status": "ok", "users": stats.users, "time_is_synthetic": stats.time_is_synthetic}

    @app.get("/profiles/{user_id}")
    def get_profile(user_id: int) -> dict[str, Any]:
        rows = repo.fetch_all("user_profiles_cache", order_by="user_id")
        row = next((item for item in rows if int(item["user_id"]) == int(user_id)), None)
        if not row:
            raise HTTPException(status_code=404, detail="profile not found")
        profile = dict(row["cache_json"])
        if "cvp_profile" not in profile:
            profile["cvp_profile"] = build_cvp_profile(
                profile_cache_row=profile,
                constraint_rows=repo.fetch_all("user_constraints", order_by="user_id, constraint_key"),
            )
        return profile

    @app.post("/recommendations/score")
    def score_endpoint(payload: ScoreRequest) -> dict[str, Any]:
        with _score_lock:
            return _score_endpoint_inner(payload)

    def _score_endpoint_inner(payload: ScoreRequest) -> dict[str, Any]:
        cached = cache.get(payload.user_id)
        if cached is not None:
            return cached
        export_postgres_to_derived(derived, dsn=dsn)
        try:
            routed = route_recommendation(
                derived_dir=derived,
                user_id=payload.user_id,
                top_k=payload.top_k,
                request_context=payload.context,
                questionnaire_raw=payload.questionnaire_raw,
                explicit_mode=payload.mode,
            )
        except QuestionnaireNormalizationError as exc:
            raise HTTPException(status_code=400, detail={"message": str(exc), "mode": "questionnaire_only"}) from exc
        except QuestionnaireScoringNotReady as exc:
            raise HTTPException(status_code=501, detail={"message": exc.message, **exc.to_metadata()}) from exc
        except QuestionnaireNoSafeCandidates as exc:
            raise HTTPException(status_code=409, detail={"message": exc.message, **exc.to_metadata()}) from exc
        except ModeResolutionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        import_derived_to_postgres(derived, dsn=dsn)
        scores_path = derived / "recommendation_scores.jsonl"
        scores = []
        if scores_path.exists():
            scores = [
                json.loads(line)
                for line in scores_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        top = scores[: payload.top_k]
        request_id = routed.scoring_stats.request_id if routed.scoring_stats else ""
        recommendation_state_path = derived / "recommendation_state.json"
        recommendation_state = (
            json.loads(recommendation_state_path.read_text(encoding="utf-8"))
            if recommendation_state_path.exists()
            else {
                "request_id": request_id,
                "status": "empty" if not top else ("partial" if len(top) < int(payload.top_k) else "ok"),
                "backend_order_contract": "backend_order",
            }
        )
        appendix_path = derived / "questionnaire_menu_appendix_items.jsonl"
        appendix_items = []
        if appendix_path.exists() and str(request_id).startswith("qreq_"):
            appendix_items = [
                row
                for row in (
                    json.loads(line)
                    for line in appendix_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
                if str(row.get("request_id", "")) == str(request_id)
            ]
        result = {
            "request_id": request_id,
            "user_id": payload.user_id,
            "results": top,
            "food_recommendations": top,
            "menu_sections": {"food_recommendations": top, "appendix_items": appendix_items},
            "recommendation_state": recommendation_state,
            "mode": routed.mode_resolution.resolved_mode,
            "engine_selected": routed.mode_resolution.engine_selected,
            "mode_resolution_source": routed.mode_resolution.mode_resolution_source,
            "fallback_used": routed.mode_resolution.fallback_used,
        }
        cache.set(payload.user_id, result)
        return result

    @app.post("/recommendations/{request_id}/outcome")
    def outcome_endpoint(request_id: str, payload: OutcomeRequest) -> dict[str, Any]:
        questionnaire_outcome = None
        if str(request_id).startswith("qreq_"):
            questionnaire_outcome = log_questionnaire_outcome(
                derived_dir=derived,
                request_id=request_id,
                dish_id=payload.dish_id,
                outcome_type=payload.outcome,
                occurred_at=payload.occurred_at,
                user_id_or_session_id="",
                venue_normalized="",
            )
            build_questionnaire_ranking_dataset(derived)
            import_derived_to_postgres(derived, dsn=dsn)
            return {"status": "ok", "outcome": questionnaire_outcome, "questionnaire_outcome": questionnaire_outcome}
        row = log_recommendation_outcome(
            derived_dir=derived,
            request_id=request_id,
            dish_id=payload.dish_id,
            outcome_type=payload.outcome,
            occurred_at=payload.occurred_at,
            time_to_action_ms=payload.time_to_action_ms,
        )
        import_derived_to_postgres(derived, dsn=dsn)
        return {"status": "ok", "outcome": row, "questionnaire_outcome": questionnaire_outcome}

    @app.get("/recommendations/{request_id}")
    def recommendation_group(request_id: str) -> dict[str, Any]:
        requests = repo.fetch_all("recommendation_requests", order_by="recommendation_request_id")
        req = next((row for row in requests if row["recommendation_request_id"] == request_id), None)
        if req is None:
            raise HTTPException(status_code=404, detail="request not found")
        candidates = [
            row
            for row in repo.fetch_all("recommendation_candidates", order_by="recommendation_request_id, rank_position")
            if row["recommendation_request_id"] == request_id
        ]
        outcomes = [
            row
            for row in repo.fetch_all("recommendation_outcomes", order_by="recommendation_request_id, occurred_at")
            if row["recommendation_request_id"] == request_id
        ]
        return {"request": req, "candidates": candidates, "outcomes": outcomes}

    @app.post("/ranking/build-dataset")
    def ranking_dataset_endpoint() -> dict[str, Any]:
        export_postgres_to_derived(derived, dsn=dsn)
        stats = build_ranking_dataset(derived_dir=derived)
        import_derived_to_postgres(derived, dsn=dsn)
        return {"status": "ok", **stats}

    return app
