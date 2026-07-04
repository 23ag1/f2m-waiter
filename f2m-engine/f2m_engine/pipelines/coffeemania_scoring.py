from __future__ import annotations

import csv
import hashlib
import heapq
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from f2m_engine.config.taxonomy import load_runtime_taxonomy
from f2m_engine.pipelines.dish_features_stage_a import build_dish_features_stage_a


SUCCESS_STATUSES = {"DELIVERED", "GIVEN_AWAY"}
PROFILE_AXES = {"taste", "ingredient", "cuisine", "format_texture", "context"}
SCORE_COMPONENT_BY_AXIS = {
    "taste": "taste_match",
    "ingredient": "ingredient_match",
    "cuisine": "method_cuisine_match",
    "format_texture": "format_texture_match",
    "context": "context_match",
}
DEFAULT_VENUE = "coffeemania"


@dataclass(frozen=True)
class CoffeemaniaScoringStats:
    dishes_total: int
    sales_rows: int
    distinct_order_items: int
    success_purchase_events: int
    users: int
    profiles: int
    candidates: int
    recommendations: int
    modifier_ids_in_sales: int
    modifier_ids_mapped: int
    backtest_users: int
    hit_at_5: float
    hit_at_10: float
    recall_at_10: float
    mrr: float
    output_dir: str


def run_coffeemania_primary_scoring(
    *,
    dishes: Path | str,
    modifiers: Path | str,
    restrictions: Path | str,
    sales: Path | str,
    out: Path | str,
    taxonomy: Path | str = "docs/runtime_taxonomy_resolved_v1.json",
    top_k: int = 20,
    min_backtest_orders: int = 3,
    max_backtest_users: int = 5000,
    skip_existing_recommendations: bool = False,
) -> CoffeemaniaScoringStats:
    out_path = Path(out)
    audit_dir = out_path / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    dish_rows = _load_result_rows(Path(dishes))
    modifier_rows = _load_result_rows(Path(modifiers))
    restriction_rows = _load_result_rows(Path(restrictions))
    dish_by_sku = _index_by(dish_rows, "sku")
    restriction_departments = _restriction_departments_by_sku(restriction_rows)

    sales_parse = _read_sales(Path(sales))
    stage_input = audit_dir / "coffeemania_stage_a_menu.xlsx"
    _write_stage_a_menu_xlsx(stage_input, dish_rows)
    taxonomy_lock = load_runtime_taxonomy(Path(taxonomy))
    stage_stats = build_dish_features_stage_a(
        menu_path=stage_input,
        output_dir=out_path,
        taxonomy=taxonomy_lock,
    )

    feature_rows = _load_stage_feature_rows(out_path / "dish_feature_values.jsonl")
    _write_csv(out_path / "dish_feature_values.csv", feature_rows)
    _write_csv(out_path / "real_dish_feature_values.csv", feature_rows)

    menu_nodes, candidate_rows = _build_menu_nodes(
        dish_rows=dish_rows,
        sales_dish_ids=sales_parse["sales_dish_ids"],
        restriction_departments=restriction_departments,
    )
    _write_csv(out_path / "menu_nodes.csv", menu_nodes)
    _write_csv(out_path / "real_menu_nodes.csv", menu_nodes)
    _write_csv(audit_dir / "coffeemania_candidate_pool.csv", candidate_rows)

    purchase_events, order_headers, order_items, item_modifiers = _build_purchase_events(
        sales_items=sales_parse["items"],
        dish_by_sku=dish_by_sku,
    )
    _write_csv(out_path / "real_order_headers.csv", order_headers)
    _write_csv(out_path / "real_order_item_raw.csv", order_items)
    _write_csv(out_path / "real_order_item_modifiers.csv", item_modifiers)
    _write_csv(out_path / "real_purchase_events.csv", purchase_events)

    feature_values, profiles, profile_summary = _build_user_profiles(purchase_events, feature_rows)
    _write_csv(out_path / "real_user_feature_values.csv", feature_values)
    _write_json(out_path / "real_user_profiles.json", profiles)
    _write_csv(audit_dir / "user_profile_summary.csv", profile_summary)

    candidates = [row for row in menu_nodes if row["candidate_scope"] == "sales_observed" and _as_bool(row["is_sellable"])]
    if not candidates:
        candidates = [row for row in menu_nodes if row["candidate_scope"] == "sales_observed"]

    scoring_context = _build_scoring_context(
        candidates=candidates,
        feature_rows=feature_rows,
        purchase_events=purchase_events,
    )
    recommendations_path = out_path / f"coffeemania_recommendations_top{top_k}.csv"
    if skip_existing_recommendations and recommendations_path.exists():
        recommendations_written = _count_csv_data_rows(recommendations_path)
        _write_recommendation_sample_from_existing(
            source_path=recommendations_path,
            sample_path=out_path / "recommendations_sample.csv",
            limit=500,
        )
    else:
        recommendations_written = _write_all_recommendations(
            path=recommendations_path,
            sample_path=out_path / "recommendations_sample.csv",
            profiles=profiles,
            purchase_events=purchase_events,
            context=scoring_context,
            top_k=top_k,
        )
    backtest = _run_temporal_backtest(
        audit_dir=audit_dir,
        purchase_events=purchase_events,
        feature_rows=feature_rows,
        candidates=candidates,
        top_k=max(10, top_k),
        min_orders=min_backtest_orders,
        max_users=max_backtest_users,
    )

    modifier_audit = _modifier_catalog_coverage(
        sales_modifier_counts=sales_parse["modifier_counts"],
        modifier_rows=modifier_rows,
    )
    _write_csv(audit_dir / "modifier_catalog_coverage.csv", modifier_audit["rows"])
    _write_csv(audit_dir / "sales_status_distribution.csv", _counter_rows(sales_parse["status_counts"], "status"))
    _write_csv(audit_dir / "data_quality_metrics.csv", _data_quality_rows(sales_parse, stage_stats, profiles, candidates))
    _write_markdown_report(
        path=audit_dir / "coffeemania_data_quality_report.md",
        sales_parse=sales_parse,
        dish_rows=dish_rows,
        feature_rows=feature_rows,
        profiles=profiles,
        candidates=candidates,
        recommendations_written=recommendations_written,
        modifier_audit=modifier_audit,
        backtest=backtest,
        stage_stats=stage_stats,
    )

    return CoffeemaniaScoringStats(
        dishes_total=len(dish_rows),
        sales_rows=sales_parse["sales_rows"],
        distinct_order_items=len(sales_parse["items"]),
        success_purchase_events=len(purchase_events),
        users=len(sales_parse["customer_ids"]),
        profiles=len(profiles),
        candidates=len(candidates),
        recommendations=recommendations_written,
        modifier_ids_in_sales=modifier_audit["sales_modifier_ids"],
        modifier_ids_mapped=modifier_audit["mapped_modifier_ids"],
        backtest_users=backtest["users_in_backtest"],
        hit_at_5=backtest["hit_at_5"],
        hit_at_10=backtest["hit_at_10"],
        recall_at_10=backtest["recall_at_10"],
        mrr=backtest["mrr"],
        output_dir=str(out_path),
    )


def _load_result_rows(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict):
        result = raw.get("result")
        if isinstance(result, list):
            return [row for row in result if isinstance(row, dict)]
        lists = [value for value in raw.values() if isinstance(value, list)]
        if lists:
            return [row for row in max(lists, key=len) if isinstance(row, dict)]
    raise ValueError(f"Cannot find row list in {path}")


def _index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = _clean(row.get(key))
        if value and value not in out:
            out[value] = row
    return out


def _restriction_departments_by_sku(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in rows:
        sku = _clean(row.get("sku"))
        departments = row.get("departments") or []
        if sku:
            out[sku] = sorted({_clean(item) for item in departments if _clean(item)})
    return out


def _read_sales(path: Path) -> dict[str, Any]:
    items: dict[tuple[str, str, str], dict[str, Any]] = {}
    modifiers_by_item: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    modifier_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    channel_counts: Counter[str] = Counter()
    customer_ids: set[str] = set()
    order_ids: set[str] = set()
    sales_dish_ids: set[str] = set()
    sales_rows = 0
    malformed_rows = 0

    for row in _iter_sales_rows(path):
        sales_rows += 1
        customer_id = _clean(row.get("customer_id")).strip('"')
        order_id = _clean(row.get("order_id"))
        dish_id = _clean(row.get("dish_id")).strip('"')
        item_link_id = _clean(row.get("item_link_id")) or f"row-{sales_rows}"
        modifier_id = _clean(row.get("modifier_id"))
        status = _clean(row.get("FulfillmentStatus"))
        channel = _clean(row.get("channel"))
        if not customer_id or not order_id or not dish_id:
            malformed_rows += 1
            continue

        customer_ids.add(customer_id)
        order_ids.add(order_id)
        sales_dish_ids.add(dish_id)
        status_counts[status] += 1
        channel_counts[channel] += 1
        if modifier_id and modifier_id != "0":
            modifier_counts[modifier_id] += 1

        key = (order_id, item_link_id, dish_id)
        if key not in items:
            quantity = _to_decimal(row.get("quantity"))
            price = _to_decimal(row.get("price"))
            items[key] = {
                "customer_id": customer_id,
                "order_id": order_id,
                "order_datetime": _to_iso_datetime(row.get("order_datetime")),
                "status": status,
                "dish_id": dish_id,
                "item_link_id": item_link_id,
                "quantity": str(quantity),
                "price": str(price),
                "line_sum": str(quantity * price),
                "channel": channel,
                "raw_row_count": 0,
            }
        items[key]["raw_row_count"] = int(items[key]["raw_row_count"]) + 1
        if modifier_id and modifier_id != "0":
            modifiers_by_item[key].add(modifier_id)

    for key, item in items.items():
        item["modifier_ids"] = "|".join(sorted(modifiers_by_item.get(key, set()), key=_natural_key))

    return {
        "sales_rows": sales_rows,
        "malformed_rows": malformed_rows,
        "items": items,
        "modifier_counts": modifier_counts,
        "status_counts": status_counts,
        "channel_counts": channel_counts,
        "customer_ids": customer_ids,
        "order_ids": order_ids,
        "sales_dish_ids": sales_dish_ids,
    }


def _iter_sales_rows(path: Path):
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            csv_name = next((name for name in archive.namelist() if name.lower().endswith(".csv")), None)
            if not csv_name:
                raise ValueError(f"No CSV file found in {path}")
            with archive.open(csv_name) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                yield from csv.DictReader(text)
        return
    with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        yield from csv.DictReader(file_obj)


def _write_stage_a_menu_xlsx(path: Path, dish_rows: list[dict[str, Any]]) -> None:
    headers = [
        "Статус / status",
        "Id товара / id",
        "Название / name",
        "Описание",
        "Категория",
        "Состав",
        "Ингредиенты (полные)",
        "Калории / nutrition_facts,calories",
        "Белки / nutrition_facts,proteins",
        "Жиры / nutrition_facts,fats",
        "Углеводы / nutrition_facts,carbohydrates",
        "Вес",
        "Ресторан",
    ]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(headers)
    for dish in dish_rows:
        categories = _category_text(dish)
        ingredients_short = _clean(dish.get("composition")) or _clean(dish.get("siteComposition")) or _clean(dish.get("name"))
        ingredients_full = " ".join(
            value
            for value in [_clean(dish.get("composition")), _strip_markup(_clean(dish.get("siteComposition")))]
            if value
        )
        sheet.append(
            [
                "active",
                _clean(dish.get("sku")),
                _clean(dish.get("name")),
                _clean(dish.get("description")),
                categories,
                ingredients_short,
                ingredients_full,
                dish.get("calories"),
                dish.get("proteins"),
                dish.get("fats"),
                dish.get("carbohydrates"),
                _clean(dish.get("weightStr")),
                DEFAULT_VENUE,
            ]
        )
    workbook.save(path)


def _load_stage_feature_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            if not line.strip():
                continue
            raw = json.loads(line)
            value = raw.get("value_num")
            if value is None and raw.get("value_bool") is not None:
                value = 1.0 if raw.get("value_bool") else 0.0
            rows.append(
                {
                    "dish_id": _clean(raw.get("dish_id")),
                    "axis": _clean(raw.get("axis")),
                    "feature_key": _clean(raw.get("feature_key")),
                    "weight": _safe_float(value),
                    "source": _clean(raw.get("source")),
                    "confidence": _safe_float(raw.get("confidence"), default=1.0),
                    "feature_version": _clean(raw.get("feature_version")),
                    "updated_at": _clean(raw.get("updated_at")),
                }
            )
    return rows


def _build_menu_nodes(
    *,
    dish_rows: list[dict[str, Any]],
    sales_dish_ids: set[str],
    restriction_departments: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for dish in dish_rows:
        sku = _clean(dish.get("sku"))
        if not sku:
            continue
        available_departments = [_clean(item) for item in (dish.get("availableInDepartments") or []) if _clean(item)]
        restricted_departments = restriction_departments.get(sku, [])
        is_sellable = (not bool(dish.get("isOutdated"))) and (
            bool(dish.get("availableForDelivery")) or bool(dish.get("availableForPickUp"))
        )
        candidate_scope = "sales_observed" if sku in sales_dish_ids else "catalog_only"
        row = {
            "node_id": sku,
            "node_name": _clean(dish.get("name")),
            "node_type": "dish",
            "venue": DEFAULT_VENUE,
            "is_sellable": str(bool(is_sellable)).lower(),
            "candidate_scope": candidate_scope,
            "category": _category_text(dish),
            "dish_type": _clean(dish.get("dishType")),
            "price_raw": _clean(dish.get("price")),
            "price_rub_est": _price_rub(dish.get("price")),
            "available_for_delivery": str(bool(dish.get("availableForDelivery"))).lower(),
            "available_for_pickup": str(bool(dish.get("availableForPickUp"))).lower(),
            "is_outdated": str(bool(dish.get("isOutdated"))).lower(),
            "composition_present": str(bool(_clean(dish.get("composition")))).lower(),
            "site_composition_present": str(bool(_clean(dish.get("siteComposition")))).lower(),
            "allergen_ids": "|".join(_clean(item) for item in (dish.get("allergens") or []) if _clean(item)),
            "available_departments_count": len(available_departments),
            "restriction_departments_count": len(restricted_departments),
            "available_departments": "|".join(available_departments),
            "restriction_departments": "|".join(restricted_departments),
        }
        rows.append(row)
        if candidate_scope == "sales_observed":
            candidates.append(row)
    return sorted(rows, key=lambda item: _natural_key(item["node_id"])), sorted(
        candidates, key=lambda item: _natural_key(item["node_id"])
    )


def _build_purchase_events(
    *,
    sales_items: dict[tuple[str, str, str], dict[str, Any]],
    dish_by_sku: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    order_headers: dict[str, dict[str, Any]] = {}
    order_items: list[dict[str, Any]] = []
    item_modifiers: list[dict[str, Any]] = []

    for key, item in sales_items.items():
        order_id, item_link_id, dish_id = key
        dish = dish_by_sku.get(dish_id, {})
        order_headers.setdefault(
            order_id,
            {
                "order_id": order_id,
                "order_datetime": item["order_datetime"],
                "user_id": item["customer_id"],
                "status": item["status"],
                "channel": item["channel"],
                "venue": DEFAULT_VENUE,
                "venue_normalized": DEFAULT_VENUE,
            },
        )
        modifier_ids = [value for value in str(item.get("modifier_ids", "")).split("|") if value]
        order_items.append(
            {
                "order_id": order_id,
                "item_link_id": item_link_id,
                "dish_id": dish_id,
                "dish_name": _clean(dish.get("name")) or dish_id,
                "item_type": "catalog_item",
                "quantity": item["quantity"],
                "price": item["price"],
                "line_sum": item["line_sum"],
                "status": item["status"],
                "channel": item["channel"],
                "modifier_ids": "|".join(modifier_ids),
                "raw_row_count": item["raw_row_count"],
            }
        )
        for modifier_id in modifier_ids:
            item_modifiers.append(
                {
                    "order_id": order_id,
                    "item_link_id": item_link_id,
                    "dish_id": dish_id,
                    "modifier_id": modifier_id,
                    "modifier_mapping_status": "unmapped_in_current_modifiers_json",
                }
            )
        if item["status"] not in SUCCESS_STATUSES:
            continue
        if dish_id not in dish_by_sku:
            continue
        events.append(
            {
                "event_id": _stable_hash(f"{order_id}|{item_link_id}|{dish_id}|{item['customer_id']}"),
                "event_uuid": _stable_hash(f"coffeemania|{order_id}|{item_link_id}|{dish_id}"),
                "source_system": "coffeemania_sales",
                "event_type": "purchase_paid",
                "user_id": item["customer_id"],
                "order_id": order_id,
                "order_datetime": item["order_datetime"],
                "dish_id": dish_id,
                "dish_name": _clean(dish.get("name")) or dish_id,
                "item_link_id": item_link_id,
                "quantity": item["quantity"],
                "price": item["price"],
                "line_sum": item["line_sum"],
                "item_type": "catalog_item",
                "venue_raw": DEFAULT_VENUE,
                "venue_normalized": DEFAULT_VENUE,
                "venue": DEFAULT_VENUE,
                "channel": item["channel"],
                "modifier_ids": "|".join(modifier_ids),
                "modifier_patch_status": "raw_ids_only",
            }
        )
    return (
        sorted(events, key=lambda row: (row["user_id"], row["order_datetime"], row["order_id"], row["dish_id"])),
        sorted(order_headers.values(), key=lambda row: (row["order_datetime"], row["order_id"])),
        sorted(order_items, key=lambda row: (row["order_id"], row["item_link_id"], row["dish_id"])),
        sorted(item_modifiers, key=lambda row: (row["order_id"], row["item_link_id"], row["modifier_id"])),
    )


def _build_user_profiles(
    purchase_events: list[dict[str, Any]],
    feature_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    features_by_dish: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        if row["axis"] in PROFILE_AXES:
            features_by_dish[row["dish_id"]].append(row)

    by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in purchase_events:
        if event.get("user_id"):
            by_user[event["user_id"]].append(event)

    feature_values: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for user_id in sorted(by_user.keys()):
        events = sorted(by_user[user_id], key=lambda row: (row["order_datetime"], row["order_id"], row["dish_id"]))
        latest = _safe_datetime(events[-1]["order_datetime"])
        first = events[0]["order_datetime"]
        long_term: dict[tuple[str, str], float] = defaultdict(float)
        short_term: dict[tuple[str, str], float] = defaultdict(float)
        repeats: dict[str, int] = defaultdict(int)
        order_ids = set()
        for event in events:
            order_ids.add(event["order_id"])
            dish_id = event["dish_id"]
            repeats[dish_id] += 1
            event_dt = _safe_datetime(event["order_datetime"]) or latest
            days = max(0.0, ((latest - event_dt).total_seconds() / 86400.0) if latest and event_dt else 0.0)
            long_decay = math.exp(-days / 120.0)
            short_decay = math.exp(-days / 10.0)
            repeat_boost = 1.0 + min(0.6, (repeats[dish_id] - 1) * 0.12)
            quantity_boost = min(2.0, math.sqrt(max(1.0, _safe_float(event.get("quantity"), default=1.0))))
            for feature in features_by_dish.get(dish_id, []):
                axis = feature["axis"]
                key = feature["feature_key"]
                weight = _safe_float(feature.get("weight"))
                long_term[(axis, key)] += weight * long_decay * 0.20 * repeat_boost * quantity_boost
                short_term[(axis, key)] += weight * short_decay * 0.50 * repeat_boost * quantity_boost

        long_json = _layer_to_json(long_term)
        short_json = _layer_to_json(short_term)
        profiles.append(
            {
                "user_id": user_id,
                "explicit": {},
                "long_term": long_json,
                "short_term": short_json,
                "hard_constraints": [],
                "source": "coffeemania_sales",
                "events_count": len(events),
                "orders_count": len(order_ids),
                "first_event_at": first,
                "latest_event_at": events[-1]["order_datetime"],
            }
        )
        for layer_name, layer in (("long_term", long_json), ("short_term", short_json)):
            for axis, values in layer.items():
                for key, value in values.items():
                    feature_values.append(
                        {
                            "user_id": user_id,
                            "layer": layer_name,
                            "axis": axis,
                            "feature_key": key,
                            "weight": value,
                            "source": "coffeemania_sales",
                        }
                    )
        summary.append(
            {
                "user_id": user_id,
                "events_count": len(events),
                "orders_count": len(order_ids),
                "long_term_features": sum(len(values) for values in long_json.values()),
                "short_term_features": sum(len(values) for values in short_json.values()),
                "top_long_features": _top_feature_text(long_json),
            }
        )
    return (
        sorted(feature_values, key=lambda row: (row["user_id"], row["layer"], row["axis"], row["feature_key"])),
        profiles,
        summary,
    )


def _build_scoring_context(
    *,
    candidates: list[dict[str, Any]],
    feature_rows: list[dict[str, Any]],
    purchase_events: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_by_id = {row["node_id"]: row for row in candidates}
    candidate_ids = set(candidate_by_id)
    feature_index: dict[tuple[str, str], list[tuple[str, str, float]]] = defaultdict(list)
    for row in feature_rows:
        dish_id = row["dish_id"]
        axis = row["axis"]
        if dish_id not in candidate_ids or axis not in SCORE_COMPONENT_BY_AXIS:
            continue
        feature_index[(axis, row["feature_key"])].append((dish_id, SCORE_COMPONENT_BY_AXIS[axis], _safe_float(row["weight"])))

    popularity = Counter(row["dish_id"] for row in purchase_events if row.get("dish_id") in candidate_ids)
    max_popularity = max((math.log1p(value) for value in popularity.values()), default=1.0)
    popularity_prior = {
        dish_id: round(0.15 * math.log1p(count) / max_popularity, 6) for dish_id, count in popularity.items()
    }
    return {
        "candidate_by_id": candidate_by_id,
        "candidate_ids": sorted(candidate_ids, key=_natural_key),
        "feature_index": feature_index,
        "popularity_prior": popularity_prior,
    }


def _write_all_recommendations(
    *,
    path: Path,
    sample_path: Path,
    profiles: list[dict[str, Any]],
    purchase_events: list[dict[str, Any]],
    context: dict[str, Any],
    top_k: int,
) -> int:
    events_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in purchase_events:
        events_by_user[event["user_id"]].append(event)

    fieldnames = _recommendation_fieldnames()
    written = 0
    sample_rows: list[dict[str, Any]] = []
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for profile in profiles:
            rows = _score_user(profile, events_by_user.get(profile["user_id"], []), context, top_k)
            for row in rows:
                writer.writerow(row)
                written += 1
                if len(sample_rows) < 500:
                    sample_rows.append(row)
    _write_csv(sample_path, sample_rows, fieldnames=fieldnames)
    return written


def _score_user(
    profile: dict[str, Any],
    user_events: list[dict[str, Any]],
    context: dict[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    long = _flatten_layer(profile.get("long_term", {}))
    short = _flatten_layer(profile.get("short_term", {}))
    components: dict[str, dict[str, float]] = defaultdict(_empty_components)
    for feature_key, long_value in long.items():
        axis, key = feature_key
        base = (long_value * 0.65) + short.get(feature_key, 0.0)
        if abs(base) < 0.000001:
            continue
        for dish_id, component, weight in context["feature_index"].get((axis, key), []):
            components[dish_id][component] += base * weight
    for feature_key, short_value in short.items():
        if feature_key in long:
            continue
        axis, key = feature_key
        if abs(short_value) < 0.000001:
            continue
        for dish_id, component, weight in context["feature_index"].get((axis, key), []):
            components[dish_id][component] += short_value * weight

    recency = _recency_map(user_events)
    now = max((_safe_datetime(row.get("order_datetime")) for row in user_events), default=None)
    heap: list[tuple[float, int, str, tuple[float, float, float, float, float, float, float, float, float, float, int]]] = []
    for dish_id in context["candidate_ids"]:
        row_components = components.get(dish_id, _empty_components())
        taste_match = row_components["taste_match"]
        ingredient_match = row_components["ingredient_match"]
        method_cuisine_match = row_components["method_cuisine_match"]
        format_texture_match = row_components["format_texture_match"]
        context_match = row_components["context_match"]
        repeat_count, last_dt = recency.get(dish_id, (0, None))
        repeat_bonus = min(0.8, repeat_count * 0.12)
        novelty_bonus = 0.35 if repeat_count == 0 else 0.0
        diversity_penalty = 0.12 * repeat_count
        recency_penalty = 0.0
        if now and last_dt:
            days = max(0.0, (now - last_dt).total_seconds() / 86400.0)
            recency_penalty = max(0.0, 0.6 - (days / 20.0))
        popularity_prior = context["popularity_prior"].get(dish_id, 0.0)
        score = (
            taste_match
            + ingredient_match
            + method_cuisine_match
            + format_texture_match
            + context_match
            + repeat_bonus
            + novelty_bonus
            + popularity_prior
            - recency_penalty
            - diversity_penalty
        )
        tie_breaker = -int(dish_id) if str(dish_id).isdigit() else 0
        payload = (
            taste_match,
            ingredient_match,
            method_cuisine_match,
            format_texture_match,
            context_match,
            repeat_bonus,
            novelty_bonus,
            popularity_prior,
            recency_penalty,
            diversity_penalty,
            repeat_count,
        )
        heap_item = (score, tie_breaker, dish_id, payload)
        if len(heap) < top_k:
            heapq.heappush(heap, heap_item)
        elif heap_item > heap[0]:
            heapq.heapreplace(heap, heap_item)

    rows: list[dict[str, Any]] = []
    top_items = sorted(heap, key=lambda item: (-item[0], -item[1], _natural_key(item[2])))
    for idx, (score, _tie, dish_id, payload) in enumerate(top_items, start=1):
        candidate = context["candidate_by_id"][dish_id]
        (
            taste_match,
            ingredient_match,
            method_cuisine_match,
            format_texture_match,
            context_match,
            repeat_bonus,
            novelty_bonus,
            popularity_prior,
            recency_penalty,
            diversity_penalty,
            repeat_count,
        ) = payload
        row_components = {
            "taste_match": taste_match,
            "ingredient_match": ingredient_match,
            "method_cuisine_match": method_cuisine_match,
            "format_texture_match": format_texture_match,
            "context_match": context_match,
        }
        rows.append(
            {
                "user_id": profile["user_id"],
                "rank": idx,
                "dish_id": dish_id,
                "dish_name": candidate["node_name"],
                "score": round(score, 6),
                "taste_match": round(taste_match, 6),
                "ingredient_match": round(ingredient_match, 6),
                "method_cuisine_match": round(method_cuisine_match, 6),
                "format_texture_match": round(format_texture_match, 6),
                "context_match": round(context_match, 6),
                "repeat_bonus": round(repeat_bonus, 6),
                "novelty_bonus": round(novelty_bonus, 6),
                "popularity_prior": round(popularity_prior, 6),
                "recency_penalty": round(recency_penalty, 6),
                "diversity_penalty": round(diversity_penalty, 6),
                "history_count_same_dish": repeat_count,
                "category": candidate.get("category", ""),
                "price_rub_est": candidate.get("price_rub_est", ""),
                "explanation": _explain_score(
                    row_components,
                    repeat_bonus,
                    novelty_bonus,
                    popularity_prior,
                    recency_penalty,
                    diversity_penalty,
                ),
            }
        )
    return rows


def _run_temporal_backtest(
    *,
    audit_dir: Path,
    purchase_events: list[dict[str, Any]],
    feature_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    top_k: int,
    min_orders: int,
    max_users: int,
) -> dict[str, Any]:
    candidate_ids = {row["node_id"] for row in candidates}
    by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in purchase_events:
        by_user[event["user_id"]].append(event)

    train_events: list[dict[str, Any]] = []
    holdout_by_user: dict[str, set[str]] = {}
    holdout_candidate_hits = 0
    for user_id, events in sorted(by_user.items()):
        if max_users > 0 and len(holdout_by_user) >= max_users:
            break
        by_order: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            by_order[event["order_id"]].append(event)
        if len(by_order) < min_orders:
            continue
        latest_order_id = max(
            by_order.keys(),
            key=lambda order_id: max(_safe_datetime(row["order_datetime"]) or datetime.min for row in by_order[order_id]),
        )
        holdout = by_order[latest_order_id]
        train = [row for row in events if row["order_id"] != latest_order_id]
        if not train:
            continue
        holdout_dishes = {row["dish_id"] for row in holdout}
        if holdout_dishes & candidate_ids:
            holdout_candidate_hits += 1
        holdout_by_user[user_id] = holdout_dishes
        train_events.extend(train)

    _feature_values, train_profiles, _summary = _build_user_profiles(train_events, feature_rows)
    train_context = _build_scoring_context(candidates=candidates, feature_rows=feature_rows, purchase_events=train_events)
    train_events_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in train_events:
        train_events_by_user[event["user_id"]].append(event)

    hit5 = 0
    hit10 = 0
    recall10_sum = 0.0
    mrr_sum = 0.0
    sample_rows: list[dict[str, Any]] = []
    users_eval = 0
    for profile in train_profiles:
        user_id = profile["user_id"]
        holdout_dishes = holdout_by_user.get(user_id)
        if not holdout_dishes:
            continue
        users_eval += 1
        ranked = _score_user(profile, train_events_by_user.get(user_id, []), train_context, top_k)
        ranked_ids = [row["dish_id"] for row in ranked]
        hit_rank = next((idx for idx, dish_id in enumerate(ranked_ids, start=1) if dish_id in holdout_dishes), 0)
        if hit_rank and hit_rank <= 5:
            hit5 += 1
        if hit_rank and hit_rank <= 10:
            hit10 += 1
        recall10_sum += len(set(ranked_ids[:10]) & holdout_dishes) / max(1, len(holdout_dishes))
        mrr_sum += (1.0 / hit_rank) if hit_rank else 0.0
        if len(sample_rows) < 500:
            sample_rows.append(
                {
                    "user_id": user_id,
                    "holdout_dishes": "|".join(sorted(holdout_dishes, key=_natural_key)),
                    "top10": "|".join(ranked_ids[:10]),
                    "hit_rank": hit_rank,
                }
            )

    metrics = {
        "users_in_backtest": users_eval,
        "hit_at_5": round(hit5 / max(1, users_eval), 6),
        "hit_at_10": round(hit10 / max(1, users_eval), 6),
        "recall_at_10": round(recall10_sum / max(1, users_eval), 6),
        "mrr": round(mrr_sum / max(1, users_eval), 6),
        "holdout_candidate_coverage": round(holdout_candidate_hits / max(1, len(holdout_by_user)), 6),
        "max_backtest_users": max_users,
    }
    _write_csv(audit_dir / "backtest_metrics.csv", [{"metric": key, "value": value} for key, value in metrics.items()])
    _write_csv(audit_dir / "backtest_user_sample.csv", sample_rows)
    return metrics


def _modifier_catalog_coverage(
    *,
    sales_modifier_counts: Counter[str],
    modifier_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    catalog_skus = {_clean(row.get("sku")) for row in modifier_rows if _clean(row.get("sku"))}
    catalog_uids = {_clean(row.get("uid")) for row in modifier_rows if _clean(row.get("uid"))}
    rows: list[dict[str, Any]] = []
    mapped = 0
    for modifier_id, count in sales_modifier_counts.most_common():
        mapped_by = ""
        if modifier_id in catalog_skus:
            mapped_by = "sku"
        elif modifier_id in catalog_uids:
            mapped_by = "uid"
        if mapped_by:
            mapped += 1
        rows.append(
            {
                "modifier_id": modifier_id,
                "sales_rows": count,
                "mapped": str(bool(mapped_by)).lower(),
                "mapped_by": mapped_by,
            }
        )
    return {
        "rows": rows,
        "sales_modifier_ids": len(sales_modifier_counts),
        "mapped_modifier_ids": mapped,
    }


def _write_markdown_report(
    *,
    path: Path,
    sales_parse: dict[str, Any],
    dish_rows: list[dict[str, Any]],
    feature_rows: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    recommendations_written: int,
    modifier_audit: dict[str, Any],
    backtest: dict[str, Any],
    stage_stats: Any,
) -> None:
    lines = [
        "# Coffeemania Primary Scoring Data Quality Report",
        "",
        "## Inputs",
        f"- catalog dishes: {len(dish_rows)}",
        f"- sales rows: {sales_parse['sales_rows']}",
        f"- distinct order items after modifier collapse: {len(sales_parse['items'])}",
        f"- malformed sales rows skipped: {sales_parse['malformed_rows']}",
        f"- unique customers: {len(sales_parse['customer_ids'])}",
        f"- unique orders: {len(sales_parse['order_ids'])}",
        f"- sales dish ids covered by catalog sku: {len(sales_parse['sales_dish_ids'])}/{len(sales_parse['sales_dish_ids'])}",
        "",
        "## Feature Build",
        f"- Stage A dishes processed: {stage_stats.dishes_processed}",
        f"- Stage A feature rows: {len(feature_rows)}",
        f"- nutrition parse success rate: {stage_stats.nutrition_parse_success_rate}",
        "",
        "## Profiles And Scoring",
        f"- profiles: {len(profiles)}",
        f"- candidate dishes: {len(candidates)}",
        f"- recommendations written: {recommendations_written}",
        f"- backtest users: {backtest['users_in_backtest']}",
        f"- hit@5: {backtest['hit_at_5']}",
        f"- hit@10: {backtest['hit_at_10']}",
        f"- recall@10: {backtest['recall_at_10']}",
        f"- mrr: {backtest['mrr']}",
        "",
        "## Known Gaps",
        f"- modifier ids in sales: {modifier_audit['sales_modifier_ids']}",
        f"- modifier ids mapped to current modifiers.json: {modifier_audit['mapped_modifier_ids']}",
        "- modifier patches are stored at event-item level as raw ids, but not translated into ingredient changes yet",
        "- restrictions.json is treated as department availability audit, not as user hard constraints",
        "- customer_id is already hashed, so identity joins to CRM/app/iiko still require an external identity map",
        "",
        "## Main Outputs",
        "- `menu_nodes.csv` / `real_menu_nodes.csv`",
        "- `dish_feature_values.csv` / `real_dish_feature_values.csv`",
        "- `real_purchase_events.csv`",
        "- `real_user_profiles.json`",
        "- `coffeemania_recommendations_top*.csv`",
        "- `audit/backtest_metrics.csv`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _data_quality_rows(sales_parse: dict[str, Any], stage_stats: Any, profiles: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"metric": "sales_rows", "value": sales_parse["sales_rows"]},
        {"metric": "distinct_order_items", "value": len(sales_parse["items"])},
        {"metric": "malformed_sales_rows", "value": sales_parse["malformed_rows"]},
        {"metric": "unique_customers", "value": len(sales_parse["customer_ids"])},
        {"metric": "unique_orders", "value": len(sales_parse["order_ids"])},
        {"metric": "stage_a_dishes_processed", "value": stage_stats.dishes_processed},
        {"metric": "stage_a_feature_rows", "value": stage_stats.feature_rows_written},
        {"metric": "profiles", "value": len(profiles)},
        {"metric": "candidates", "value": len(candidates)},
    ]


def _counter_rows(counter: Counter[str], key_name: str) -> list[dict[str, Any]]:
    return [{key_name: key, "count": count} for key, count in counter.most_common()]


def _recommendation_fieldnames() -> list[str]:
    return [
        "user_id",
        "rank",
        "dish_id",
        "dish_name",
        "score",
        "taste_match",
        "ingredient_match",
        "method_cuisine_match",
        "format_texture_match",
        "context_match",
        "repeat_bonus",
        "novelty_bonus",
        "popularity_prior",
        "recency_penalty",
        "diversity_penalty",
        "history_count_same_dish",
        "category",
        "price_rub_est",
        "explanation",
    ]


def _empty_components() -> dict[str, float]:
    return {
        "taste_match": 0.0,
        "ingredient_match": 0.0,
        "method_cuisine_match": 0.0,
        "format_texture_match": 0.0,
        "context_match": 0.0,
    }


def _recency_map(events: list[dict[str, Any]]) -> dict[str, tuple[int, datetime | None]]:
    out: dict[str, tuple[int, datetime | None]] = {}
    for event in events:
        dish_id = event["dish_id"]
        count, latest = out.get(dish_id, (0, None))
        event_dt = _safe_datetime(event.get("order_datetime"))
        if latest is None or (event_dt is not None and event_dt > latest):
            latest = event_dt
        out[dish_id] = (count + 1, latest)
    return out


def _flatten_layer(layer: dict[str, Any]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for axis, values in layer.items():
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            out[(str(axis), str(key))] = _safe_float(value)
    return out


def _layer_to_json(layer: dict[tuple[str, str], float]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for (axis, key), value in sorted(layer.items(), key=lambda item: (item[0][0], item[0][1])):
        clipped = max(-1.0, min(1.0, value))
        if abs(clipped) >= 0.0001:
            out[axis][key] = round(clipped, 6)
    return dict(out)


def _top_feature_text(layer: dict[str, dict[str, float]]) -> str:
    pairs: list[tuple[str, float]] = []
    for axis, values in layer.items():
        for key, value in values.items():
            pairs.append((f"{axis}:{key}", _safe_float(value)))
    pairs.sort(key=lambda item: (-item[1], item[0]))
    return "|".join(f"{key}={value:.3f}" for key, value in pairs[:10])


def _explain_score(
    components: dict[str, float],
    repeat_bonus: float,
    novelty_bonus: float,
    popularity_prior: float,
    recency_penalty: float,
    diversity_penalty: float,
) -> str:
    parts = []
    for key in ("taste_match", "ingredient_match", "method_cuisine_match", "format_texture_match", "context_match"):
        if components.get(key, 0.0) > 0:
            parts.append(f"{key}={components[key]:.3f}")
    if repeat_bonus > 0:
        parts.append(f"repeat_bonus={repeat_bonus:.3f}")
    if novelty_bonus > 0:
        parts.append(f"novelty={novelty_bonus:.3f}")
    if popularity_prior > 0:
        parts.append(f"popularity_prior={popularity_prior:.3f}")
    penalties = []
    if recency_penalty > 0:
        penalties.append(f"recency_penalty={recency_penalty:.3f}")
    if diversity_penalty > 0:
        penalties.append(f"diversity_penalty={diversity_penalty:.3f}")
    if penalties:
        parts.append("penalties:" + ",".join(penalties))
    return "; ".join(parts) if parts else "baseline"


def _category_text(dish: dict[str, Any]) -> str:
    values = []
    for item in dish.get("extendedCategories") or []:
        if isinstance(item, dict) and _clean(item.get("title")):
            values.append(_clean(item.get("title")))
    for item in dish.get("categories") or []:
        if isinstance(item, dict) and _clean(item.get("title")):
            values.append(_clean(item.get("title")))
        elif _clean(item):
            values.append(_clean(item))
    return " | ".join(dict.fromkeys(values))


def _strip_markup(value: str) -> str:
    text = re.sub(r"[*_`#>\[\]()]|https?://\S+", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _price_rub(value: Any) -> str:
    number = _safe_float(value)
    if number <= 0:
        return ""
    return str(round(number / 100.0, 2))


def _to_decimal(value: Any) -> Decimal:
    text = _clean(value)
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def _to_iso_datetime(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text).isoformat()
    except Exception:
        return text


def _safe_datetime(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _natural_key(value: Any) -> tuple[int, str]:
    text = _clean(value)
    if text.isdigit():
        return (0, f"{int(text):020d}")
    return (1, text)


def _write_json(path: Path, rows: Any) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _count_csv_data_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj)
        next(reader, None)
        return sum(1 for _row in reader)


def _write_recommendation_sample_from_existing(*, source_path: Path, sample_path: Path, limit: int) -> None:
    with source_path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        rows = []
        for row in reader:
            rows.append(row)
            if len(rows) >= limit:
                break
    _write_csv(sample_path, rows, fieldnames=_recommendation_fieldnames())
