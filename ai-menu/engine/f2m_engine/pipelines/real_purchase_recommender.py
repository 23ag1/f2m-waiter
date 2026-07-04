from __future__ import annotations

import ast
import csv
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


DRINK_KEYWORDS = (
    "кофе",
    "чай",
    "ром",
    "коктейл",
    "пиво",
    "mojito",
    "daiquiri",
    "margarita",
    "cappuccino",
    "americano",
    "вино",
    "виски",
    "водка",
    "джин",
    "лимонад",
    "сок",
    "морс",
    "вода",
    "espresso",
    "latte",
)
SERVICE_KEYWORDS = ("комплимент", "доставка", "сервис", "чаевые", "упаковка")


@dataclass(frozen=True)
class InspectStats:
    guest_rows: int
    order_rows: int
    linkage_candidates: int


@dataclass(frozen=True)
class IngestStats:
    users_total: int
    orders_total: int
    food_items_total: int
    matched_food_items_count: int
    purchase_events_total: int
    linked_orders_count: int
    order_linkage_coverage: float


@dataclass(frozen=True)
class ProfileStats:
    users: int
    feature_rows: int


@dataclass(frozen=True)
class RecommendationStats:
    user_id: str
    candidates: int
    top_k: int


@dataclass(frozen=True)
class BacktestStats:
    users_in_backtest: int
    hit_at_5: float
    hit_at_10: float
    recall_at_10: float
    mrr: float


def inspect_real_inputs(guest_cards: Path | str, orders: Path | str, out: Path | str) -> InspectStats:
    guest_path = Path(guest_cards)
    orders_path = Path(orders)
    out_path = Path(out)
    audit_dir = out_path / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    guest_rows = _read_guest_card_rows(guest_path)
    for row in guest_rows:
        row["canonical_user_id"] = _canonical_user_id(row.get("Id клиента"))
        row["venue_normalized"] = _normalize_venue(row.get("Заведение"))
    order_rows = _read_orders_rows(orders_path)
    guest_columns = list(guest_rows[0].keys()) if guest_rows else []
    order_columns = list(order_rows[0].keys()) if order_rows else []

    schema_lines = [
        "# Input Schema Report",
        "",
        "## Files",
        f"- guest_cards: `{guest_path}`",
        f"- orders: `{orders_path}`",
        "",
        "## Guest card columns",
    ]
    for col in guest_columns:
        dtype = _infer_dtype([row.get(col, "") for row in guest_rows])
        schema_lines.append(f"- `{col}`: {dtype}")
    schema_lines += ["", "## Orders columns"]
    for col in order_columns:
        dtype = _infer_dtype([row.get(col, "") for row in order_rows])
        schema_lines.append(f"- `{col}`: {dtype}")

    schema_lines += [
        "",
        "## Identity and linkage",
        "- user identity: `Id клиента` (fallback: normalized `Телефон` hash)",
        "- order identity: `Номер заказа` in both files",
        "- datetime: `Время визита` (guest), `Дата` + `Время` (orders)",
        "- venue: `Заведение` (guest), unavailable directly in orders",
        "- item list: `Список блюд` in orders",
        "- checks/financials: `Сумма чека`, `Оплачено`, discounts and bonus fields in guest cards",
        "- linkage usable now: exact `Номер заказа` match; unmatched rows explicitly reported",
    ]
    (out_path / "input_schema_report.md").write_text("\n".join(schema_lines), encoding="utf-8")

    mapping_rows = [
        {"source_file": "guest_cards", "column_name": "Id клиента", "mapped_to": "user_id", "confidence": 1.0, "notes": "primary user key"},
        {"source_file": "guest_cards", "column_name": "Телефон", "mapped_to": "phone_normalized", "confidence": 0.9, "notes": "fallback identity"},
        {"source_file": "guest_cards", "column_name": "Номер заказа", "mapped_to": "order_id", "confidence": 1.0, "notes": "join key to orders"},
        {"source_file": "guest_cards", "column_name": "Время визита", "mapped_to": "visit_datetime", "confidence": 0.9, "notes": "datetime"},
        {"source_file": "guest_cards", "column_name": "Заведение", "mapped_to": "venue", "confidence": 0.8, "notes": "venue context"},
        {"source_file": "orders", "column_name": "Номер заказа", "mapped_to": "order_id", "confidence": 1.0, "notes": "primary order key"},
        {"source_file": "orders", "column_name": "Дата", "mapped_to": "order_date", "confidence": 1.0, "notes": "date"},
        {"source_file": "orders", "column_name": "Время", "mapped_to": "order_time", "confidence": 1.0, "notes": "time"},
        {"source_file": "orders", "column_name": "Список блюд", "mapped_to": "order_items_raw", "confidence": 1.0, "notes": "list payload"},
        {"source_file": "orders", "column_name": "Число гостей", "mapped_to": "guest_count", "confidence": 0.9, "notes": "auxiliary"},
    ]
    _write_csv(out_path / "input_column_mapping.csv", mapping_rows)
    _write_csv(audit_dir / "input_samples_guest_card.csv", guest_rows[:80])
    _write_csv(audit_dir / "input_samples_orders.csv", order_rows[:80])

    order_ids = {str(row.get("Номер заказа", "")).strip() for row in order_rows}
    linkage_candidates = len([row for row in guest_rows if str(row.get("Номер заказа", "")).strip() in order_ids])
    return InspectStats(guest_rows=len(guest_rows), order_rows=len(order_rows), linkage_candidates=linkage_candidates)


def ingest_real_orders(
    guest_cards: Path | str,
    orders: Path | str,
    menu_derived: Path | str,
    out: Path | str,
) -> IngestStats:
    out_path = Path(out)
    audit_dir = out_path / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    menu_path = Path(menu_derived)
    before_snapshot = _collect_pipeline_metric_snapshot(out_path)
    _write_json(audit_dir / "linkage_before_snapshot.json", before_snapshot)

    guest_rows = _read_guest_card_rows(Path(guest_cards))
    orders_rows = _read_orders_rows(Path(orders))

    real_users = _normalize_real_users(guest_rows)
    real_headers, real_items = _normalize_real_orders(orders_rows)
    _write_csv(out_path / "real_user_identity.csv", real_users)
    _write_csv(out_path / "real_order_headers.csv", real_headers)
    _write_csv(out_path / "real_order_item_raw.csv", real_items)

    menu_nodes = _read_csv_rows(menu_path / "menu_nodes.csv")
    dish_features = _read_csv_rows(menu_path / "dish_feature_values.csv")
    _write_csv(out_path / "real_menu_nodes.csv", menu_nodes)
    _write_csv(out_path / "real_dish_feature_values.csv", dish_features)
    menu_corrections = _read_csv_rows(menu_path / "audit" / "menu_node_type_corrections.csv")
    if menu_corrections:
        _write_csv(audit_dir / "menu_node_type_corrections.csv", menu_corrections)

    curated = _load_top50_curated_hardening(out_path / "manual_curation", menu_nodes)
    real_items, hardening_applied, affected_food_before, affected_food_after = _apply_curated_reclassifications(
        real_items,
        curated,
    )

    links, linkage_quality, linkage_audits = _link_orders_users(real_users, real_headers)
    _write_csv(out_path / "real_order_user_link.csv", links)
    _write_csv(audit_dir / "linkage_quality.csv", linkage_quality)
    _write_csv(audit_dir / "linkage_method_breakdown.csv", linkage_audits["method_breakdown"])
    _write_csv(audit_dir / "linkage_conflict_cases.csv", linkage_audits["conflict_cases"])
    _write_csv(audit_dir / "low_confidence_links.csv", linkage_audits["low_confidence_links"])
    _write_csv(audit_dir / "unlinked_orders_top_reasons.csv", linkage_audits["unlinked_reasons"])
    _write_csv(audit_dir / "user_id_normalization_report.csv", _user_id_normalization_report(real_users, links, real_items))
    _write_csv(audit_dir / "venue_normalization_report.csv", _venue_normalization_report(real_users, menu_nodes))

    dish_lookup = _build_dish_lookup_for_real(menu_nodes)
    item_match, match_summary, unmatched, match_hardening_rows = _match_real_order_items(real_items, dish_lookup, curated)
    hardening_applied.extend(match_hardening_rows)
    _write_csv(out_path / "real_order_item_match.csv", item_match)
    _write_csv(audit_dir / "item_match_summary.csv", match_summary)
    _write_csv(audit_dir / "high_freq_unmatched_items.csv", _high_freq_unmatched(unmatched))
    _write_csv(audit_dir / "top_matched_food_items.csv", _top_matched_food(item_match))
    _write_csv(audit_dir / "item_match_review_queue.csv", [row for row in item_match if row.get("review_required")])
    _write_csv(audit_dir / "top50_hardening_applied.csv", hardening_applied)
    _write_csv(
        audit_dir / "top50_hardening_summary.csv",
        _top50_hardening_summary(
            curated=curated,
            hardening_applied=hardening_applied,
            affected_food_before=affected_food_before,
            affected_food_after=affected_food_after,
        ),
    )

    purchase_events = _build_real_purchase_events(real_headers, links, item_match, dish_lookup)
    _write_csv(out_path / "real_purchase_events.csv", purchase_events)
    _write_csv(audit_dir / "drink_service_leakage_real.csv", _drink_service_leakage_real(item_match, purchase_events, dish_lookup))
    _write_metric_definitions_report(audit_dir / "metric_definitions_report.md")

    orders_total = len(real_headers)
    linked_orders_count = len([row for row in links if row.get("user_id")])
    food_items_total = len([row for row in item_match if row["item_type"] == "food"])
    matched_food_items_count = len([row for row in item_match if row["item_type"] == "food" and row["matched_dish_id"]])
    purchase_events_total = len(purchase_events)
    linked_purchase_events_count = len([row for row in purchase_events if row.get("user_id")])
    users_with_profiles = _count_users_with_profiles(out_path)
    users_in_backtest = _read_single_metric(out_path / "backtest_summary.csv", "users_in_backtest")
    _write_csv(
        audit_dir / "linkage_metric_breakdown.csv",
        _build_linkage_metric_breakdown(
            orders_total=orders_total,
            linked_orders_count=linked_orders_count,
            food_items_total=food_items_total,
            matched_food_items_count=matched_food_items_count,
            purchase_events_total=purchase_events_total,
            linked_purchase_events_count=linked_purchase_events_count,
            users_total=len({row["user_id"] for row in real_users if row.get("user_id")}),
            users_with_profiles=users_with_profiles,
            users_in_backtest=users_in_backtest,
        ),
    )

    order_linkage_coverage = round(linked_orders_count / max(1, orders_total), 6)
    return IngestStats(
        users_total=len({row["user_id"] for row in real_users if row.get("user_id")}),
        orders_total=orders_total,
        food_items_total=food_items_total,
        matched_food_items_count=matched_food_items_count,
        purchase_events_total=purchase_events_total,
        linked_orders_count=linked_orders_count,
        order_linkage_coverage=order_linkage_coverage,
    )


def build_real_user_profiles(derived: Path | str, out: Path | str) -> ProfileStats:
    derived_path = Path(derived)
    out_path = Path(out)
    audit_dir = out_path / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    purchase_events = _normalize_purchase_events_for_profile(_read_csv_rows(derived_path / "real_purchase_events.csv"))
    dish_features = _read_csv_rows(derived_path / "real_dish_feature_values.csv")
    menu_nodes = _read_csv_rows(derived_path / "real_menu_nodes.csv")

    feature_rows, profiles, summary = _compute_profiles(purchase_events, dish_features)
    _write_csv(out_path / "real_user_feature_values.csv", feature_rows)
    _write_json(out_path / "real_user_profiles.json", profiles)
    _write_csv(audit_dir / "user_profile_summary.csv", summary)
    _write_csv(audit_dir / "user_profile_sanity_sample.csv", _profile_sanity_sample(profiles, feature_rows))
    _write_csv(
        audit_dir / "user_top_items_vs_profile.csv",
        _user_top_items_vs_profile(purchase_events, profiles, dish_features, menu_nodes),
    )
    return ProfileStats(users=len(profiles), feature_rows=len(feature_rows))


def recommend_real(derived: Path | str, user_id: str, venue: str, top_k: int) -> RecommendationStats:
    derived_path = Path(derived)
    audit_dir = derived_path / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    user_profiles = _read_json(derived_path / "real_user_profiles.json")
    if not isinstance(user_profiles, list):
        raise ValueError("real_user_profiles.json must contain list")
    canonical_user_id = _canonical_user_id(user_id)
    profile_lookup = _build_profile_lookup(user_profiles)
    profile = profile_lookup.get(canonical_user_id)
    if profile is None:
        sample_ids = sorted({str(row.get("user_id", "")) for row in user_profiles if row.get("user_id")})[:10]
        raise ValueError(
            f"user_id not found: requested={user_id} canonical={canonical_user_id or '<empty>'}; "
            f"sample_available_user_ids={sample_ids}"
        )

    menu_nodes = _read_csv_rows(derived_path / "real_menu_nodes.csv")
    dish_features = _read_csv_rows(derived_path / "real_dish_feature_values.csv")
    purchase_events = _normalize_purchase_events_for_profile(_read_csv_rows(derived_path / "real_purchase_events.csv"))
    available_venues_for_user = sorted(
        {
            str(row.get("venue_normalized", "") or row.get("venue", ""))
            for row in purchase_events
            if str(row.get("user_id", "")) == str(profile["user_id"])
            and (row.get("venue_normalized") or row.get("venue"))
        }
    )

    venue_normalized = _normalize_venue(venue)
    if venue_normalized and available_venues_for_user and venue_normalized not in set(available_venues_for_user):
        raise ValueError(
            f"user has no activity for venue: requested={venue} normalized={venue_normalized}; "
            f"available_venues_for_user={available_venues_for_user}"
        )
    candidates = _candidate_dishes_for_venue(menu_nodes, venue_normalized)
    if not candidates:
        raise ValueError(
            f"no candidate dishes for venue: requested={venue} normalized={venue_normalized or '<empty>'}; "
            f"available_venues_for_user={available_venues_for_user}"
        )
    ranked = _score_candidates(profile, candidates, dish_features, purchase_events, venue_normalized)
    top = ranked[: int(top_k)]

    _write_csv(derived_path / "recommendations_sample.csv", top)
    _write_csv(
        audit_dir / "recommend_input_resolution_sample.csv",
        _recommend_input_resolution_sample(
            requested_user_id=user_id,
            canonical_user_id=canonical_user_id,
            requested_venue=venue,
            normalized_venue=venue_normalized,
            available_user_ids=sorted({str(row.get("user_id", "")) for row in user_profiles if row.get("user_id")})[:15],
            available_venues_for_user=available_venues_for_user,
        ),
    )
    _write_csv(audit_dir / "recommendation_debug_sample.csv", ranked[:200])
    _write_recommendation_md(
        derived_path / "recommendation_examples.md",
        user_id=str(canonical_user_id or user_id),
        venue=venue_normalized or venue,
        rows=top,
    )
    return RecommendationStats(user_id=str(canonical_user_id or user_id), candidates=len(candidates), top_k=len(top))


def backtest_real(derived: Path | str, top_k: int, min_orders: int) -> BacktestStats:
    derived_path = Path(derived)
    audit_dir = derived_path / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    menu_nodes = _read_csv_rows(derived_path / "real_menu_nodes.csv")
    dish_features = _read_csv_rows(derived_path / "real_dish_feature_values.csv")
    purchase_events = _normalize_purchase_events_for_profile(_read_csv_rows(derived_path / "real_purchase_events.csv"))
    users = _read_csv_rows(derived_path / "real_user_identity.csv")
    links = _read_csv_rows(derived_path / "real_order_user_link.csv")

    by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in purchase_events:
        canonical = _canonical_user_id(event.get("user_id"))
        if canonical:
            by_user[canonical].append(event)
    users_with_link = {_canonical_user_id(row.get("user_id")) for row in users if _canonical_user_id(row.get("user_id"))}
    linked_users = {_canonical_user_id(row.get("user_id")) for row in links if _canonical_user_id(row.get("user_id"))}

    failures: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    per_venue: dict[str, list[dict[str, float]]] = defaultdict(list)
    metrics: list[dict[str, float]] = []
    filtered_drink_service = len([row for row in purchase_events if row.get("item_type") in {"drink", "service"}])

    for user_id in sorted(by_user.keys()):
        events = sorted(by_user[user_id], key=lambda row: (row["order_datetime"], row["order_id"], row["dish_id"]))
        order_ids = sorted({row["order_id"] for row in events})
        if user_id not in linked_users:
            failures.append({"user_id": user_id, "reason": "missing_order_link"})
            continue
        if len(order_ids) < int(min_orders):
            failures.append({"user_id": user_id, "reason": "not_enough_orders"})
            continue

        holdout_order = order_ids[-1]
        train_events = [row for row in events if row["order_id"] != holdout_order]
        holdout_events = [row for row in events if row["order_id"] == holdout_order]
        holdout_dishes = sorted({row["dish_id"] for row in holdout_events})
        if not train_events or not holdout_dishes:
            failures.append({"user_id": user_id, "reason": "empty_train_or_holdout"})
            continue

        venue = _normalize_venue(holdout_events[0].get("venue_normalized", "") or holdout_events[0].get("venue", ""))
        feature_rows, profiles, _ = _compute_profiles(train_events, dish_features)
        if not profiles:
            failures.append({"user_id": user_id, "reason": "profile_empty_after_holdout"})
            continue
        profile = profiles[0]
        candidates = _candidate_dishes_for_venue(menu_nodes, venue)
        if not candidates:
            failures.append({"user_id": user_id, "reason": f"no_candidates_for_venue:{venue}"})
            continue
        ranked = _score_candidates(profile, candidates, dish_features, train_events, venue)
        top = ranked[: int(top_k)]
        ranked_ids = [row["dish_id"] for row in ranked]
        top5 = set(ranked_ids[:5])
        top10 = set(ranked_ids[:10])
        holdout_set = set(holdout_dishes)
        hit5 = 1.0 if holdout_set & top5 else 0.0
        hit10 = 1.0 if holdout_set & top10 else 0.0
        recall10 = len(holdout_set & top10) / max(1, len(holdout_set))
        rr = 0.0
        for idx, dish_id in enumerate(ranked_ids, start=1):
            if dish_id in holdout_set:
                rr = 1.0 / idx
                break
        record = {"hit5": hit5, "hit10": hit10, "recall10": recall10, "mrr": rr}
        metrics.append(record)
        per_venue[venue].append(record)
        sample_rows.append(
            {
                "user_id": user_id,
                "venue": venue,
                "holdout_order_id": holdout_order,
                "holdout_dishes": "|".join(holdout_dishes),
                "top10_predicted": "|".join(ranked_ids[:10]),
                "hit_at_5": hit5,
                "hit_at_10": hit10,
                "recall_at_10": round(recall10, 6),
                "mrr": round(rr, 6),
            }
        )

    summary = [
        {
            "metric": "users_in_backtest",
            "value": len(metrics),
        },
        {"metric": "hit_at_5", "value": round(_mean([row["hit5"] for row in metrics]), 6)},
        {"metric": "hit_at_10", "value": round(_mean([row["hit10"] for row in metrics]), 6)},
        {"metric": "recall_at_10", "value": round(_mean([row["recall10"] for row in metrics]), 6)},
        {"metric": "mrr", "value": round(_mean([row["mrr"] for row in metrics]), 6)},
    ]
    by_venue_rows: list[dict[str, Any]] = []
    for venue, rows in sorted(per_venue.items()):
        by_venue_rows.append(
            {
                "venue": venue,
                "users": len(rows),
                "hit_at_5": round(_mean([row["hit5"] for row in rows]), 6),
                "hit_at_10": round(_mean([row["hit10"] for row in rows]), 6),
                "recall_at_10": round(_mean([row["recall10"] for row in rows]), 6),
                "mrr": round(_mean([row["mrr"] for row in rows]), 6),
            }
        )

    coverage_rows = [
        {"metric": "users_total", "value": len(users_with_link)},
        {"metric": "users_with_profiles", "value": len(by_user)},
        {"metric": "users_in_backtest", "value": len(metrics)},
        {"metric": "backtest_eligibility_dropped_users_count", "value": len(failures)},
        {"metric": "orders_filtered_drink_service_count", "value": filtered_drink_service},
    ]

    _write_csv(derived_path / "backtest_summary.csv", summary)
    _write_csv(derived_path / "backtest_by_venue.csv", by_venue_rows)
    _write_csv(derived_path / "backtest_user_sample.csv", sample_rows[:200])
    _write_csv(audit_dir / "backtest_coverage.csv", coverage_rows)
    _write_csv(audit_dir / "backtest_failures.csv", failures)
    _write_csv(audit_dir / "backtest_eligibility_drop_reasons.csv", _group_backtest_drop_reasons(failures))
    _write_csv(
        audit_dir / "linkage_metric_breakdown.csv",
        _build_linkage_metric_breakdown(
            orders_total=len(_read_csv_rows(derived_path / "real_order_headers.csv")),
            linked_orders_count=len([row for row in _read_csv_rows(derived_path / "real_order_user_link.csv") if row.get("user_id")]),
            food_items_total=len([row for row in _read_csv_rows(derived_path / "real_order_item_match.csv") if row.get("item_type") == "food"]),
            matched_food_items_count=len(
                [
                    row
                    for row in _read_csv_rows(derived_path / "real_order_item_match.csv")
                    if row.get("item_type") == "food" and row.get("matched_dish_id")
                ]
            ),
            purchase_events_total=len(purchase_events),
            linked_purchase_events_count=len([row for row in purchase_events if row.get("user_id")]),
            users_total=len(users_with_link),
            users_with_profiles=len(by_user),
            users_in_backtest=len(metrics),
        ),
    )
    _write_csv(
        audit_dir / "linkage_delta_summary.csv",
        _build_linkage_delta_summary(
            before_snapshot=_read_json_if_exists(audit_dir / "linkage_before_snapshot.json"),
            after_snapshot=_collect_pipeline_metric_snapshot(derived_path),
        ),
    )

    return BacktestStats(
        users_in_backtest=len(metrics),
        hit_at_5=round(_mean([row["hit5"] for row in metrics]), 6),
        hit_at_10=round(_mean([row["hit10"] for row in metrics]), 6),
        recall_at_10=round(_mean([row["recall10"] for row in metrics]), 6),
        mrr=round(_mean([row["mrr"] for row in metrics]), 6),
    )


def _read_guest_card_rows(path: Path) -> list[dict[str, Any]]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    it = ws.iter_rows(values_only=True)
    headers = [str(v).strip() if v is not None else "" for v in next(it)]
    rows: list[dict[str, Any]] = []
    for raw in it:
        if raw is None:
            continue
        values = list(raw)
        if not any(value is not None and str(value).strip() for value in values):
            continue
        row: dict[str, Any] = {}
        for idx, header in enumerate(headers):
            row[header] = values[idx] if idx < len(values) else ""
        rows.append(row)
    return rows


def _read_orders_rows(path: Path) -> list[dict[str, Any]]:
    encodings = ("utf-8-sig", "utf-8", "cp1251")
    for enc in encodings:
        try:
            with path.open("r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                rows = [dict(row) for row in reader]
            return rows
        except UnicodeDecodeError:
            continue
    raise ValueError(f"unable to decode csv file: {path}")


def _normalize_real_users(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        order_id = _clean(row.get("Номер заказа"))
        user_id_raw = _clean(row.get("Id клиента"))
        user_id = _canonical_user_id(user_id_raw)
        phone = _normalize_phone(_clean(row.get("Телефон")))
        card_number_raw = _clean(row.get("Номер карты"))
        card_number_normalized = _normalize_card_number(card_number_raw)
        venue_raw = _clean(row.get("Заведение"))
        venue_normalized = _normalize_venue(venue_raw)
        out.append(
            {
                "user_id": user_id or f"phone_{phone}" if phone else "",
                "user_id_raw": user_id_raw,
                "source_user_id": user_id_raw,
                "order_id": order_id,
                "phone_normalized": phone,
                "phone_hash": _stable_hash(phone),
                "card_number_raw": card_number_raw,
                "card_number_normalized": card_number_normalized,
                "guest_card_key": card_number_normalized or user_id or phone,
                "visit_datetime": _to_iso_datetime(_clean(row.get("Время визита"))),
                "venue_raw": venue_raw,
                "venue_normalized": venue_normalized,
                "venue": venue_normalized,
                "check_amount": _safe_float(row.get("Сумма чека")),
                "paid_amount": _safe_float(row.get("Оплачено")),
                "checks_count": _safe_int(row.get("Чеков")),
            }
        )
    return sorted(out, key=lambda item: (item["order_id"], item["user_id"]))


def _normalize_real_orders(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    headers: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for row in rows:
        order_id = _clean(row.get("Номер заказа"))
        order_date = _clean(row.get("Дата"))
        order_time = _clean(row.get("Время"))
        order_dt = _to_iso_datetime(f"{order_date} {order_time}".strip())
        raw_clean_dishes = _clean(row.get("Чистые блюда"))
        raw_item_list = _clean(row.get("Список блюд"))
        # Real export uses two layouts: either items are in "Список блюд" (expected),
        # or in "Чистые блюда" with trailing comma and empty "Список блюд".
        if raw_item_list and "[" in raw_item_list:
            items_raw = raw_item_list
        elif raw_clean_dishes and "[" in raw_clean_dishes:
            items_raw = raw_clean_dishes
        else:
            items_raw = raw_item_list or raw_clean_dishes
        clean_count = _safe_int(raw_clean_dishes) if "[" not in raw_clean_dishes else 0

        headers.append(
            {
                "order_id": order_id,
                "order_date": order_date,
                "order_time": order_time,
                "order_datetime": order_dt,
                "guest_count": _safe_int(row.get("Число гостей")),
                "clean_dishes_count": clean_count,
                "items_raw": items_raw,
            }
        )
        parsed_items = _parse_items_list(items_raw)
        for idx, item in enumerate(parsed_items, start=1):
            item_type = _classify_item_type(item)
            items.append(
                {
                    "order_id": order_id,
                    "line_no": idx,
                    "item_name_raw": item,
                    "item_name_norm": _norm(item),
                    "item_type": item_type,
                }
            )
    return (
        sorted(headers, key=lambda item: (item["order_datetime"], item["order_id"])),
        sorted(items, key=lambda item: (item["order_id"], item["line_no"])),
    )


def _link_orders_users(
    users: list[dict[str, Any]],
    orders: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_order: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in users:
        by_order[row["order_id"]].append(row)
    links: list[dict[str, Any]] = []
    missing = 0
    multi = 0
    conflict_cases: list[dict[str, Any]] = []
    method_counts: dict[str, list[float]] = defaultdict(list)
    low_confidence_links: list[dict[str, Any]] = []
    unlinked_reason_counts: dict[str, int] = defaultdict(int)
    for order in orders:
        options = by_order.get(order["order_id"], [])
        if not options:
            missing += 1
            reason = "missing_order_number_match"
            unlinked_reason_counts[reason] += 1
            links.append(
                {
                    "order_id": order["order_id"],
                    "user_id": "",
                    "linkage_method": "unlinked",
                    "linkage_confidence": 0.0,
                    "conflict_flag": True,
                    "evidence": reason,
                }
            )
            continue
        chosen: dict[str, Any] | None = None
        linkage_method = "exact_order_number"
        linkage_confidence = 1.0
        conflict_flag = False
        evidence_parts = [f"order_id={order['order_id']}", f"candidate_rows={len(options)}"]
        if len(options) > 1:
            multi += 1
            conflict_flag = True
        options_sorted = sorted(options, key=lambda row: (row.get("visit_datetime", ""), row.get("user_id", "")))
        unique_user_ids = sorted({row.get("user_id", "") for row in options_sorted if row.get("user_id")})
        unique_phones = sorted({row.get("phone_normalized", "") for row in options_sorted if row.get("phone_normalized")})
        unique_cards = sorted({row.get("card_number_normalized", "") for row in options_sorted if row.get("card_number_normalized")})
        if len(options_sorted) == 1:
            chosen = options_sorted[0]
            evidence_parts.append("single_candidate_for_order")
        elif len(unique_user_ids) == 1:
            linkage_method = "exact_client_id"
            linkage_confidence = 0.99
            chosen = next((row for row in options_sorted if row.get("user_id") == unique_user_ids[0]), options_sorted[0])
            evidence_parts.append(f"unique_user_id={unique_user_ids[0]}")
        elif len(unique_phones) == 1:
            linkage_method = "normalized_phone"
            linkage_confidence = 0.94
            chosen = next((row for row in options_sorted if row.get("phone_normalized") == unique_phones[0]), options_sorted[0])
            evidence_parts.append(f"unique_phone={unique_phones[0]}")
        elif len(unique_cards) == 1:
            linkage_method = "normalized_card_number"
            linkage_confidence = 0.92
            chosen = next((row for row in options_sorted if row.get("card_number_normalized") == unique_cards[0]), options_sorted[0])
            evidence_parts.append(f"unique_card={unique_cards[0]}")
        else:
            linkage_method = "deterministic_composite_fallback"
            linkage_confidence = 0.7
            order_dt = _safe_iso_datetime(order.get("order_datetime"))
            scored: list[tuple[float, dict[str, Any]]] = []
            for candidate in options_sorted:
                visit_dt = _safe_iso_datetime(candidate.get("visit_datetime"))
                time_distance = abs((visit_dt - order_dt).total_seconds()) if visit_dt and order_dt else 10**9
                missing_penalty = 0
                if not candidate.get("user_id"):
                    missing_penalty += 200000
                if not candidate.get("phone_normalized"):
                    missing_penalty += 100000
                if not candidate.get("card_number_normalized"):
                    missing_penalty += 10000
                deterministic_score = float(time_distance) + float(missing_penalty)
                scored.append((deterministic_score, candidate))
            scored.sort(key=lambda item: (item[0], _clean(item[1].get("visit_datetime", "")), _clean(item[1].get("user_id", ""))))
            chosen = scored[0][1] if scored else options_sorted[0]
            evidence_parts.append("fallback_by_time_distance+identity_completeness")
        assert chosen is not None
        if not chosen.get("user_id"):
            reason = "missing_canonical_user_id_after_linkage"
            unlinked_reason_counts[reason] += 1
            links.append(
                {
                    "order_id": order["order_id"],
                    "user_id": "",
                    "linkage_method": linkage_method,
                    "linkage_confidence": round(linkage_confidence, 6),
                    "conflict_flag": True,
                    "evidence": ";".join(evidence_parts + [reason]),
                }
            )
            continue
        evidence_parts += [
            f"candidate_user_ids={','.join(unique_user_ids) or '<empty>'}",
            f"candidate_phones={','.join(unique_phones) or '<empty>'}",
            f"candidate_cards={','.join(unique_cards) or '<empty>'}",
        ]
        links.append(
            {
                "order_id": order["order_id"],
                "user_id": chosen["user_id"],
                "linkage_method": linkage_method,
                "linkage_confidence": round(linkage_confidence, 6),
                "conflict_flag": bool(conflict_flag),
                "evidence": ";".join(evidence_parts),
            }
        )
        method_counts[linkage_method].append(float(linkage_confidence))
        if float(linkage_confidence) < 0.8:
            low_confidence_links.append(
                {
                    "order_id": order["order_id"],
                    "user_id": chosen["user_id"],
                    "linkage_method": linkage_method,
                    "linkage_confidence": round(linkage_confidence, 6),
                    "conflict_flag": bool(conflict_flag),
                    "evidence": ";".join(evidence_parts),
                }
            )
        if conflict_flag:
            conflict_cases.append(
                {
                    "order_id": order["order_id"],
                    "candidate_count": len(options_sorted),
                    "chosen_user_id": chosen["user_id"],
                    "linkage_method": linkage_method,
                    "linkage_confidence": round(linkage_confidence, 6),
                    "conflict_flag": bool(conflict_flag),
                    "evidence": ";".join(evidence_parts),
                }
            )
    orders_total = len(orders)
    linked_orders_count = len([row for row in links if row["user_id"]])
    order_linkage_coverage = round(linked_orders_count / max(1, orders_total), 6)
    quality = [
        {"metric": "orders_total", "value": orders_total},
        {"metric": "linked_orders_count", "value": linked_orders_count},
        {"metric": "order_linkage_coverage", "value": order_linkage_coverage},
        {"metric": "unlinked_orders_count", "value": orders_total - linked_orders_count},
        {"metric": "conflict_orders_count", "value": len(conflict_cases)},
        {"metric": "ambiguous_multi_user_same_order", "value": multi},
        {"metric": "missing_order_number_match", "value": missing},
    ]
    method_breakdown = []
    for method, confidences in sorted(method_counts.items()):
        method_links = [row for row in links if row.get("linkage_method") == method and row.get("user_id")]
        method_breakdown.append(
            {
                "linkage_method": method,
                "orders_count": len(method_links),
                "share_of_orders": round(len(method_links) / max(1, orders_total), 6),
                "avg_confidence": round(_mean(confidences), 6),
                "conflict_cases_count": len([row for row in method_links if str(row.get("conflict_flag")).lower() in {"true", "1"}]),
            }
        )
    unlinked_reasons = [
        {"reason_code": reason, "orders_count": count}
        for reason, count in sorted(unlinked_reason_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    audits = {
        "method_breakdown": method_breakdown,
        "conflict_cases": sorted(conflict_cases, key=lambda item: item["order_id"]),
        "low_confidence_links": sorted(low_confidence_links, key=lambda item: item["order_id"]),
        "unlinked_reasons": unlinked_reasons,
    }
    return sorted(links, key=lambda item: item["order_id"]), quality, audits


def _load_top50_curated_hardening(manual_curation_dir: Path, menu_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    seed_path = manual_curation_dir / "top50_alias_hardening_seed.csv"
    review_path = manual_curation_dir / "top50_manual_review_queue.csv"
    seed_rows = _read_csv_rows(seed_path)
    review_rows = _read_csv_rows(review_path)

    menu_nodes_by_id = {str(row.get("node_id", "")): row for row in menu_nodes}
    map_alias_by_name: dict[str, str] = {}
    map_alias_rows: dict[str, dict[str, Any]] = {}
    reclassify_by_name: dict[str, str] = {}
    top50_names: set[str] = set()

    for row in seed_rows:
        item_name_norm = _norm(row.get("item_name_norm", ""))
        if not item_name_norm:
            continue
        top50_names.add(item_name_norm)
        action = _clean(row.get("proposed_action"))
        if action == "map_dish_alias":
            target_id = _clean(row.get("proposed_target_id"))
            target_node = menu_nodes_by_id.get(target_id)
            if target_id and target_node and target_node.get("node_type") == "dish" and str(target_node.get("is_sellable", "")).lower() in {"true", "1"}:
                map_alias_by_name[item_name_norm] = target_id
                map_alias_rows[item_name_norm] = row
        elif action == "reclassify_drink":
            reclassify_by_name[item_name_norm] = "drink"
        elif action == "reclassify_service":
            reclassify_by_name[item_name_norm] = "service"

    manual_review_names = {_norm(row.get("item_name_norm", "")) for row in review_rows if _norm(row.get("item_name_norm", ""))}
    top50_names.update(manual_review_names)

    return {
        "seed_loaded": seed_path.exists(),
        "review_loaded": review_path.exists(),
        "seed_rows_count": len(seed_rows),
        "review_rows_count": len(review_rows),
        "map_alias_by_name": map_alias_by_name,
        "map_alias_rows": map_alias_rows,
        "reclassify_by_name": reclassify_by_name,
        "manual_review_names": manual_review_names,
        "top50_names": top50_names,
        "menu_nodes_by_id": menu_nodes_by_id,
    }


def _apply_curated_reclassifications(
    order_items: list[dict[str, Any]],
    curated: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    reclassify_by_name = dict(curated.get("reclassify_by_name", {}))
    top50_names = set(curated.get("top50_names", set()))
    out: list[dict[str, Any]] = []
    hardening_rows: list[dict[str, Any]] = []
    affected_food_before = 0
    affected_food_after = 0

    for row in order_items:
        item_name_norm = _norm(row.get("item_name_norm", ""))
        previous_item_type = _clean(row.get("item_type"))
        if item_name_norm in top50_names and previous_item_type == "food":
            affected_food_before += 1
        new_item_type = reclassify_by_name.get(item_name_norm, previous_item_type)
        if item_name_norm in top50_names and new_item_type == "food":
            affected_food_after += 1

        updated = {
            **row,
            "item_name_norm": item_name_norm,
            "item_type": new_item_type,
        }
        out.append(updated)

        if new_item_type != previous_item_type:
            action = "reclassified_to_drink" if new_item_type == "drink" else "reclassified_to_service"
            hardening_rows.append(
                {
                    "order_id": row["order_id"],
                    "line_no": row["line_no"],
                    "item_name_raw": row["item_name_raw"],
                    "item_name_norm": item_name_norm,
                    "action": action,
                    "previous_item_type": previous_item_type,
                    "new_item_type": new_item_type,
                    "matched_dish_id": "",
                    "matched_dish_name": "",
                    "source": "top50_alias_hardening_seed.csv",
                    "details": "applied_before_food_matching",
                }
            )

    return out, hardening_rows, affected_food_before, affected_food_after


def _top50_hardening_summary(
    curated: dict[str, Any],
    hardening_applied: list[dict[str, Any]],
    affected_food_before: int,
    affected_food_after: int,
) -> list[dict[str, Any]]:
    mapped_count = len([row for row in hardening_applied if row.get("action") == "mapped_to_dish"])
    drink_count = len([row for row in hardening_applied if row.get("action") == "reclassified_to_drink"])
    service_count = len([row for row in hardening_applied if row.get("action") == "reclassified_to_service"])
    kept_review_count = len([row for row in hardening_applied if row.get("action") == "kept_in_review_queue"])
    affected_distinct_orders = len({str(row.get("order_id", "")) for row in hardening_applied if _clean(row.get("order_id", ""))})

    return [
        {"metric": "seed_file_loaded", "value": int(bool(curated.get("seed_loaded"))), "details": ""},
        {"metric": "review_file_loaded", "value": int(bool(curated.get("review_loaded"))), "details": ""},
        {"metric": "total_curated_rows", "value": len(set(curated.get("top50_names", set()))), "details": ""},
        {"metric": "mapped_to_dish_count", "value": mapped_count, "details": ""},
        {"metric": "reclassified_to_drink_count", "value": drink_count, "details": ""},
        {"metric": "reclassified_to_service_count", "value": service_count, "details": ""},
        {"metric": "kept_in_review_queue_count", "value": kept_review_count, "details": ""},
        {"metric": "affected_distinct_orders", "value": affected_distinct_orders, "details": ""},
        {"metric": "affected_food_items_before", "value": affected_food_before, "details": ""},
        {"metric": "affected_food_items_after", "value": affected_food_after, "details": ""},
    ]


def _build_dish_lookup_for_real(menu_nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in menu_nodes:
        if row.get("node_type") != "dish":
            continue
        if str(row.get("is_sellable")).lower() not in {"true", "1"}:
            continue
        name_norm = _norm(row.get("node_name", ""))
        if name_norm:
            lookup[name_norm] = row
    return lookup


def _match_real_order_items(
    order_items: list[dict[str, Any]],
    dish_lookup: dict[str, dict[str, Any]],
    curated: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    curated = curated or {}
    manual_review_names = set(curated.get("manual_review_names", set()))
    map_alias_by_name = dict(curated.get("map_alias_by_name", {}))
    map_alias_rows = dict(curated.get("map_alias_rows", {}))
    menu_nodes_by_id = dict(curated.get("menu_nodes_by_id", {}))
    rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    hardening_rows: list[dict[str, Any]] = []
    for row in order_items:
        if row["item_type"] != "food":
            rows.append(
                {
                    **row,
                    "matched_dish_id": "",
                    "match_method": "not_food",
                    "match_confidence": 0.0,
                    "review_required": False,
                }
            )
            continue
        name = _norm(row["item_name_norm"])
        explicit_node_id = map_alias_by_name.get(name, "")
        explicit_map_row = map_alias_rows.get(name, {})
        matched = None
        method = "exact"
        confidence = 0.0
        if explicit_node_id:
            target_node = menu_nodes_by_id.get(explicit_node_id)
            if target_node and target_node.get("node_type") == "dish" and str(target_node.get("is_sellable", "")).lower() in {"true", "1"}:
                matched = target_node
                method = "curated_alias"
                confidence = 1.0
                hardening_rows.append(
                    {
                        "order_id": row["order_id"],
                        "line_no": row["line_no"],
                        "item_name_raw": row["item_name_raw"],
                        "item_name_norm": name,
                        "action": "mapped_to_dish",
                        "previous_item_type": row["item_type"],
                        "new_item_type": row["item_type"],
                        "matched_dish_id": matched["node_id"],
                        "matched_dish_name": matched["node_name"],
                        "source": "top50_alias_hardening_seed.csv",
                        "details": f"proposed_action={explicit_map_row.get('proposed_action','map_dish_alias')}",
                    }
                )
            else:
                method = "curated_alias_invalid_target"
                confidence = 0.0
                unresolved.append(
                    {
                        "order_id": row["order_id"],
                        "line_no": row["line_no"],
                        "item_name_raw": row["item_name_raw"],
                        "item_name_norm": row["item_name_norm"],
                        "reason": "curated_alias_invalid_target",
                    }
                )
        elif name in manual_review_names:
            method = "manual_review_queue"
            confidence = 0.0
            unresolved.append(
                {
                    "order_id": row["order_id"],
                    "line_no": row["line_no"],
                    "item_name_raw": row["item_name_raw"],
                    "item_name_norm": row["item_name_norm"],
                    "reason": "manual_review_queue",
                }
            )
            hardening_rows.append(
                {
                    "order_id": row["order_id"],
                    "line_no": row["line_no"],
                    "item_name_raw": row["item_name_raw"],
                    "item_name_norm": name,
                    "action": "kept_in_review_queue",
                    "previous_item_type": row["item_type"],
                    "new_item_type": row["item_type"],
                    "matched_dish_id": "",
                    "matched_dish_name": "",
                    "source": "top50_manual_review_queue.csv",
                    "details": "blocked_auto_mapping",
                }
            )
        else:
            matched = dish_lookup.get(name)
            method = "exact"
            confidence = 1.0 if matched else 0.0
        if not matched and method not in {"manual_review_queue", "curated_alias_invalid_target"}:
            alias = _soft_normalize_name(name)
            matched = dish_lookup.get(alias)
            method = "alias"
            confidence = 0.92 if matched else 0.0
        if not matched and method not in {"manual_review_queue", "curated_alias_invalid_target"}:
            unresolved.append(
                {
                    "order_id": row["order_id"],
                    "line_no": row["line_no"],
                    "item_name_raw": row["item_name_raw"],
                    "item_name_norm": row["item_name_norm"],
                    "reason": "unmatched_food_item",
                }
            )
        rows.append(
            {
                **row,
                "matched_dish_id": matched["node_id"] if matched else "",
                "matched_dish_name": matched["node_name"] if matched else "",
                "match_method": (
                    method
                    if matched or method in {"manual_review_queue", "curated_alias_invalid_target"}
                    else "unresolved"
                ),
                "match_confidence": round(confidence, 6),
                "review_required": (not matched) or method in {"fuzzy_strict", "manual_review_queue", "curated_alias_invalid_target"},
            }
        )
    food_items = [row for row in rows if row["item_type"] == "food"]
    matched_food = [row for row in food_items if row["matched_dish_id"]]
    summary = [
        {"metric": "items_total", "value": len(rows)},
        {"metric": "food_items_total", "value": len(food_items)},
        {"metric": "matched_food_items_count", "value": len(matched_food)},
        {"metric": "food_match_coverage", "value": round(len(matched_food) / max(1, len(food_items)), 6)},
        {"metric": "unmatched_food_items_count", "value": len(food_items) - len(matched_food)},
        {"metric": "fuzzy_strict_matches", "value": 0},
        {"metric": "review_queue_size", "value": len([row for row in rows if row["review_required"]])},
    ]
    return rows, summary, unresolved, hardening_rows


def _build_real_purchase_events(
    headers: list[dict[str, Any]],
    links: list[dict[str, Any]],
    item_match: list[dict[str, Any]],
    dish_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    order_dt = {row["order_id"]: row["order_datetime"] for row in headers}
    link_map = {row["order_id"]: row for row in links}
    events: list[dict[str, Any]] = []
    for row in item_match:
        if row["item_type"] != "food":
            continue
        if not row["matched_dish_id"]:
            continue
        link = link_map.get(row["order_id"])
        if not link or not link["user_id"]:
            continue
        dish = dish_lookup.get(_norm(row["matched_dish_name"])) or {}
        venue_raw = _clean(dish.get("venue", ""))
        venue_normalized = _normalize_venue(venue_raw)
        events.append(
            {
                "event_id": _stable_hash(f"{row['order_id']}|{row['line_no']}|{link['user_id']}"),
                "user_id": _canonical_user_id(link.get("user_id")),
                "order_id": row["order_id"],
                "order_datetime": order_dt.get(row["order_id"], ""),
                "dish_id": row["matched_dish_id"],
                "dish_name": row["matched_dish_name"],
                "item_type": "food",
                "venue_raw": venue_raw,
                "venue_normalized": venue_normalized,
                "venue": venue_normalized or venue_raw,
                "menu_source": dish.get("menu_source", ""),
                "match_confidence": row["match_confidence"],
                "linkage_method": _clean(link.get("linkage_method")),
                "linkage_confidence": _safe_float(link.get("linkage_confidence")),
                "link_conflict_flag": str(link.get("conflict_flag", "")),
            }
        )
    return sorted(events, key=lambda item: (item["user_id"], item["order_datetime"], item["order_id"], item["dish_id"]))


def _drink_service_leakage_real(
    item_match: list[dict[str, Any]],
    purchase_events: list[dict[str, Any]],
    dish_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    food_rows = len([row for row in item_match if row["item_type"] == "food"])
    leaked = len([row for row in purchase_events if row.get("item_type") != "food"])
    linked_purchase_events_count = len([row for row in purchase_events if row.get("user_id")])
    return [
        {"metric": "food_items_total", "value": food_rows, "details": ""},
        {"metric": "purchase_events_total", "value": len(purchase_events), "details": ""},
        {"metric": "linked_purchase_events_count", "value": linked_purchase_events_count, "details": ""},
        {
            "metric": "purchase_event_linkage_coverage",
            "value": round(linked_purchase_events_count / max(1, len(purchase_events)), 6),
            "details": "linked_purchase_events_count/purchase_events_total",
        },
        {"metric": "leaked_non_food_events", "value": leaked, "details": ""},
        {"metric": "leakage_ratio", "value": round(leaked / max(1, len(purchase_events)), 6), "details": ""},
        {"metric": "dish_lookup_size", "value": len(dish_lookup), "details": ""},
    ]


def _compute_profiles(
    purchase_events: list[dict[str, Any]],
    dish_features: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    features_by_dish: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dish_features:
        features_by_dish[str(row["dish_id"])].append(row)
    by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in purchase_events:
        canonical = _canonical_user_id(event.get("user_id"))
        if canonical:
            by_user[canonical].append(event)

    all_rows: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for user_id in sorted(by_user.keys()):
        events = sorted(by_user[user_id], key=lambda item: (item["order_datetime"], item["order_id"], item["dish_id"]))
        if not events:
            continue
        long_term: dict[tuple[str, str], float] = defaultdict(float)
        short_term: dict[tuple[str, str], float] = defaultdict(float)
        latest = _safe_iso_datetime(events[-1]["order_datetime"])
        repeats: dict[str, int] = defaultdict(int)
        for event in events:
            repeats[event["dish_id"]] += 1
            event_dt = _safe_iso_datetime(event["order_datetime"]) or latest
            days = max(0.0, ((latest - event_dt).total_seconds() / 86400.0) if latest and event_dt else 0.0)
            long_decay = math.exp(-days / 120.0)
            short_decay = math.exp(-days / 10.0)
            repeat_boost = 1.0 + min(0.6, (repeats[event["dish_id"]] - 1) * 0.12)

            for feature in features_by_dish.get(event["dish_id"], []):
                axis = str(feature.get("axis", ""))
                if axis not in {"ingredient", "method", "format_texture", "restaurant", "cuisine"}:
                    continue
                key = str(feature.get("feature_key", ""))
                weight = _safe_float(feature.get("weight", 0.0))
                long_term[(axis, key)] += weight * long_decay * 0.20 * repeat_boost
                short_term[(axis, key)] += weight * short_decay * 0.50 * repeat_boost
            venue_value = _normalize_venue(event.get("venue_normalized", "") or event.get("venue", ""))
            if venue_value:
                long_term[("restaurant", f"venue:{venue_value}")] += 0.08 * long_decay
                short_term[("restaurant", f"venue:{venue_value}")] += 0.20 * short_decay

        for (axis, key), value in sorted(long_term.items(), key=lambda item: (item[0][0], item[0][1])):
            all_rows.append(
                {
                    "user_id": user_id,
                    "layer": "long_term",
                    "axis": axis,
                    "feature_key": key,
                    "weight": round(_clip(value), 6),
                    "source": "purchase_only",
                }
            )
        for (axis, key), value in sorted(short_term.items(), key=lambda item: (item[0][0], item[0][1])):
            all_rows.append(
                {
                    "user_id": user_id,
                    "layer": "short_term",
                    "axis": axis,
                    "feature_key": key,
                    "weight": round(_clip(value), 6),
                    "source": "purchase_only",
                }
            )
        profiles.append(
            {
                "user_id": user_id,
                "explicit": {},
                "long_term": _layer_to_json(long_term),
                "short_term": _layer_to_json(short_term),
                "meta": {
                    "orders_count": len(sorted({row["order_id"] for row in events})),
                    "events_count": len(events),
                    "last_order_datetime": events[-1]["order_datetime"],
                },
            }
        )
        summary.append(
            {
                "user_id": user_id,
                "orders_count": len(sorted({row["order_id"] for row in events})),
                "events_count": len(events),
                "long_term_features": len(long_term),
                "short_term_features": len(short_term),
            }
        )
    return (
        sorted(all_rows, key=lambda item: (item["user_id"], item["layer"], item["axis"], item["feature_key"])),
        sorted(profiles, key=lambda item: item["user_id"]),
        sorted(summary, key=lambda item: item["user_id"]),
    )


def _candidate_dishes_for_venue(menu_nodes: list[dict[str, Any]], venue: str) -> list[dict[str, Any]]:
    venue_norm = _normalize_venue(venue)
    rows = []
    for row in menu_nodes:
        if row.get("node_type") != "dish":
            continue
        if str(row.get("is_sellable")).lower() not in {"true", "1"}:
            continue
        if _classify_item_type(str(row.get("node_name", ""))) != "food":
            continue
        row_venue = _normalize_venue(row.get("venue", ""))
        if venue_norm and row_venue and venue_norm != row_venue:
            continue
        rows.append(row)
    return sorted(rows, key=lambda item: item["node_id"])


def _score_candidates(
    profile: dict[str, Any],
    candidates: list[dict[str, Any]],
    dish_features: list[dict[str, Any]],
    purchase_events: list[dict[str, Any]],
    venue: str,
) -> list[dict[str, Any]]:
    by_dish: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dish_features:
        by_dish[str(row["dish_id"])].append(row)
    user_id = _canonical_user_id(profile.get("user_id"))
    user_events = [row for row in purchase_events if str(row["user_id"]) == user_id]
    recency_map: dict[str, tuple[int, datetime | None]] = defaultdict(lambda: (0, None))
    for row in user_events:
        dish_id = row["dish_id"]
        count, prev = recency_map[dish_id]
        dt = _safe_iso_datetime(row["order_datetime"])
        if prev is None or (dt and prev and dt > prev):
            recency_map[dish_id] = (count + 1, dt)
        else:
            recency_map[dish_id] = (count + 1, prev)

    long = _flatten_layer(profile.get("long_term", {}))
    short = _flatten_layer(profile.get("short_term", {}))
    venue_norm = _normalize_venue(venue)
    now = max((_safe_iso_datetime(row.get("order_datetime", "")) for row in user_events), default=None)

    ranked: list[dict[str, Any]] = []
    for dish in candidates:
        dish_id = str(dish["node_id"])
        feats = by_dish.get(dish_id, [])
        ingredient_score = 0.0
        method_score = 0.0
        format_score = 0.0
        restaurant_score = 0.0
        for feat in feats:
            axis = str(feat.get("axis", ""))
            key = str(feat.get("feature_key", ""))
            weight = _safe_float(feat.get("weight", 0.0))
            base = (long.get((axis, key), 0.0) * 0.65) + (short.get((axis, key), 0.0) * 1.0)
            delta = base * weight
            if axis == "ingredient":
                ingredient_score += delta
            elif axis in {"method", "cuisine"}:
                method_score += delta
            elif axis == "format_texture":
                format_score += delta
            elif axis == "restaurant":
                restaurant_score += delta

        repeat_count, last_dt = recency_map.get(dish_id, (0, None))
        recency_penalty = 0.0
        repeat_bonus = min(0.8, repeat_count * 0.12)
        if now and last_dt:
            days = max(0.0, (now - last_dt).total_seconds() / 86400.0)
            recency_penalty = max(0.0, 0.6 - (days / 20.0))
        novelty_bonus = 0.35 if repeat_count == 0 else 0.0
        diversity_penalty = 0.12 * repeat_count
        venue_boost = 0.25 if venue_norm and _normalize_venue(dish.get("venue", "")) == venue_norm else 0.0
        score = (
            ingredient_score
            + method_score
            + format_score
            + restaurant_score
            + repeat_bonus
            + novelty_bonus
            + venue_boost
            - recency_penalty
            - diversity_penalty
        )
        ranked.append(
            {
                "user_id": user_id,
                "venue": venue_norm or venue,
                "dish_id": dish_id,
                "dish_name": dish["node_name"],
                "score": round(score, 6),
                "ingredient_match": round(ingredient_score, 6),
                "method_cuisine_match": round(method_score, 6),
                "format_texture_match": round(format_score, 6),
                "restaurant_match": round(restaurant_score, 6),
                "repeat_bonus": round(repeat_bonus, 6),
                "recency_penalty": round(recency_penalty, 6),
                "novelty_bonus": round(novelty_bonus, 6),
                "diversity_penalty": round(diversity_penalty, 6),
                "venue_boost": round(venue_boost, 6),
                "history_count_same_dish": repeat_count,
                "explanation": _explain_candidate(
                    ingredient_score=ingredient_score,
                    method_score=method_score,
                    format_score=format_score,
                    restaurant_score=restaurant_score,
                    repeat_bonus=repeat_bonus,
                    novelty_bonus=novelty_bonus,
                    venue_boost=venue_boost,
                    recency_penalty=recency_penalty,
                    diversity_penalty=diversity_penalty,
                ),
            }
        )
    ranked.sort(key=lambda item: (-item["score"], item["dish_name"], item["dish_id"]))
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


def _high_freq_unmatched(unmatched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in unmatched:
        key = row["item_name_norm"]
        bucket = grouped.setdefault(
            key,
            {"item_name_norm": key, "example_item_name_raw": row["item_name_raw"], "count": 0, "distinct_orders": set()},
        )
        bucket["count"] += 1
        bucket["distinct_orders"].add(row["order_id"])
    out = [
        {
            "item_name_norm": row["item_name_norm"],
            "example_item_name_raw": row["example_item_name_raw"],
            "count": row["count"],
            "distinct_orders": len(row["distinct_orders"]),
            "review_required": True,
        }
        for row in grouped.values()
    ]
    return sorted(out, key=lambda item: (-item["count"], item["item_name_norm"]))[:200]


def _top_matched_food(item_match: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in item_match:
        if row["item_type"] != "food" or not row["matched_dish_id"]:
            continue
        key = row["item_name_norm"]
        bucket = grouped.setdefault(
            key,
            {"item_name_norm": key, "example_item_name_raw": row["item_name_raw"], "hits": 0, "dish_id": row["matched_dish_id"], "dish_name": row["matched_dish_name"]},
        )
        bucket["hits"] += 1
    return sorted(grouped.values(), key=lambda item: (-item["hits"], item["item_name_norm"]))[:200]


def _profile_sanity_sample(profiles: list[dict[str, Any]], feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        by_user[str(row["user_id"])].append(row)
    out: list[dict[str, Any]] = []
    for profile in profiles[:200]:
        user_id = str(profile["user_id"])
        long_rows = [row for row in by_user[user_id] if row["layer"] == "long_term"]
        long_rows = sorted(long_rows, key=lambda item: (-_safe_float(item["weight"]), item["axis"], item["feature_key"]))
        top = "|".join(f"{row['axis']}:{row['feature_key']}={row['weight']}" for row in long_rows[:10])
        leakage = [row for row in long_rows if row["axis"] in {"drink", "service"}]
        out.append(
            {
                "user_id": user_id,
                "orders_count": profile.get("meta", {}).get("orders_count", 0),
                "top_features": top,
                "drink_service_feature_hits": len(leakage),
                "sanity_status": "ok" if not leakage else "review",
            }
        )
    return out


def _user_top_items_vs_profile(
    purchase_events: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    dish_features: list[dict[str, Any]],
    menu_nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    profile_map = {_canonical_user_id(row.get("user_id")): row for row in profiles if _canonical_user_id(row.get("user_id"))}
    node_name = {str(row["node_id"]): row.get("node_name", "") for row in menu_nodes}
    features_by_dish: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dish_features:
        features_by_dish[str(row["dish_id"])].append(row)
    by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in purchase_events:
        canonical = _canonical_user_id(row.get("user_id"))
        if canonical:
            by_user[canonical].append(row)
    out: list[dict[str, Any]] = []
    for user_id, events in sorted(by_user.items()):
        dish_counts: dict[str, int] = defaultdict(int)
        for event in events:
            dish_counts[event["dish_id"]] += 1
        profile = profile_map.get(user_id, {})
        top_profile = set()
        for axis, tags in profile.get("long_term", {}).items():
            for key, value in sorted(tags.items(), key=lambda item: (-_safe_float(item[1]), item[0]))[:10]:
                top_profile.add(f"{axis}:{key}")
        for dish_id, count in sorted(dish_counts.items(), key=lambda item: (-item[1], item[0]))[:5]:
            overlaps = []
            for feat in features_by_dish.get(dish_id, []):
                token = f"{feat['axis']}:{feat['feature_key']}"
                if token in top_profile:
                    overlaps.append(token)
            out.append(
                {
                    "user_id": user_id,
                    "dish_id": dish_id,
                    "dish_name": node_name.get(dish_id, dish_id),
                    "purchase_count": count,
                    "overlap_count": len(set(overlaps)),
                    "overlap_features": "|".join(sorted(set(overlaps))[:10]),
                }
            )
    return out[:400]


def _infer_dtype(values: list[Any]) -> str:
    non_empty = [value for value in values if value not in ("", None)]
    if not non_empty:
        return "empty"
    if all(isinstance(value, datetime) for value in non_empty):
        return "datetime"
    as_text = [str(value).strip() for value in non_empty]
    if all(re.fullmatch(r"-?[0-9]+", text or "") for text in as_text):
        return "int_like"
    if all(re.fullmatch(r"-?[0-9]+(?:[.,][0-9]+)?", text or "") for text in as_text):
        return "float_like"
    return "string"


def _parse_items_list(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        value = ast.literal_eval(raw)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]
    except Exception:
        chunks = [item.strip().strip("'").strip('"') for item in raw.strip("[]").split(",")]
        return [item for item in chunks if item]


def _classify_item_type(name: str) -> str:
    norm = _norm(name)
    if any(keyword in norm for keyword in SERVICE_KEYWORDS):
        return "service"
    if any(keyword in norm for keyword in DRINK_KEYWORDS):
        return "drink"
    return "food"


def _soft_normalize_name(name: str) -> str:
    text = _norm(name)
    text = re.sub(r"[^a-zа-я0-9\\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("ё", "е")
    return text


def _fuzzy_match(value: str, candidates: list[str]) -> tuple[str, float] | None:
    if not candidates:
        return None
    import difflib

    best = ("", 0.0)
    for candidate in candidates:
        score = difflib.SequenceMatcher(None, value, candidate).ratio()
        if score > best[1]:
            best = (candidate, score)
    return best if best[1] >= 0.82 else None


def _layer_to_json(layer: dict[tuple[str, str], float]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for (axis, key), value in sorted(layer.items(), key=lambda item: (item[0][0], item[0][1])):
        out[axis][key] = round(_clip(value), 6)
    return dict(out)


def _flatten_layer(layer: dict[str, Any]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for axis, values in layer.items():
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            out[(str(axis), str(key))] = _safe_float(value)
    return out


def _clip(value: float, min_value: float = -1.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, value))


def _explain_candidate(
    ingredient_score: float,
    method_score: float,
    format_score: float,
    restaurant_score: float,
    repeat_bonus: float,
    novelty_bonus: float,
    venue_boost: float,
    recency_penalty: float,
    diversity_penalty: float,
) -> str:
    parts = []
    if ingredient_score > 0:
        parts.append(f"ingredient_match={ingredient_score:.3f}")
    if method_score > 0:
        parts.append(f"method_cuisine_match={method_score:.3f}")
    if format_score > 0:
        parts.append(f"format_texture_match={format_score:.3f}")
    if restaurant_score > 0:
        parts.append(f"restaurant_context={restaurant_score:.3f}")
    if repeat_bonus > 0:
        parts.append(f"repeat_bonus={repeat_bonus:.3f}")
    if novelty_bonus > 0:
        parts.append(f"novelty={novelty_bonus:.3f}")
    if venue_boost > 0:
        parts.append(f"venue_boost={venue_boost:.3f}")
    penalties = []
    if recency_penalty > 0:
        penalties.append(f"recency_penalty={recency_penalty:.3f}")
    if diversity_penalty > 0:
        penalties.append(f"diversity_penalty={diversity_penalty:.3f}")
    if penalties:
        parts.append("penalties:" + ",".join(penalties))
    return "; ".join(parts) if parts else "neutral_score"


def _write_recommendation_md(path: Path, user_id: str, venue: str, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Recommendation Examples",
        "",
        f"- user_id: `{user_id}`",
        f"- venue: `{venue}`",
        "",
        "## Top recommendations",
    ]
    for row in rows:
        lines.append(f"- #{row['rank']} {row['dish_name']} (`{row['dish_id']}`): {row['score']} -> {row['explanation']}")
    path.write_text("\n".join(lines), encoding="utf-8")


def _safe_iso_datetime(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _canonical_user_id(value: Any) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    normalized = raw.replace(",", ".")
    if re.fullmatch(r"[+-]?[0-9]+(?:\.0+)?", normalized):
        try:
            return str(int(float(normalized)))
        except Exception:
            return raw
    return raw


def _user_id_lookup_keys(value: Any) -> set[str]:
    raw = _clean(value)
    canonical = _canonical_user_id(raw)
    keys: set[str] = set()
    if raw:
        keys.add(raw)
    if canonical:
        keys.add(canonical)
        keys.add(f"{canonical}.0")
    if raw.endswith(".0"):
        keys.add(raw[:-2])
    return {key for key in keys if key}


def _normalize_venue(value: Any) -> str:
    norm = _norm(value)
    compact = re.sub(r"[^a-zа-я0-9]+", "", norm)
    if compact in {"gc", "гц"}:
        return "gc"
    if compact in {"hc", "хц"}:
        return "hc"
    if compact in {"businesslunch", "бизнесланч"} or "ланч" in norm:
        return "business_lunch"
    return norm


def _build_profile_lookup(user_profiles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in user_profiles:
        row_canonical = _canonical_user_id(row.get("user_id"))
        if not row_canonical:
            continue
        normalized = dict(row)
        normalized["user_id_raw"] = _clean(row.get("user_id"))
        normalized["user_id"] = row_canonical
        for key in _user_id_lookup_keys(row.get("user_id")):
            lookup[key] = normalized
    return lookup


def _normalize_purchase_events_for_profile(purchase_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in purchase_events:
        user_canonical = _canonical_user_id(row.get("user_id"))
        venue_raw = _clean(row.get("venue_raw", "")) or _clean(row.get("venue", ""))
        venue_normalized = _normalize_venue(row.get("venue_normalized", "")) or _normalize_venue(venue_raw)
        out.append(
            {
                **row,
                "user_id_raw": _clean(row.get("user_id_raw", "")) or _clean(row.get("user_id", "")),
                "user_id": user_canonical,
                "venue_raw": venue_raw,
                "venue_normalized": venue_normalized,
                "venue": venue_normalized or venue_raw,
            }
        )
    return out


def _user_id_normalization_report(
    real_users: list[dict[str, Any]],
    links: list[dict[str, Any]],
    real_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_values = [_clean(row.get("user_id_raw", "")) for row in real_users if _clean(row.get("user_id_raw", ""))]
    canonical_values = [_canonical_user_id(row.get("user_id")) for row in real_users if _canonical_user_id(row.get("user_id"))]
    linked_values = sorted({_canonical_user_id(row.get("user_id")) for row in links if _canonical_user_id(row.get("user_id"))})
    normalized_changes = len(
        [
            1
            for row in real_users
            if _clean(row.get("user_id_raw", ""))
            and _canonical_user_id(row.get("user_id"))
            and _clean(row.get("user_id_raw", "")) != _canonical_user_id(row.get("user_id"))
        ]
    )
    has_dot_zero = any(value.endswith(".0") for value in canonical_values + linked_values)
    return [
        {"metric": "real_user_rows", "value": len(real_users), "details": ""},
        {"metric": "order_item_rows", "value": len(real_items), "details": ""},
        {"metric": "raw_user_ids_non_empty", "value": len(raw_values), "details": ""},
        {"metric": "canonical_user_ids_unique", "value": len(set(canonical_values)), "details": ""},
        {"metric": "normalization_changes", "value": normalized_changes, "details": ""},
        {"metric": "linked_user_ids_unique", "value": len(linked_values), "details": ""},
        {"metric": "canonical_ids_with_dot_zero", "value": int(has_dot_zero), "details": ""},
        {"metric": "sample_canonical_user_ids", "value": "", "details": "|".join(sorted(set(canonical_values))[:15])},
    ]


def _venue_normalization_report(real_users: list[dict[str, Any]], menu_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    user_raw = [_clean(row.get("venue_raw", "")) for row in real_users if _clean(row.get("venue_raw", ""))]
    user_norm = [_normalize_venue(row.get("venue_normalized", "")) for row in real_users if _normalize_venue(row.get("venue_normalized", ""))]
    menu_raw = [_clean(row.get("venue", "")) for row in menu_nodes if _clean(row.get("venue", ""))]
    menu_norm = [_normalize_venue(row.get("venue", "")) for row in menu_nodes if _normalize_venue(row.get("venue", ""))]
    return [
        {"metric": "user_rows", "value": len(real_users), "details": ""},
        {"metric": "user_venue_raw_unique", "value": len(set(user_raw)), "details": ""},
        {"metric": "user_venue_normalized_unique", "value": len(set(user_norm)), "details": "|".join(sorted(set(user_norm)))},
        {"metric": "menu_node_rows", "value": len(menu_nodes), "details": ""},
        {"metric": "menu_venue_raw_unique", "value": len(set(menu_raw)), "details": ""},
        {"metric": "menu_venue_normalized_unique", "value": len(set(menu_norm)), "details": "|".join(sorted(set(menu_norm)))},
    ]


def _recommend_input_resolution_sample(
    requested_user_id: str,
    canonical_user_id: str,
    requested_venue: str,
    normalized_venue: str,
    available_user_ids: list[str],
    available_venues_for_user: list[str],
) -> list[dict[str, Any]]:
    return [
        {
            "requested_user_id": _clean(requested_user_id),
            "canonical_user_id": canonical_user_id,
            "requested_venue": _clean(requested_venue),
            "normalized_venue": normalized_venue,
            "available_user_ids_sample": "|".join(available_user_ids),
            "available_venues_for_user": "|".join(available_venues_for_user),
        }
    ]


def _write_metric_definitions_report(path: Path) -> None:
    lines = [
        "# Metric Definitions",
        "",
        "- orders_total: all rows in `real_order_headers.csv`.",
        "- linked_orders_count: rows in `real_order_user_link.csv` with non-empty `user_id`.",
        "- order_linkage_coverage: `linked_orders_count / orders_total`.",
        "",
        "- food_items_total: rows in `real_order_item_match.csv` where `item_type=food`.",
        "- matched_food_items_count: food rows with non-empty `matched_dish_id`.",
        "- food_match_coverage: `matched_food_items_count / food_items_total`.",
        "",
        "- purchase_events_total: rows in `real_purchase_events.csv`.",
        "- linked_purchase_events_count: purchase events with non-empty `user_id`.",
        "- purchase_event_linkage_coverage: `linked_purchase_events_count / purchase_events_total`.",
        "",
        "- users_total: unique canonical users in `real_user_identity.csv`.",
        "- users_with_profiles: unique users in `real_user_profiles.json` (or inferred from purchase events during backtest).",
        "- users_in_backtest: users that pass backtest eligibility and are evaluated.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_linkage_metric_breakdown(
    orders_total: int,
    linked_orders_count: int,
    food_items_total: int,
    matched_food_items_count: int,
    purchase_events_total: int,
    linked_purchase_events_count: int,
    users_total: int,
    users_with_profiles: int,
    users_in_backtest: int,
) -> list[dict[str, Any]]:
    return [
        {
            "metric": "orders_total",
            "value": orders_total,
            "numerator": "",
            "denominator": "",
            "definition": "all order headers",
        },
        {
            "metric": "linked_orders_count",
            "value": linked_orders_count,
            "numerator": "",
            "denominator": "",
            "definition": "orders with non-empty linked user",
        },
        {
            "metric": "order_linkage_coverage",
            "value": round(linked_orders_count / max(1, orders_total), 6),
            "numerator": linked_orders_count,
            "denominator": orders_total,
            "definition": "linked_orders_count/orders_total",
        },
        {
            "metric": "food_items_total",
            "value": food_items_total,
            "numerator": "",
            "denominator": "",
            "definition": "food rows in item match",
        },
        {
            "metric": "matched_food_items_count",
            "value": matched_food_items_count,
            "numerator": "",
            "denominator": "",
            "definition": "food rows with matched_dish_id",
        },
        {
            "metric": "food_match_coverage",
            "value": round(matched_food_items_count / max(1, food_items_total), 6),
            "numerator": matched_food_items_count,
            "denominator": food_items_total,
            "definition": "matched_food_items_count/food_items_total",
        },
        {
            "metric": "purchase_events_total",
            "value": purchase_events_total,
            "numerator": "",
            "denominator": "",
            "definition": "all purchase events",
        },
        {
            "metric": "linked_purchase_events_count",
            "value": linked_purchase_events_count,
            "numerator": "",
            "denominator": "",
            "definition": "purchase events with linked user",
        },
        {
            "metric": "purchase_event_linkage_coverage",
            "value": round(linked_purchase_events_count / max(1, purchase_events_total), 6),
            "numerator": linked_purchase_events_count,
            "denominator": purchase_events_total,
            "definition": "linked_purchase_events_count/purchase_events_total",
        },
        {
            "metric": "users_total",
            "value": users_total,
            "numerator": "",
            "denominator": "",
            "definition": "unique users in identity table",
        },
        {
            "metric": "users_with_profiles",
            "value": users_with_profiles,
            "numerator": "",
            "denominator": "",
            "definition": "users with profile rows",
        },
        {
            "metric": "users_in_backtest",
            "value": users_in_backtest,
            "numerator": "",
            "denominator": "",
            "definition": "users evaluated in backtest",
        },
    ]


def _group_backtest_drop_reasons(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in failures:
        reason = _clean(row.get("reason", "")) or "unknown"
        grouped[reason].append(_clean(row.get("user_id", "")))
    out = []
    for reason, users in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        out.append(
            {
                "reason_code": reason,
                "users_count": len(users),
                "user_id_sample": "|".join(sorted({user for user in users if user})[:20]),
            }
        )
    return out


def _collect_pipeline_metric_snapshot(base_path: Path) -> dict[str, float]:
    linkage = _read_metrics_csv(base_path / "audit" / "linkage_quality.csv")
    item_match = _read_metrics_csv(base_path / "audit" / "item_match_summary.csv")
    leakage = _read_metrics_csv(base_path / "audit" / "drink_service_leakage_real.csv")
    backtest = _read_metrics_csv(base_path / "backtest_summary.csv")
    users_with_profiles = _count_users_with_profiles(base_path)
    return {
        "linked_orders_count": _metric_pick(linkage, ("linked_orders_count", "linked_orders"), 0.0),
        "order_linkage_coverage": _metric_pick(linkage, ("order_linkage_coverage", "linkage_coverage"), 0.0),
        "matched_food_items_count": _metric_pick(item_match, ("matched_food_items_count", "matched_food_items"), 0.0),
        "food_match_coverage": _metric_pick(item_match, ("food_match_coverage",), 0.0),
        "purchase_events_total": _metric_pick(leakage, ("purchase_events_total",), 0.0),
        "users_with_profiles": float(users_with_profiles),
        "users_in_backtest": _metric_pick(backtest, ("users_in_backtest",), 0.0),
        "leakage_ratio": _metric_pick(leakage, ("leakage_ratio",), 0.0),
    }


def _build_linkage_delta_summary(before_snapshot: dict[str, Any], after_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    before_snapshot = before_snapshot or {}
    after_snapshot = after_snapshot or {}
    metrics = (
        "linked_orders_count",
        "order_linkage_coverage",
        "matched_food_items_count",
        "food_match_coverage",
        "purchase_events_total",
        "users_with_profiles",
        "users_in_backtest",
        "leakage_ratio",
    )
    rows = []
    for metric in metrics:
        before_value = _safe_float(before_snapshot.get(metric, 0.0))
        after_value = _safe_float(after_snapshot.get(metric, 0.0))
        rows.append(
            {
                "metric": metric,
                "before_value": round(before_value, 6),
                "after_value": round(after_value, 6),
                "delta": round(after_value - before_value, 6),
            }
        )
    return rows


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = _read_json(path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_metrics_csv(path: Path) -> dict[str, float]:
    rows = _read_csv_rows(path)
    out: dict[str, float] = {}
    for row in rows:
        metric = _clean(row.get("metric", ""))
        if metric:
            out[metric] = _safe_float(row.get("value", 0.0))
    return out


def _metric_pick(metric_map: dict[str, float], keys: tuple[str, ...], default: float = 0.0) -> float:
    for key in keys:
        if key in metric_map:
            return _safe_float(metric_map[key])
    return default


def _count_users_with_profiles(base_path: Path) -> int:
    profiles_path = base_path / "real_user_profiles.json"
    if not profiles_path.exists():
        return 0
    try:
        payload = _read_json(profiles_path)
    except Exception:
        return 0
    if not isinstance(payload, list):
        return 0
    return len({str(row.get("user_id")) for row in payload if isinstance(row, dict) and row.get("user_id")})


def _read_single_metric(path: Path, metric_name: str) -> int:
    rows = _read_csv_rows(path)
    for row in rows:
        if _clean(row.get("metric")) == metric_name:
            return _safe_int(row.get("value", 0))
    return 0


def _to_iso_datetime(value: str) -> str:
    text = _clean(value)
    if not text:
        return ""
    candidates = (
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y",
    )
    for fmt in candidates:
        try:
            return datetime.strptime(text, fmt).isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).isoformat()
    except Exception:
        return ""


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value).strip()


def _norm(value: Any) -> str:
    return _clean(value).lower().replace("ё", "е").strip()


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", value)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return digits


def _normalize_card_number(value: str) -> str:
    text = _clean(value)
    if not text:
        return ""
    normalized = text.replace(",", ".")
    if re.fullmatch(r"[+-]?[0-9]+(?:\.0+)?", normalized):
        try:
            return str(int(float(normalized)))
        except Exception:
            return re.sub(r"[^0-9]", "", text)
    return re.sub(r"[^0-9a-zA-Z]", "", text).lower()


def _stable_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_float(value: Any) -> float:
    text = _clean(value).replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    text = _clean(value).replace(" ", "")
    try:
        return int(float(text))
    except Exception:
        return 0


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
