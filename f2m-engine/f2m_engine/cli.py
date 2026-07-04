from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from f2m_engine.api import create_app
from f2m_engine.config.taxonomy import DEFAULT_TAXONOMY_PATH, load_runtime_taxonomy
from f2m_engine.pipelines.dish_features_stage_a import build_dish_features_stage_a
from f2m_engine.pipelines.profile_rebuild import rebuild_profiles, show_profile
from f2m_engine.pipelines.questionnaire_audit import run_questionnaire_audit
from f2m_engine.pipelines.questionnaire_engine import QuestionnaireNoSafeCandidates, QuestionnaireScoringNotReady
from f2m_engine.pipelines.questionnaire_logging import build_questionnaire_ranking_dataset, log_questionnaire_outcome
from f2m_engine.pipelines.questionnaire_normalizer import QuestionnaireNormalizationError
from f2m_engine.pipelines.questionnaire_seed import run_seed_questionnaire_extraction
from f2m_engine.pipelines.recommend_router import ModeResolutionError, route_recommendation
from f2m_engine.pipelines.recommendation_dataset import (
    build_ranking_dataset,
    log_recommendation_outcome,
    show_ranking_group,
)
from f2m_engine.pipelines.real_purchase_recommender import (
    backtest_real,
    build_real_user_profiles,
    ingest_real_orders,
    inspect_real_inputs,
    recommend_real,
)
from f2m_engine.pipelines.coffeemania_scoring import run_coffeemania_primary_scoring
from f2m_engine.pipelines.scoring_deterministic import explain_dish_for_user
from f2m_engine.pipelines.seed_events import ingest_seed_purchase_events
from f2m_engine.pipelines.tag_audit import audit_menu_tags
from f2m_engine.pipelines.txt_data_layer import build_text_data_layer
from f2m_engine.repositories.file_repository import FileRepository
from f2m_engine.services.api_smoke import run_api_smoke, run_ingest_idempotency_check, write_smoke_reports
from f2m_engine.services.repository_sync import (
    apply_postgres_migrations,
    export_postgres_to_derived,
    import_derived_to_postgres,
    postgres_row_counts,
    verify_repository_equivalence,
    write_csv_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="food2mood")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_questionnaire = subparsers.add_parser("extract-questionnaire")
    extract_questionnaire.add_argument("--users", required=True, help="Path to cust.json")
    extract_questionnaire.add_argument(
        "--out",
        default="data/derived",
        help="Output folder for derived jsonl files",
    )
    extract_questionnaire.add_argument(
        "--taxonomy",
        default=str(DEFAULT_TAXONOMY_PATH),
        help="Path to runtime taxonomy lock file",
    )

    ingest_events = subparsers.add_parser("ingest-events")
    ingest_events.add_argument("--users", required=True, help="Path to cust.json")
    ingest_events.add_argument(
        "--out",
        default="data/derived",
        help="Output folder for derived jsonl files",
    )

    audit_questionnaire = subparsers.add_parser("audit-questionnaire")
    audit_questionnaire.add_argument("--users", required=True, help="Path to cust.json")
    audit_questionnaire.add_argument(
        "--derived",
        default="data/derived",
        help="Derived data folder with jsonl outputs",
    )

    build_dish_features = subparsers.add_parser("build-dish-features")
    build_dish_features.add_argument("--menu", required=True, help="Path to menu_export.xlsx")
    build_dish_features.add_argument(
        "--sostav",
        default="",
        help="Optional path to Состав.xlsx for PLU-based ingredient enrichment",
    )
    build_dish_features.add_argument(
        "--out",
        default="data/derived",
        help="Output folder for dish features artifacts",
    )
    build_dish_features.add_argument(
        "--taxonomy",
        default=str(DEFAULT_TAXONOMY_PATH),
        help="Path to runtime taxonomy lock file",
    )

    rebuild_profiles_cmd = subparsers.add_parser("rebuild-profiles")
    rebuild_profiles_cmd.add_argument(
        "--derived",
        default="data/derived",
        help="Derived data folder",
    )
    rebuild_profiles_cmd.add_argument(
        "--taxonomy",
        default=str(DEFAULT_TAXONOMY_PATH),
        help="Path to runtime taxonomy lock file",
    )

    show_profile_cmd = subparsers.add_parser("show-profile")
    show_profile_cmd.add_argument("--user-id", required=True, type=int, help="User id")
    show_profile_cmd.add_argument(
        "--derived",
        default="data/derived",
        help="Derived data folder",
    )

    audit_tags_cmd = subparsers.add_parser("audit-tags")
    audit_tags_cmd.add_argument("--derived", default="data/derived", help="Derived data folder")
    audit_tags_cmd.add_argument(
        "--taxonomy",
        default=str(DEFAULT_TAXONOMY_PATH),
        help="Path to runtime taxonomy lock file",
    )

    score_dishes_cmd = subparsers.add_parser("score-dishes")
    score_dishes_cmd.add_argument("--user-id", required=True, type=int, help="User id")
    score_dishes_cmd.add_argument("--top-k", default=10, type=int, help="Top K to export")
    score_dishes_cmd.add_argument("--derived", default="data/derived", help="Derived data folder")
    score_dishes_cmd.add_argument("--time-of-day", default="", help="Optional context: morning/lunch/evening/night")
    score_dishes_cmd.add_argument("--hunger-level", default="", help="Optional context: snack/quick/hearty")
    score_dishes_cmd.add_argument("--venue", default="", help="Optional context: venue/store id (e.g. gc)")
    score_dishes_cmd.add_argument("--venue-type", default="", help="Optional context: home/office/dine_in")
    score_dishes_cmd.add_argument("--situation", default="", help="Optional free-text situation")
    score_dishes_cmd.add_argument(
        "--mode",
        default="",
        help="Recommendation mode: questionnaire_only|orders_only|auto (optional; env default applies when empty)",
    )
    score_dishes_cmd.add_argument(
        "--questionnaire-json",
        default="",
        help="Questionnaire raw input as inline JSON or path to .json file (used by questionnaire_only mode).",
    )

    explain_dish_cmd = subparsers.add_parser("explain-dish")
    explain_dish_cmd.add_argument("--user-id", required=True, type=int, help="User id")
    explain_dish_cmd.add_argument("--dish-id", required=True, help="Dish id")
    explain_dish_cmd.add_argument("--derived", default="data/derived", help="Derived data folder")
    explain_dish_cmd.add_argument("--time-of-day", default="", help="Optional context: morning/lunch/evening/night")
    explain_dish_cmd.add_argument("--hunger-level", default="", help="Optional context: snack/quick/hearty")
    explain_dish_cmd.add_argument("--venue-type", default="", help="Optional context: home/office/dine_in")
    explain_dish_cmd.add_argument("--situation", default="", help="Optional free-text situation")

    log_recommendation_cmd = subparsers.add_parser("log-recommendation")
    log_recommendation_cmd.add_argument("--request-id", required=True, help="Recommendation request id")
    log_recommendation_cmd.add_argument("--dish-id", required=True, help="Dish id")
    log_recommendation_cmd.add_argument(
        "--outcome",
        required=True,
        choices=[
            "shown",
            "opened",
            "clicked",
            "viewed_details",
            "added_to_cart",
            "removed_from_cart",
            "purchased",
            "dismissed",
            "expired",
        ],
        help="Outcome type",
    )
    log_recommendation_cmd.add_argument("--derived", default="data/derived", help="Derived data folder")
    log_recommendation_cmd.add_argument("--occurred-at", default="", help="Optional occurred_at ISO timestamp")
    log_recommendation_cmd.add_argument("--time-to-action-ms", default=-1, type=int, help="Optional latency in ms")

    build_ranking_dataset_cmd = subparsers.add_parser("build-ranking-dataset")
    build_ranking_dataset_cmd.add_argument("--derived", default="data/derived", help="Derived data folder")

    show_ranking_group_cmd = subparsers.add_parser("show-ranking-group")
    show_ranking_group_cmd.add_argument("--request-id", required=True, help="Recommendation request id")
    show_ranking_group_cmd.add_argument("--derived", default="data/derived", help="Derived data folder")

    migrate_pg_cmd = subparsers.add_parser("migrate-postgres")
    migrate_pg_cmd.add_argument("--dsn", required=True, help="Postgres DSN")
    migrate_pg_cmd.add_argument("--workspace", default=".", help="Workspace root path")

    import_pg_cmd = subparsers.add_parser("import-derived-to-postgres")
    import_pg_cmd.add_argument("--derived", default="data/derived", help="Derived data folder")
    import_pg_cmd.add_argument("--dsn", required=True, help="Postgres DSN")

    export_pg_cmd = subparsers.add_parser("export-postgres-to-derived")
    export_pg_cmd.add_argument("--derived", default="data/derived", help="Derived data folder")
    export_pg_cmd.add_argument("--dsn", required=True, help="Postgres DSN")

    verify_repo_cmd = subparsers.add_parser("verify-repository-equivalence")
    verify_repo_cmd.add_argument("--derived", default="data/derived", help="Derived data folder")
    verify_repo_cmd.add_argument("--dsn", required=True, help="Postgres DSN")

    serve_api_cmd = subparsers.add_parser("serve-api")
    serve_api_cmd.add_argument("--dsn", required=True, help="Postgres DSN")
    serve_api_cmd.add_argument("--derived", default="data/derived", help="Derived data folder")
    serve_api_cmd.add_argument("--host", default="127.0.0.1", help="Host")
    serve_api_cmd.add_argument("--port", default=8000, type=int, help="Port")

    txt_layer_cmd = subparsers.add_parser("build-text-data-layer")
    txt_layer_cmd.add_argument("--input-dir", default="data/menu files", help="Directory with txt sources")
    txt_layer_cmd.add_argument("--out", default="data/derived", help="Derived output directory")

    inspect_real_cmd = subparsers.add_parser("inspect-real-inputs")
    inspect_real_cmd.add_argument("--guest-cards", default="data/guest_card.xlsx", help="Path to guest cards xlsx")
    inspect_real_cmd.add_argument("--orders", default="data/restaurant_parsed_data (8).csv", help="Path to orders csv")
    inspect_real_cmd.add_argument("--out", default="data/derived_real", help="Output folder")

    ingest_real_cmd = subparsers.add_parser("ingest-real-orders")
    ingest_real_cmd.add_argument("--guest-cards", default="data/guest_card.xlsx", help="Path to guest cards xlsx")
    ingest_real_cmd.add_argument("--orders", default="data/restaurant_parsed_data (8).csv", help="Path to orders csv")
    ingest_real_cmd.add_argument("--menu-derived", default="data/derived", help="Menu derived folder")
    ingest_real_cmd.add_argument("--out", default="data/derived_real", help="Output folder")

    build_real_profiles_cmd = subparsers.add_parser("build-real-user-profiles")
    build_real_profiles_cmd.add_argument("--derived", default="data/derived_real", help="Derived real folder")
    build_real_profiles_cmd.add_argument("--out", default="data/derived_real", help="Output folder")

    recommend_real_cmd = subparsers.add_parser("recommend-real")
    recommend_real_cmd.add_argument("--derived", default="data/derived_real", help="Derived real folder")
    recommend_real_cmd.add_argument("--user-id", required=True, help="User id")
    recommend_real_cmd.add_argument("--venue", required=True, help="Venue")
    recommend_real_cmd.add_argument("--top-k", default=10, type=int, help="Top K")

    backtest_real_cmd = subparsers.add_parser("backtest-real")
    backtest_real_cmd.add_argument("--derived", default="data/derived_real", help="Derived real folder")
    backtest_real_cmd.add_argument("--top-k", default=10, type=int, help="Top K")
    backtest_real_cmd.add_argument("--min-orders", default=3, type=int, help="Min orders for user")

    score_coffeemania_cmd = subparsers.add_parser("score-coffeemania")
    score_coffeemania_cmd.add_argument("--sales", required=True, help="Path to Coffeemania sales csv/zip")
    score_coffeemania_cmd.add_argument("--dishes", required=True, help="Path to dishes.json")
    score_coffeemania_cmd.add_argument("--modifiers", required=True, help="Path to modifiers.json")
    score_coffeemania_cmd.add_argument("--restrictions", required=True, help="Path to restrictions.json")
    score_coffeemania_cmd.add_argument("--out", default="data/derived_coffeemania", help="Output folder")
    score_coffeemania_cmd.add_argument(
        "--taxonomy",
        default=str(DEFAULT_TAXONOMY_PATH),
        help="Path to runtime taxonomy lock file",
    )
    score_coffeemania_cmd.add_argument("--top-k", default=20, type=int, help="Top K per user")
    score_coffeemania_cmd.add_argument(
        "--min-backtest-orders",
        default=3,
        type=int,
        help="Min orders for temporal backtest",
    )
    score_coffeemania_cmd.add_argument(
        "--max-backtest-users",
        default=5000,
        type=int,
        help="Max users for primary temporal backtest; 0 means all",
    )
    score_coffeemania_cmd.add_argument(
        "--skip-existing-recommendations",
        action="store_true",
        help="Reuse an existing recommendations export when rerunning audit/backtest",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "extract-questionnaire":
        taxonomy = load_runtime_taxonomy(Path(args.taxonomy))
        repository = FileRepository(base_dir=Path(args.out))
        stats = run_seed_questionnaire_extraction(
            users_path=Path(args.users),
            repository=repository,
            taxonomy=taxonomy,
        )
        print(
            "extract-questionnaire completed:",
            f"users={stats.users_processed}",
            f"constraints={stats.constraints_written}",
            f"features={stats.features_written}",
        )
        return

    if args.command == "ingest-events":
        repository = FileRepository(base_dir=Path(args.out))
        stats = ingest_seed_purchase_events(
            users_path=Path(args.users),
            repository=repository,
        )
        print(
            "ingest-events completed:",
            f"users={stats.users_processed}",
            f"events={stats.events_written}",
            f"items={stats.items_written}",
        )
        return

    if args.command == "audit-questionnaire":
        stats = run_questionnaire_audit(
            source_users_path=Path(args.users),
            derived_dir=Path(args.derived),
        )
        print(
            "audit-questionnaire completed:",
            f"hard_constraints={stats.hard_constraints_total}",
            f"soft_features={stats.soft_features_total}",
            f"unmapped_phrases={stats.unmapped_phrases_total}",
            f"events={stats.events_total}",
        )
        return

    if args.command == "build-dish-features":
        taxonomy = load_runtime_taxonomy(Path(args.taxonomy))
        stats = build_dish_features_stage_a(
            menu_path=Path(args.menu),
            output_dir=Path(args.out),
            taxonomy=taxonomy,
            sostav_path=Path(args.sostav) if args.sostav else None,
        )
        print(
            "build-dish-features completed:",
            f"parsed_rows={stats.parsed_rows}",
            f"dishes={stats.dishes_processed}",
            f"skipped_rows={stats.skipped_rows}",
            f"skipped_by_reason={stats.skipped_by_reason}",
            f"unique_dish_ids={stats.unique_dish_ids}",
            f"nutrition_parse_success_rate={stats.nutrition_parse_success_rate}",
            f"feature_rows={stats.feature_rows_written}",
            f"cache_rows={stats.cache_rows_written}",
        )
        return

    if args.command == "rebuild-profiles":
        stats = rebuild_profiles(
            derived_dir=Path(args.derived),
            taxonomy_path=Path(args.taxonomy),
        )
        print(
            "rebuild-profiles completed:",
            f"users={stats.users}",
            f"feature_rows={stats.feature_rows}",
            f"cache_rows={stats.cache_rows}",
            f"time_is_synthetic={stats.time_is_synthetic}",
        )
        return

    if args.command == "show-profile":
        print(show_profile(derived_dir=Path(args.derived), user_id=int(args.user_id)))
        return

    if args.command == "audit-tags":
        stats = audit_menu_tags(
            derived_dir=Path(args.derived),
            taxonomy_path=Path(args.taxonomy),
        )
        print(
            "audit-tags completed:",
            f"dishes={stats.dishes}",
            f"missing_label_rows={stats.missing_label_rows}",
            f"anomaly_rows={stats.anomaly_rows}",
            f"questionable_dishes={stats.questionable_dishes}",
            f"questionable_tag_rows={stats.questionable_tag_rows}",
        )
        return

    if args.command == "score-dishes":
        try:
            questionnaire_raw = _parse_questionnaire_json_arg(str(args.questionnaire_json))
            routed = route_recommendation(
                derived_dir=Path(args.derived),
                user_id=int(args.user_id),
                top_k=int(args.top_k),
                request_context={
                    "time_of_day": args.time_of_day,
                    "hunger_level": args.hunger_level,
                    "venue": args.venue,
                    "venue_type": args.venue_type,
                    "situation": args.situation,
                },
                questionnaire_raw=questionnaire_raw,
                explicit_mode=(str(args.mode).strip() or None),
            )
        except QuestionnaireNormalizationError as exc:
            raise ValueError(f"QuestionnaireNormalizationError: {exc}") from exc
        except QuestionnaireNoSafeCandidates as exc:
            raise ValueError(f"{exc.message} metadata={exc.to_metadata()}") from exc
        except QuestionnaireScoringNotReady as exc:
            raise ValueError(f"{exc.message} metadata={exc.to_metadata()}") from exc
        except ModeResolutionError as exc:
            raise ValueError(f"Invalid mode configuration: {exc}") from exc
        stats = routed.scoring_stats
        if stats is None:
            raise ValueError("Router returned no scoring stats for order-based path.")
        print(
            "score-dishes completed:",
            f"user_id={stats.user_id}",
            f"request_id={stats.request_id}",
            f"survivors={stats.survivors}",
            f"excluded={stats.excluded}",
            f"top_k={stats.top_k}",
            f"status={stats.status}",
            f"mode={routed.mode_resolution.resolved_mode}",
            f"engine_selected={routed.mode_resolution.engine_selected}",
            f"mode_resolution_source={routed.mode_resolution.mode_resolution_source}",
            f"fallback_used={routed.mode_resolution.fallback_used}",
        )
        return

    if args.command == "explain-dish":
        print(
            explain_dish_for_user(
                derived_dir=Path(args.derived),
                user_id=int(args.user_id),
                dish_id=str(args.dish_id),
                request_context={
                    "time_of_day": args.time_of_day,
                    "hunger_level": args.hunger_level,
                    "venue_type": args.venue_type,
                    "situation": args.situation,
                },
            )
        )
        return

    if args.command == "log-recommendation":
        if str(args.request_id).startswith("qreq_"):
            row = log_questionnaire_outcome(
                derived_dir=Path(args.derived),
                request_id=str(args.request_id),
                dish_id=str(args.dish_id),
                outcome_type=str(args.outcome),
                occurred_at=(str(args.occurred_at) if str(args.occurred_at) else None),
                user_id_or_session_id="",
                venue_normalized="",
            )
            build_questionnaire_ranking_dataset(Path(args.derived))
            print(
                "log-recommendation completed:",
                f"request_id={row['request_id']}",
                f"dish_id={row['dish_id']}",
                f"outcome={row['outcome_type']}",
            )
            return
        row = log_recommendation_outcome(
            derived_dir=Path(args.derived),
            request_id=str(args.request_id),
            dish_id=str(args.dish_id),
            outcome_type=str(args.outcome),
            occurred_at=(str(args.occurred_at) if str(args.occurred_at) else None),
            time_to_action_ms=(int(args.time_to_action_ms) if int(args.time_to_action_ms) >= 0 else None),
        )
        print(
            "log-recommendation completed:",
            f"request_id={row['recommendation_request_id']}",
            f"dish_id={row['dish_id']}",
            f"outcome={row['outcome_type']}",
        )
        return

    if args.command == "build-ranking-dataset":
        stats = build_ranking_dataset(derived_dir=Path(args.derived))
        print(
            "build-ranking-dataset completed:",
            f"requests={stats['requests']}",
            f"candidates={stats['candidates']}",
            f"dataset_rows={stats['dataset_rows']}",
            f"pairwise_rows={stats['pairwise_rows']}",
        )
        return

    if args.command == "show-ranking-group":
        print(
            show_ranking_group(
                derived_dir=Path(args.derived),
                request_id=str(args.request_id),
            )
        )
        return

    if args.command == "migrate-postgres":
        apply_postgres_migrations(dsn=str(args.dsn), workspace_root=Path(args.workspace))
        print("migrate-postgres completed")
        return

    if args.command == "import-derived-to-postgres":
        stats = import_derived_to_postgres(derived_dir=Path(args.derived), dsn=str(args.dsn))
        counts = postgres_row_counts(dsn=str(args.dsn))
        write_csv_report(Path(args.derived) / "audit" / "postgres_row_counts.csv", counts)
        idem_rows = run_ingest_idempotency_check(dsn=str(args.dsn))
        write_csv_report(Path(args.derived) / "audit" / "ingest_idempotency_report.csv", idem_rows)
        print("import-derived-to-postgres completed:", stats)
        return

    if args.command == "export-postgres-to-derived":
        stats = export_postgres_to_derived(derived_dir=Path(args.derived), dsn=str(args.dsn))
        counts = postgres_row_counts(dsn=str(args.dsn))
        write_csv_report(Path(args.derived) / "audit" / "postgres_row_counts.csv", counts)
        print("export-postgres-to-derived completed:", stats)
        return

    if args.command == "verify-repository-equivalence":
        report = verify_repository_equivalence(derived_dir=Path(args.derived), dsn=str(args.dsn))
        write_csv_report(Path(args.derived) / "audit" / "repository_equivalence_report.csv", report)
        api_rows = run_api_smoke(dsn=str(args.dsn), derived_dir=Path(args.derived))
        idem_rows = run_ingest_idempotency_check(dsn=str(args.dsn))
        write_smoke_reports(Path(args.derived), api_rows=api_rows, idem_rows=idem_rows)
        print("verify-repository-equivalence completed:", len(report), "rows")
        return

    if args.command == "serve-api":
        app = create_app(dsn=str(args.dsn), derived_dir=str(args.derived))
        uvicorn.run(app, host=str(args.host), port=int(args.port))
        return

    if args.command == "build-text-data-layer":
        stats = build_text_data_layer(input_dir=Path(args.input_dir), output_dir=Path(args.out))
        print(
            "build-text-data-layer completed:",
            f"menu_sources={stats.menu_sources}",
            f"sellable_dishes={stats.sellable_dishes}",
            f"semi_finished_nodes={stats.semi_finished_nodes}",
            f"canonical_ingredients={stats.canonical_ingredients}",
            f"item_match_coverage={stats.item_match_coverage}",
            f"users_with_profiles={stats.users_with_profiles}",
        )
        return

    if args.command == "inspect-real-inputs":
        guest_cards = Path(args.guest_cards)
        if not guest_cards.exists():
            alt = Path("data/guests_card.xlsx")
            if alt.exists():
                guest_cards = alt
        stats = inspect_real_inputs(
            guest_cards=guest_cards,
            orders=Path(args.orders),
            out=Path(args.out),
        )
        print(
            "inspect-real-inputs completed:",
            f"guest_rows={stats.guest_rows}",
            f"order_rows={stats.order_rows}",
            f"linkage_candidates={stats.linkage_candidates}",
        )
        return

    if args.command == "ingest-real-orders":
        guest_cards = Path(args.guest_cards)
        if not guest_cards.exists():
            alt = Path("data/guests_card.xlsx")
            if alt.exists():
                guest_cards = alt
        stats = ingest_real_orders(
            guest_cards=guest_cards,
            orders=Path(args.orders),
            menu_derived=Path(args.menu_derived),
            out=Path(args.out),
        )
        print(
            "ingest-real-orders completed:",
            f"users_total={stats.users_total}",
            f"orders_total={stats.orders_total}",
            f"linked_orders_count={stats.linked_orders_count}",
            f"order_linkage_coverage={stats.order_linkage_coverage}",
            f"food_items_total={stats.food_items_total}",
            f"matched_food_items_count={stats.matched_food_items_count}",
            f"purchase_events_total={stats.purchase_events_total}",
        )
        return

    if args.command == "build-real-user-profiles":
        stats = build_real_user_profiles(derived=Path(args.derived), out=Path(args.out))
        print(
            "build-real-user-profiles completed:",
            f"users={stats.users}",
            f"feature_rows={stats.feature_rows}",
        )
        return

    if args.command == "recommend-real":
        stats = recommend_real(
            derived=Path(args.derived),
            user_id=str(args.user_id),
            venue=str(args.venue),
            top_k=int(args.top_k),
        )
        print(
            "recommend-real completed:",
            f"user_id={stats.user_id}",
            f"candidates={stats.candidates}",
            f"top_k={stats.top_k}",
        )
        return

    if args.command == "backtest-real":
        stats = backtest_real(
            derived=Path(args.derived),
            top_k=int(args.top_k),
            min_orders=int(args.min_orders),
        )
        print(
            "backtest-real completed:",
            f"users_in_backtest={stats.users_in_backtest}",
            f"hit_at_5={stats.hit_at_5}",
            f"hit_at_10={stats.hit_at_10}",
            f"recall_at_10={stats.recall_at_10}",
            f"mrr={stats.mrr}",
        )
        return

    if args.command == "score-coffeemania":
        stats = run_coffeemania_primary_scoring(
            sales=Path(args.sales),
            dishes=Path(args.dishes),
            modifiers=Path(args.modifiers),
            restrictions=Path(args.restrictions),
            out=Path(args.out),
            taxonomy=Path(args.taxonomy),
            top_k=int(args.top_k),
            min_backtest_orders=int(args.min_backtest_orders),
            max_backtest_users=int(args.max_backtest_users),
            skip_existing_recommendations=bool(args.skip_existing_recommendations),
        )
        print(
            "score-coffeemania completed:",
            f"dishes_total={stats.dishes_total}",
            f"sales_rows={stats.sales_rows}",
            f"distinct_order_items={stats.distinct_order_items}",
            f"success_purchase_events={stats.success_purchase_events}",
            f"profiles={stats.profiles}",
            f"candidates={stats.candidates}",
            f"recommendations={stats.recommendations}",
            f"hit_at_10={stats.hit_at_10}",
            f"mrr={stats.mrr}",
            f"output_dir={stats.output_dir}",
        )
        return

    raise ValueError(f"Unsupported command: {args.command}")


def _parse_questionnaire_json_arg(raw_value: str) -> dict | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    path = Path(value)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


if __name__ == "__main__":
    main()
