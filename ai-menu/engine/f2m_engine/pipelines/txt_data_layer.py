from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


MENU_FILE_HINTS = ("ланч", "гц", "хц", "меню")
GENERIC_INGREDIENTS = {
    "вода",
    "соль",
    "масло",
    "соус",
    "овощи",
    "гарнир",
    "добавка",
    "белок",
    "жир",
    "ingredient",
}
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
    "marry pickford",
    "sencha",
    "raff",
    "pina colada",
    "zombi",
    "cuba libre",
    "english breakfast",
)
DRINK_KEYWORDS_EXACT_TOKEN = ("ром",)
SERVICE_KEYWORDS = ("комплимент", "доставка", "сервис", "чаевые")
FOOD_FALSE_DRINK_TOKEN_PREFIXES = ("ромир", "роман")
COMPOSITE_DISH_TARGETS = (
    "кесадилья с курицей",
    "паста ди маре",
    "кур.филе/пюре/перечный соус",
    "стейк и море",
    "тако с лососем",
    "печеный баклажан",
)
METHOD_KEYWORDS = {
    "grilled": ("гриль", "жарен", "шашлык"),
    "fried": ("фрит", "жарен"),
    "baked": ("запеч", "печен"),
    "steamed": ("на пару", "пар"),
    "sous_vide": ("су-вид", "sous"),
    "stewed": ("тушен",),
    "smoked": ("копчен",),
    "raw_or_cured": ("сырая", "сырой", "марин"),
    "creamy": ("сливк", "крем"),
    "crispy": ("хруст", "crispy"),
    "spicy": ("остр", "чили"),
    "soup": ("суп", "уха", "борщ", "гамбо"),
    "salad": ("салат",),
    "bowl": ("поке", "боул"),
    "taco": ("тако",),
    "pasta": ("паста", "пенне", "спагет"),
    "pizza": ("пицц",),
    "burger": ("бургер", "сендвич"),
    "dessert": ("десерт", "тирамису", "торт"),
    "set_or_shared": ("сет", "набор"),
}
RESTAURANT_TAG_HINTS = {
    "business_lunch": ("ланч",),
    "menu_gc": ("гц",),
    "menu_hc": ("хц",),
}
TYPO_FIXES = {
    "ростительное": "растительное",
    "тыквеный": "тыквенный",
    "ингридиенты": "ингредиенты",
    "свин ": "свинина ",
    "репчатый пф": "лук репчатый пф",
}


@dataclass(frozen=True)
class TxtDataLayerStats:
    menu_sources: int
    sellable_dishes: int
    semi_finished_nodes: int
    canonical_ingredients: int
    item_match_coverage: float
    users_with_profiles: int


class _NodeRegistry:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self._index: dict[tuple[Any, ...], str] = {}
        self._counter = 0

    def get_or_create(
        self,
        name: str,
        node_type: str,
        venue: str,
        menu_source: str,
        is_sellable: bool,
        category: str = "",
        tech_text: str = "",
        output_qty: str = "",
    ) -> str:
        norm = _norm(name)
        if node_type in {"semi_finished", "ingredient", "sauce", "garnish"}:
            key = (node_type, norm)
        else:
            key = (node_type, norm, venue, menu_source)
        node_id = self._index.get(key)
        if node_id:
            node = self.nodes[node_id]
            if tech_text and not node.get("tech_text"):
                node["tech_text"] = tech_text
            if output_qty and not node.get("output_qty"):
                node["output_qty"] = output_qty
            if category and not node.get("category"):
                node["category"] = category
            return node_id

        self._counter += 1
        node_id = f"node_{self._counter:05d}"
        self._index[key] = node_id
        self.nodes[node_id] = {
            "node_id": node_id,
            "node_name": name.strip(),
            "norm_name": norm,
            "node_type": node_type,
            "venue": venue,
            "menu_source": menu_source,
            "category": category,
            "tech_text": tech_text,
            "output_qty": output_qty,
            "is_sellable": is_sellable,
        }
        return node_id


def build_text_data_layer(input_dir: Path | str, output_dir: Path | str) -> TxtDataLayerStats:
    input_path = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    audit_dir = out / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    docs = _load_raw_documents(input_path)
    _write_jsonl(out / "raw_documents.jsonl", docs)
    raw_records = _build_raw_records(docs)
    _write_jsonl(out / "raw_records.jsonl", raw_records)

    menu_docs = [doc for doc in docs if _is_menu_file(doc["file_name"])]
    orders_doc = next((doc for doc in docs if "заказ" in _norm(doc["file_name"])), None)
    if not orders_doc:
        raise ValueError("orders txt file not found in input directory")

    nodes, edges, menu_skipped = _parse_menus(menu_docs)
    node_type_corrections = _build_menu_node_type_corrections(nodes)
    _write_csv(out / "menu_nodes.csv", nodes)
    _write_csv(out / "menu_edges.csv", edges)
    _write_csv(audit_dir / "menu_parse_skipped.csv", menu_skipped)
    _write_csv(audit_dir / "menu_node_type_corrections.csv", node_type_corrections)
    _write_menu_parse_summary(audit_dir / "menu_parse_summary.csv", nodes, edges, menu_docs, menu_skipped)

    ingredient_dict, ingredient_aliases = _build_ingredient_dictionary(nodes)
    _write_csv(out / "ingredient_dictionary.csv", ingredient_dict)
    _write_csv(out / "ingredient_aliases.csv", ingredient_aliases)

    expansion_rows, method_rows, restaurant_rows, dish_feature_rows = _build_dish_features(nodes, edges, ingredient_dict)
    _write_csv(out / "dish_flat_ingredients.csv", expansion_rows)
    _write_csv(out / "dish_method_tags.csv", method_rows)
    _write_csv(out / "dish_restaurant_tags.csv", restaurant_rows)
    _write_csv(out / "dish_feature_values.csv", dish_feature_rows)
    _write_json(out / "dish_feature_cache.json", _build_dish_feature_cache(dish_feature_rows, nodes))

    ingredient_stats = _build_ingredient_stats(expansion_rows)
    _write_csv(out / "ingredient_stats.csv", ingredient_stats)

    order_headers, order_item_raw, users, order_user_link, order_parse_summary = _parse_orders_users(orders_doc)
    _write_csv(out / "order_headers.csv", order_headers)
    _write_csv(out / "order_item_raw.csv", order_item_raw)
    _write_csv(out / "user_identity.csv", users)
    _write_csv(out / "order_user_link.csv", order_user_link)
    _write_csv(audit_dir / "order_parse_summary.csv", order_parse_summary)

    dish_lookup = _build_dish_lookup(nodes)
    order_item_match, match_summary, unmatched_items = _match_order_items(order_item_raw, dish_lookup)
    _write_csv(out / "order_item_match.csv", order_item_match)
    _write_csv(audit_dir / "item_match_summary.csv", match_summary)
    _write_csv(audit_dir / "unmatched_order_items.csv", unmatched_items)
    _write_csv(audit_dir / "item_match_review_queue.csv", [row for row in order_item_match if row["is_review_required"]])
    _write_csv(audit_dir / "alias_coverage_summary.csv", _alias_coverage_rows(order_item_match))
    item_domain_confusion = _build_item_domain_confusion(order_item_match=order_item_match, nodes=nodes)
    _write_csv(audit_dir / "item_domain_confusion.csv", item_domain_confusion)
    _write_csv(audit_dir / "top_order_items_match_sample.csv", _build_top_order_items_match_sample(order_item_match, nodes))
    _write_csv(audit_dir / "high_sales_unmatched_items.csv", _build_high_sales_unmatched_items(order_item_match))

    purchase_events = _build_purchase_events(order_headers, order_user_link, order_item_match, nodes)
    _write_csv(out / "purchase_events.csv", purchase_events)
    _write_csv(
        audit_dir / "drink_service_leakage.csv",
        _build_drink_service_leakage(
            purchase_events=purchase_events,
            order_item_match=order_item_match,
            nodes=nodes,
        ),
    )

    composite_sample, missing_provenance = _build_composite_expansion_audits(
        nodes=nodes,
        edges=edges,
        ingredient_dict=ingredient_dict,
    )
    _write_csv(audit_dir / "composite_dish_expansion_sample.csv", composite_sample)
    _write_csv(audit_dir / "missing_ingredient_provenance.csv", missing_provenance)
    _write_csv(
        audit_dir / "method_tag_evidence_sample.csv",
        _build_method_tag_evidence_sample(method_rows=method_rows, nodes=nodes),
    )
    _write_csv(
        audit_dir / "ingredient_alias_top_uncovered.csv",
        _build_ingredient_alias_top_uncovered(order_item_match=order_item_match, ingredient_aliases=ingredient_aliases),
    )
    _write_csv(
        audit_dir / "ingredient_typo_clusters.csv",
        _build_ingredient_typo_clusters(ingredient_aliases=ingredient_aliases),
    )
    _write_csv(
        audit_dir / "ingredient_dictionary_noise.csv",
        _build_ingredient_dictionary_noise(ingredient_dict=ingredient_dict),
    )

    user_feature_rows, user_profiles, profile_summary = _build_user_profiles(
        purchase_events=purchase_events,
        dish_feature_rows=dish_feature_rows,
    )
    _write_csv(out / "user_feature_values.csv", user_feature_rows)
    _write_json(out / "user_profiles.json", user_profiles)
    _write_csv(audit_dir / "profile_summary_by_user.csv", profile_summary)
    _write_csv(audit_dir / "sample_dish_expansion.csv", expansion_rows[:200])
    _write_csv(audit_dir / "sample_user_profiles.csv", _sample_user_profiles(user_profiles))
    _write_csv(
        audit_dir / "user_profile_sanity_sample.csv",
        _build_user_profile_sanity_sample(user_profiles=user_profiles, user_feature_rows=user_feature_rows),
    )
    _write_csv(
        audit_dir / "user_top_items_vs_profile.csv",
        _build_user_top_items_vs_profile(
            purchase_events=purchase_events,
            user_profiles=user_profiles,
            dish_feature_rows=dish_feature_rows,
            nodes=nodes,
        ),
    )

    _write_markdown_demo(
        path=out / "demo_report.md",
        menu_docs=menu_docs,
        nodes=nodes,
        ingredient_dict=ingredient_dict,
        order_item_match=order_item_match,
        expansion_rows=expansion_rows,
        user_profiles=user_profiles,
    )

    sellable_count = len([row for row in nodes if row["is_sellable"] and row["node_type"] == "dish"])
    semi_finished_count = len([row for row in nodes if row["node_type"] == "semi_finished"])
    matched = len([row for row in order_item_match if row["matched_dish_id"]])
    coverage = matched / max(1, len(order_item_match))
    return TxtDataLayerStats(
        menu_sources=len(menu_docs),
        sellable_dishes=sellable_count,
        semi_finished_nodes=semi_finished_count,
        canonical_ingredients=len(ingredient_dict),
        item_match_coverage=round(coverage, 4),
        users_with_profiles=len(user_profiles),
    )


def _load_raw_documents(input_dir: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    txt_files = sorted(input_dir.glob("*.txt"), key=lambda path: path.name.lower())
    for path in txt_files:
        content = path.read_text(encoding="utf-8", errors="replace")
        docs.append(
            {
                "document_id": _stable_id(f"{path.name}|{len(content)}"),
                "file_name": path.name,
                "source_path": str(path),
                "content": content,
            }
        )
    return docs


def _build_raw_records(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc in docs:
        for idx, line in enumerate(doc["content"].splitlines(), start=1):
            rows.append(
                {
                    "document_id": doc["document_id"],
                    "file_name": doc["file_name"],
                    "line_no": idx,
                    "line_text": line.rstrip("\n"),
                }
            )
    return rows


def _parse_menus(docs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    registry = _NodeRegistry()
    edges: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for doc in sorted(docs, key=lambda row: row["file_name"].lower()):
        file_name = doc["file_name"]
        venue = _detect_venue(file_name)
        source = file_name
        current_node_id: str | None = None
        category = _infer_category_from_filename(file_name)
        tech_lines: list[str] = []
        output_qty = ""
        for line_no, raw_line in enumerate(doc["content"].splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("выход"):
                parts = re.split(r"\t+", line, maxsplit=1)
                output_qty = parts[1].strip() if len(parts) > 1 else line.replace("Выход", "").strip()
                if current_node_id:
                    registry.nodes[current_node_id]["output_qty"] = output_qty
                continue

            if _is_tech_text_line(line):
                if current_node_id:
                    tech_lines.append(line)
                    registry.nodes[current_node_id]["tech_text"] = " ".join(tech_lines).strip()
                else:
                    skipped.append(
                        {
                            "file_name": file_name,
                            "line_no": line_no,
                            "line_text": line,
                            "reason": "tech_text_without_current_recipe",
                        }
                    )
                continue

            parts = re.split(r"\t+", line)
            if len(parts) == 1:
                node_name = parts[0].strip()
                node_type = _classify_node_type(node_name=node_name, is_header=True)
                current_node_id = registry.get_or_create(
                    name=node_name,
                    node_type=node_type,
                    venue=venue,
                    menu_source=source,
                    is_sellable=node_type in {"dish", "set", "drink", "service", "sauce", "garnish"},
                    category=category,
                    tech_text="",
                    output_qty=output_qty,
                )
                tech_lines = []
                output_qty = ""
                continue

            component_name = parts[0].strip()
            qty_text = parts[1].strip() if len(parts) > 1 else ""
            if not current_node_id:
                skipped.append(
                    {
                        "file_name": file_name,
                        "line_no": line_no,
                        "line_text": line,
                        "reason": "component_without_parent",
                    }
                )
                continue
            child_type = _classify_node_type(node_name=component_name, is_header=False)
            child_node_id = registry.get_or_create(
                name=component_name,
                node_type=child_type,
                venue=venue,
                menu_source=source,
                is_sellable=child_type in {"dish", "set", "drink", "service"},
            )
            edges.append(
                {
                    "edge_id": _stable_id(f"{current_node_id}|{child_node_id}|{qty_text}|{file_name}|{line_no}"),
                    "parent_node_id": current_node_id,
                    "child_node_id": child_node_id,
                    "qty_text": qty_text,
                    "qty_num": _parse_number(qty_text),
                    "source_file": file_name,
                    "source_line_no": line_no,
                }
            )

    nodes = sorted(registry.nodes.values(), key=lambda row: row["node_id"])
    edges = sorted(edges, key=lambda row: row["edge_id"])
    return nodes, edges, skipped


def _build_ingredient_dictionary(nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ingredient_rows = [row for row in nodes if row["node_type"] in {"ingredient", "sauce", "garnish"}]
    alias_rows: list[dict[str, Any]] = []
    canonical_index: dict[str, dict[str, Any]] = {}

    for row in ingredient_rows:
        alias = row["node_name"]
        normalized = _normalize_ingredient(alias)
        canonical_name = _apply_typo_fixes(normalized)
        ingredient_id = f"ing_{_stable_id(canonical_name)[:10]}"
        parent_group = _ingredient_group(canonical_name)
        is_generic = canonical_name in GENERIC_INGREDIENTS
        entry = canonical_index.get(ingredient_id)
        if not entry:
            entry = {
                "ingredient_id": ingredient_id,
                "canonical_name": canonical_name,
                "ingredient_group": parent_group,
                "parent_group": parent_group,
                "is_generic": is_generic,
                "allergen_gluten": _contains_any(canonical_name, ("мука", "хлеб", "пшениц")),
                "allergen_lactose": _contains_any(canonical_name, ("молок", "сыр", "сливк", "сметан")),
                "allergen_nuts": _contains_any(canonical_name, ("орех",)),
                "allergen_egg": _contains_any(canonical_name, ("яйц",)),
                "allergen_soy": _contains_any(canonical_name, ("соев",)),
                "allergen_fish_seafood": _contains_any(canonical_name, ("рыб", "кревет", "мид", "устриц", "лангуст")),
            }
            canonical_index[ingredient_id] = entry
        alias_rows.append(
            {
                "alias": alias,
                "alias_normalized": normalized,
                "ingredient_id": ingredient_id,
            }
        )

    ingredients = sorted(canonical_index.values(), key=lambda row: row["ingredient_id"])
    alias_rows = sorted(alias_rows, key=lambda row: (row["ingredient_id"], row["alias_normalized"], row["alias"]))
    return ingredients, alias_rows


def _build_dish_features(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    ingredient_dict: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    node_by_id = {row["node_id"]: row for row in nodes}
    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        children_by_parent.setdefault(edge["parent_node_id"], []).append(edge)
    ingredient_map = {row["canonical_name"]: row["ingredient_id"] for row in ingredient_dict}
    generic_ids = {row["ingredient_id"] for row in ingredient_dict if row["is_generic"]}

    sellable_dishes = [
        row
        for row in nodes
        if row["is_sellable"] and row["node_type"] in {"dish", "set", "sauce", "garnish", "drink", "service"}
    ]
    expansion_rows: list[dict[str, Any]] = []
    method_rows: list[dict[str, Any]] = []
    restaurant_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []

    for dish in sorted(sellable_dishes, key=lambda row: row["node_id"]):
        atomic = _expand_atomic_ingredients(
            node_id=dish["node_id"],
            node_by_id=node_by_id,
            children_by_parent=children_by_parent,
            path=set(),
        )
        total_weight = sum(value for _, value in atomic) or 1.0
        ingredient_scores: dict[str, float] = {}
        for ingredient_name, weight in atomic:
            canonical = _apply_typo_fixes(_normalize_ingredient(ingredient_name))
            ingredient_id = ingredient_map.get(canonical)
            if not ingredient_id:
                continue
            ingredient_scores[ingredient_id] = ingredient_scores.get(ingredient_id, 0.0) + weight
        for ingredient_id, weight in sorted(ingredient_scores.items()):
            share = weight / total_weight
            importance = share
            expansion_rows.append(
                {
                    "dish_id": dish["node_id"],
                    "dish_name": dish["node_name"],
                    "ingredient_id": ingredient_id,
                    "ingredient_name": _ingredient_name_by_id(ingredient_dict, ingredient_id),
                    "weight_g_est": round(weight, 4),
                    "weight_share": round(share, 6),
                    "importance_weight": round(importance, 6),
                    "is_generic": ingredient_id in generic_ids,
                }
            )
            feature_rows.append(
                {
                    "dish_id": dish["node_id"],
                    "dish_name": dish["node_name"],
                    "axis": "ingredient",
                    "source_layer": "ingredient_tags",
                    "feature_key": ingredient_id,
                    "weight": round(importance, 6),
                    "evidence_text": "ingredient_expansion",
                    "confidence": 1.0,
                }
            )

        text = f"{dish.get('node_name','')} {dish.get('tech_text','')}".lower()
        for tag, keywords in METHOD_KEYWORDS.items():
            hit = next((key for key in keywords if key in text), None)
            if not hit:
                continue
            method_rows.append(
                {
                    "dish_id": dish["node_id"],
                    "dish_name": dish["node_name"],
                    "method_tag": tag,
                    "evidence_text": hit,
                    "confidence": 0.9,
                }
            )
            axis = "format_texture" if tag in {"soup", "salad", "bowl", "taco", "pasta", "pizza", "burger", "dessert"} else "method"
            feature_rows.append(
                {
                    "dish_id": dish["node_id"],
                    "dish_name": dish["node_name"],
                    "axis": axis,
                    "source_layer": "method_tags",
                    "feature_key": tag,
                    "weight": 1.0,
                    "evidence_text": hit,
                    "confidence": 0.9,
                }
            )

        venue_tag = f"venue:{dish['venue']}"
        source_tag = f"source:{dish['menu_source']}"
        for restaurant_tag, evidence in (
            (venue_tag, dish["venue"]),
            (source_tag, dish["menu_source"]),
        ):
            restaurant_rows.append(
                {
                    "dish_id": dish["node_id"],
                    "dish_name": dish["node_name"],
                    "restaurant_tag": restaurant_tag,
                    "evidence_text": evidence,
                    "confidence": 1.0,
                }
            )
            feature_rows.append(
                {
                    "dish_id": dish["node_id"],
                    "dish_name": dish["node_name"],
                    "axis": "restaurant",
                    "source_layer": "restaurant_tags",
                    "feature_key": restaurant_tag,
                    "weight": 1.0,
                    "evidence_text": evidence,
                    "confidence": 1.0,
                }
            )
        for tag, hints in RESTAURANT_TAG_HINTS.items():
            joined = f"{dish['menu_source']} {dish['venue']}".lower()
            if any(h in joined for h in hints):
                feature_rows.append(
                    {
                        "dish_id": dish["node_id"],
                        "dish_name": dish["node_name"],
                        "axis": "restaurant",
                        "source_layer": "restaurant_tags",
                        "feature_key": tag,
                        "weight": 1.0,
                        "evidence_text": tag,
                        "confidence": 0.9,
                    }
                )
    return (
        sorted(expansion_rows, key=lambda row: (row["dish_id"], row["ingredient_id"])),
        sorted(method_rows, key=lambda row: (row["dish_id"], row["method_tag"])),
        sorted(restaurant_rows, key=lambda row: (row["dish_id"], row["restaurant_tag"])),
        sorted(feature_rows, key=lambda row: (row["dish_id"], row["axis"], row["feature_key"])),
    )


def _build_ingredient_stats(expansion_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dishes = sorted({row["dish_id"] for row in expansion_rows})
    n_dishes = max(1, len(dishes))
    df: dict[str, set[str]] = {}
    for row in expansion_rows:
        df.setdefault(row["ingredient_id"], set()).add(row["dish_id"])
    rows: list[dict[str, Any]] = []
    for ingredient_id, dish_set in sorted(df.items()):
        doc_freq = len(dish_set)
        idf = math.log((n_dishes + 1) / (doc_freq + 1)) + 1.0
        rows.append(
            {
                "ingredient_id": ingredient_id,
                "doc_frequency": doc_freq,
                "idf_weight": round(idf, 6),
            }
        )
    return rows


def _parse_orders_users(doc: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    lines = [line.rstrip() for line in doc["content"].splitlines()]
    orders_section: list[str] = []
    users_section: list[str] = []
    mode = "none"
    for line in lines:
        norm = _norm(line)
        if "пример данных заказ" in norm:
            mode = "orders"
            continue
        if "пример данных пользователь" in norm:
            mode = "users"
            continue
        if mode == "orders":
            orders_section.append(line)
        elif mode == "users":
            users_section.append(line)

    order_headers = _parse_order_headers(orders_section)
    users = _parse_user_rows(users_section)
    order_user_link = _build_order_user_link(users, order_headers)
    order_item_raw = _parse_order_items(order_headers)
    summary = [
        {"metric": "orders", "value": len(order_headers)},
        {"metric": "users", "value": len(users)},
        {"metric": "order_items_raw", "value": len(order_item_raw)},
        {"metric": "order_user_links", "value": len(order_user_link)},
    ]
    return order_headers, order_item_raw, users, order_user_link, summary


def _parse_order_headers(lines: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        if line.lower().startswith("дата,"):
            continue
        if not re.match(r"^\d{2}\.\d{2}\.\d{4},", line):
            continue
        parts = list(csv.reader([line]))[0]
        if len(parts) < 6:
            continue
        date_s, time_s, order_no, guest_count, _, dishes_raw = parts[:6]
        dt = _parse_datetime(date_s, time_s)
        rows.append(
            {
                "order_id": str(order_no).strip(),
                "order_date": date_s.strip(),
                "order_time": time_s.strip(),
                "order_datetime": dt.isoformat() if dt else "",
                "guest_count": _safe_int(guest_count),
                "dishes_raw": dishes_raw.strip(),
                "source_file": "данные заказ-пользователи.txt",
            }
        )
    return sorted(rows, key=lambda row: (row["order_datetime"], row["order_id"]))


def _parse_user_rows(lines: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    headers: list[str] | None = None
    for line in lines:
        if not line.strip():
            continue
        if headers is None:
            headers = [item.strip() for item in line.split("\t")]
            continue
        parts = [item.strip() for item in line.split("\t")]
        if len(parts) < 3:
            continue
        row = dict(zip(headers, parts))
        order_id = row.get("Номер заказа", "").strip()
        phone = row.get("Телефон", "").strip()
        rows.append(
            {
                "user_id": row.get("Id клиента", "").strip(),
                "order_id": order_id,
                "phone_normalized_hash": _stable_id(_normalize_phone(phone)),
                "phone_normalized": _normalize_phone(phone),
                "visit_time": row.get("Время визита", "").strip(),
                "venue": row.get("Заведение", "").strip(),
                "check_amount": _safe_float(row.get("Сумма чека", "")),
                "guest_count_hint": _safe_int(row.get("Чеков", "")),
                "raw": row,
            }
        )
    return sorted(rows, key=lambda row: (row["order_id"], row["user_id"]))


def _build_order_user_link(users: list[dict[str, Any]], order_headers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    links: dict[tuple[str, str], dict[str, Any]] = {}
    for row in users:
        key = (row["order_id"], row["user_id"])
        links[key] = {"order_id": row["order_id"], "user_id": row["user_id"], "link_source": "crm_user_file"}
    for order in order_headers:
        has_link = any(key[0] == order["order_id"] for key in links.keys())
        if has_link:
            continue
        fallback_user = f"guest_{order['order_id']}"
        key = (order["order_id"], fallback_user)
        links[key] = {
            "order_id": order["order_id"],
            "user_id": fallback_user,
            "link_source": "order_fallback_guest",
        }
    return sorted(links.values(), key=lambda row: (row["order_id"], row["user_id"]))


def _parse_order_items(order_headers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order in order_headers:
        raw = order["dishes_raw"]
        parsed: list[str] = []
        try:
            value = ast.literal_eval(raw)
            if isinstance(value, list):
                parsed = [str(item) for item in value]
            else:
                parsed = [str(value)]
        except Exception:
            parsed = [item.strip().strip("'").strip('"') for item in raw.strip("[]").split(",") if item.strip()]
        for idx, item in enumerate(parsed, start=1):
            item_type = _classify_order_item_type(item)
            rows.append(
                {
                    "order_id": order["order_id"],
                    "line_no": idx,
                    "item_name_raw": item,
                    "item_name_norm": _norm(item),
                    "item_type": item_type,
                }
            )
    return sorted(rows, key=lambda row: (row["order_id"], row["line_no"]))


def _build_dish_lookup(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in nodes:
        if not row["is_sellable"]:
            continue
        if row["node_type"] in {"semi_finished", "ingredient"}:
            continue
        key = _norm(row["node_name"])
        lookup[key] = row
    return lookup


def _match_order_items(
    order_items: list[dict[str, Any]],
    dish_lookup: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for row in order_items:
        if row["item_type"] != "food":
            rows.append(
                {
                    **row,
                    "matched_dish_id": "",
                    "match_method": "not_food",
                    "match_confidence": 0.0,
                    "is_review_required": False,
                }
            )
            continue
        norm_name = row["item_name_norm"]
        matched = dish_lookup.get(norm_name)
        method = "exact"
        confidence = 1.0
        if not matched:
            alias_key = _normalize_ingredient(norm_name)
            matched = dish_lookup.get(alias_key)
            method = "alias"
            confidence = 0.92 if matched else 0.0
        if not matched:
            fuzzy = _fuzzy_match(norm_name, list(dish_lookup.keys()))
            if fuzzy:
                matched = dish_lookup[fuzzy[0]]
                method = "fuzzy"
                confidence = fuzzy[1]
        if not matched:
            unresolved.append(
                {
                    "order_id": row["order_id"],
                    "line_no": row["line_no"],
                    "item_name_raw": row["item_name_raw"],
                    "item_name_norm": norm_name,
                    "reason": "unresolved_match",
                }
            )
        rows.append(
            {
                **row,
                "matched_dish_id": matched["node_id"] if matched else "",
                "match_method": method if matched else "unresolved",
                "match_confidence": round(confidence, 4),
                "is_review_required": (not matched) or (method == "fuzzy" and confidence < 0.9),
            }
        )

    total_food = len([row for row in rows if row["item_type"] == "food"])
    matched_food = len([row for row in rows if row["item_type"] == "food" and row["matched_dish_id"]])
    summary = [
        {"metric": "total_items", "value": len(rows)},
        {"metric": "food_items", "value": total_food},
        {"metric": "matched_food_items", "value": matched_food},
        {"metric": "match_coverage", "value": round(matched_food / max(1, total_food), 6)},
        {"metric": "unmatched_food_items", "value": total_food - matched_food},
        {"metric": "matched_exact", "value": len([item for item in rows if item["match_method"] == "exact"])},
        {"metric": "matched_alias", "value": len([item for item in rows if item["match_method"] == "alias"])},
        {"metric": "matched_fuzzy", "value": len([item for item in rows if item["match_method"] == "fuzzy"])},
        {"metric": "needs_manual_review", "value": len([item for item in rows if item["is_review_required"]])},
    ]
    return rows, summary, unresolved


def _build_purchase_events(
    order_headers: list[dict[str, Any]],
    order_user_link: list[dict[str, Any]],
    order_item_match: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    order_to_user: dict[str, str] = {}
    for link in order_user_link:
        order_to_user[link["order_id"]] = link["user_id"]
    order_time = {row["order_id"]: row["order_datetime"] for row in order_headers}
    node_by_id = {row["node_id"]: row for row in nodes}
    events: list[dict[str, Any]] = []
    for row in order_item_match:
        if row["item_type"] != "food":
            continue
        if not row["matched_dish_id"]:
            continue
        user_id = order_to_user.get(row["order_id"])
        if not user_id:
            continue
        dish = node_by_id.get(row["matched_dish_id"])
        if not dish:
            continue
        events.append(
            {
                "purchase_event_id": _stable_id(f"{row['order_id']}|{row['line_no']}|{user_id}"),
                "user_id": user_id,
                "order_id": row["order_id"],
                "order_datetime": order_time.get(row["order_id"], ""),
                "dish_id": row["matched_dish_id"],
                "dish_name": dish["node_name"],
                "dish_node_type": dish["node_type"],
                "venue": dish["venue"],
                "source_menu": dish["menu_source"],
            }
        )
    return sorted(events, key=lambda row: (row["user_id"], row["order_datetime"], row["order_id"], row["dish_id"]))


def _build_user_profiles(
    purchase_events: list[dict[str, Any]],
    dish_feature_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    feature_by_dish: dict[str, list[dict[str, Any]]] = {}
    for row in dish_feature_rows:
        feature_by_dish.setdefault(row["dish_id"], []).append(row)

    by_user: dict[str, list[dict[str, Any]]] = {}
    for row in purchase_events:
        by_user.setdefault(row["user_id"], []).append(row)

    all_rows: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for user_id in sorted(by_user.keys()):
        events = sorted(by_user[user_id], key=lambda row: (row["order_datetime"], row["order_id"], row["dish_id"]))
        long_term: dict[tuple[str, str], float] = {}
        short_term: dict[tuple[str, str], float] = {}
        latest_dt = _safe_datetime(events[-1]["order_datetime"])
        for idx, event in enumerate(events):
            event_dt = _safe_datetime(event["order_datetime"]) or latest_dt
            days = max(0.0, ((latest_dt - event_dt).total_seconds() / 86400.0) if latest_dt and event_dt else 0.0)
            decay_long = math.exp(-days / 120.0)
            decay_short = math.exp(-days / 7.0)
            repeat_bonus = 1.0 + (0.1 * idx / max(1, len(events)))
            context_tags = _context_from_order_time(event_dt, venue=event["venue"])
            for tag in context_tags:
                long_term[("context", tag)] = long_term.get(("context", tag), 0.0) + (0.05 * decay_long)
                short_term[("context", tag)] = short_term.get(("context", tag), 0.0) + (0.2 * decay_short)

            for feature in feature_by_dish.get(event["dish_id"], []):
                axis = feature["axis"]
                key = feature["feature_key"]
                if axis == "ingredient":
                    if "ing_" in key and feature["weight"] <= 0:
                        continue
                weight = float(feature["weight"])
                long_term[(axis, key)] = long_term.get((axis, key), 0.0) + (weight * 0.18 * decay_long * repeat_bonus)
                short_term[(axis, key)] = short_term.get((axis, key), 0.0) + (weight * 0.55 * decay_short * repeat_bonus)

        for (axis, key), value in sorted(long_term.items(), key=lambda x: (x[0][0], x[0][1])):
            all_rows.append(
                {
                    "user_id": user_id,
                    "layer": "long_term",
                    "axis": axis,
                    "feature_key": key,
                    "weight": round(_clip(value), 6),
                    "event_count": len(events),
                }
            )
        for (axis, key), value in sorted(short_term.items(), key=lambda x: (x[0][0], x[0][1])):
            all_rows.append(
                {
                    "user_id": user_id,
                    "layer": "short_term",
                    "axis": axis,
                    "feature_key": key,
                    "weight": round(_clip(value), 6),
                    "event_count": len(events),
                }
            )

        profile = {
            "user_id": user_id,
            "explicit": {},
            "long_term": _layer_to_json(long_term),
            "short_term": _layer_to_json(short_term),
            "meta": {
                "orders_count": len(events),
                "last_order_at": events[-1]["order_datetime"],
            },
        }
        profiles.append(profile)
        summary.append(
            {
                "user_id": user_id,
                "orders_count": len(events),
                "long_term_features": len(long_term),
                "short_term_features": len(short_term),
            }
        )

    all_rows = sorted(all_rows, key=lambda row: (row["user_id"], row["layer"], row["axis"], row["feature_key"]))
    profiles = sorted(profiles, key=lambda row: row["user_id"])
    return all_rows, profiles, summary


def _write_markdown_demo(
    path: Path,
    menu_docs: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    ingredient_dict: list[dict[str, Any]],
    order_item_match: list[dict[str, Any]],
    expansion_rows: list[dict[str, Any]],
    user_profiles: list[dict[str, Any]],
) -> None:
    sellable = [row for row in nodes if row["is_sellable"] and row["node_type"] == "dish"]
    semi_finished = [row for row in nodes if row["node_type"] == "semi_finished"]
    food_matches = [row for row in order_item_match if row["item_type"] == "food"]
    matched_food = [row for row in food_matches if row["matched_dish_id"]]
    coverage = len(matched_food) / max(1, len(food_matches))

    dish_examples: list[str] = []
    dish_ids = []
    for row in expansion_rows:
        if row["dish_id"] not in dish_ids:
            dish_ids.append(row["dish_id"])
    for dish_id in dish_ids[:10]:
        ingredients = [row["ingredient_name"] for row in expansion_rows if row["dish_id"] == dish_id][:8]
        name = next((row["dish_name"] for row in expansion_rows if row["dish_id"] == dish_id), dish_id)
        dish_examples.append(f"- {name}: {', '.join(ingredients)}")

    profile_examples: list[str] = []
    for profile in user_profiles[:10]:
        user_id = profile["user_id"]
        long_features = profile.get("long_term", {})
        pairs: list[tuple[str, float]] = []
        for axis, tags in long_features.items():
            for key, value in tags.items():
                pairs.append((f"{axis}:{key}", float(value)))
        pairs = sorted(pairs, key=lambda x: (-x[1], x[0]))[:6]
        profile_examples.append(f"- user {user_id}: {', '.join(f'{k}={round(v,3)}' for k, v in pairs)}")

    text = [
        "# Demo Report",
        "",
        f"- menu_sources_processed: {len(menu_docs)}",
        f"- sellable_dishes_found: {len(sellable)}",
        f"- semi_finished_nodes_found: {len(semi_finished)}",
        f"- canonical_ingredients_found: {len(ingredient_dict)}",
        f"- order_item_match_coverage: {round(coverage, 4)}",
        "",
        "## 10 примеров полностью раскрытых блюд",
        *dish_examples,
        "",
        "## 10 примеров профилей пользователей",
        *profile_examples,
        "",
    ]
    path.write_text("\n".join(text), encoding="utf-8")


def _sample_user_profiles(user_profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for profile in user_profiles[:10]:
        user_id = profile["user_id"]
        pairs: list[tuple[str, float]] = []
        for axis, tags in profile.get("long_term", {}).items():
            for key, value in tags.items():
                pairs.append((f"{axis}:{key}", float(value)))
        pairs = sorted(pairs, key=lambda x: (-x[1], x[0]))[:8]
        rows.append(
            {
                "user_id": user_id,
                "top_long_term_features": "|".join(f"{k}={round(v,3)}" for k, v in pairs),
                "orders_count": profile.get("meta", {}).get("orders_count", 0),
            }
        )
    return rows


def _build_dish_feature_cache(feature_rows: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node_by_id = {row["node_id"]: row for row in nodes}
    grouped: dict[str, dict[str, Any]] = {}
    for row in feature_rows:
        dish_id = row["dish_id"]
        cache = grouped.setdefault(
            dish_id,
            {
                "dish_id": dish_id,
                "dish_name": node_by_id.get(dish_id, {}).get("node_name", dish_id),
                "features": {},
            },
        )
        axis = row["axis"]
        cache["features"].setdefault(axis, {})[row["feature_key"]] = row["weight"]
    return [grouped[key] for key in sorted(grouped.keys())]


def _expand_atomic_ingredients(
    node_id: str,
    node_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str, list[dict[str, Any]]],
    path: set[str],
) -> list[tuple[str, float]]:
    if node_id in path:
        return []
    path = set(path)
    path.add(node_id)
    node = node_by_id.get(node_id)
    if not node:
        return []
    children = children_by_parent.get(node_id, [])
    if not children:
        if node["node_type"] in {"ingredient", "sauce", "garnish"}:
            return [(node["node_name"], 1.0)]
        return []
    result: list[tuple[str, float]] = []
    for edge in children:
        child = node_by_id.get(edge["child_node_id"])
        if not child:
            continue
        factor = edge["qty_num"] if edge["qty_num"] is not None else 1.0
        if child["node_type"] in {"ingredient", "sauce", "garnish"}:
            result.append((child["node_name"], factor))
            continue
        nested = _expand_atomic_ingredients(
            node_id=child["node_id"],
            node_by_id=node_by_id,
            children_by_parent=children_by_parent,
            path=path,
        )
        for ingredient_name, weight in nested:
            result.append((ingredient_name, weight * factor))
    return result


def _parse_datetime(date_s: str, time_s: str) -> datetime | None:
    try:
        return datetime.strptime(f"{date_s.strip()} {time_s.strip()}", "%d.%m.%Y %H:%M")
    except ValueError:
        return None


def _safe_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _context_from_order_time(dt: datetime | None, venue: str) -> list[str]:
    tags: list[str] = []
    if dt:
        if dt.hour < 11:
            tags.append("morning")
        elif dt.hour < 16:
            tags.append("lunch")
        else:
            tags.append("dinner")
        tags.append("weekend" if dt.weekday() >= 5 else "weekday")
    if venue:
        tags.append(f"venue:{_norm(venue)}")
    return sorted(set(tags))


def _is_menu_file(file_name: str) -> bool:
    norm = _norm(file_name)
    if "заказ" in norm:
        return False
    return any(hint in norm for hint in MENU_FILE_HINTS)


def _detect_venue(file_name: str) -> str:
    norm = _norm(file_name)
    if "гц" in norm:
        return "gc"
    if "хц" in norm:
        return "hc"
    if "ланч" in norm:
        return "business_lunch"
    return "unknown"


def _infer_category_from_filename(file_name: str) -> str:
    norm = _norm(file_name)
    if "ланч" in norm:
        return "lunch"
    if "соус" in norm:
        return "sauce"
    return "main_menu"


def _classify_node_type(node_name: str, is_header: bool) -> str:
    norm = _norm(node_name)
    if "п/ф" in norm or "п\\ф" in norm:
        return "semi_finished"
    if "полуф" in norm:
        return "semi_finished"
    if "сет" in norm or "набор" in norm:
        return "set"
    if any(word in norm for word in SERVICE_KEYWORDS):
        return "service"
    if _is_drink_keyword_match(norm):
        return "drink"
    if "соус" in norm and not is_header:
        return "sauce"
    if "гарнир" in norm:
        return "garnish"
    if is_header:
        return "dish"
    return "ingredient"


def _classify_order_item_type(item_name: str) -> str:
    norm = _norm(item_name)
    if any(word in norm for word in SERVICE_KEYWORDS):
        return "service"
    if any(word in norm for word in DRINK_KEYWORDS):
        return "drink"
    return "food"


def _legacy_classify_node_type(node_name: str, is_header: bool) -> str:
    norm = _norm(node_name)
    if "п/ф" in norm or "п\\ф" in norm:
        return "semi_finished"
    if "полуф" in norm:
        return "semi_finished"
    if "сет" in norm or "набор" in norm:
        return "set"
    if any(word in norm for word in SERVICE_KEYWORDS):
        return "service"
    if any(word in norm for word in DRINK_KEYWORDS):
        return "drink"
    if "соус" in norm and not is_header:
        return "sauce"
    if "гарнир" in norm:
        return "garnish"
    if is_header:
        return "dish"
    return "ingredient"


def _is_drink_keyword_match(norm_name: str) -> bool:
    tokens = _tokenize_words(norm_name)
    # Prevent substring collisions like "ром" inside food terms ("ромиро", "романо").
    if any(token.startswith(prefix) for token in tokens for prefix in FOOD_FALSE_DRINK_TOKEN_PREFIXES):
        return False
    for keyword in DRINK_KEYWORDS:
        if keyword in DRINK_KEYWORDS_EXACT_TOKEN:
            if keyword in tokens:
                return True
            continue
        if keyword in norm_name:
            return True
    return False


def _tokenize_words(value: str) -> list[str]:
    return re.findall(r"[a-zа-я0-9]+", _norm(value))


def _build_menu_node_type_corrections(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    corrections: list[dict[str, Any]] = []
    for row in nodes:
        old_type = _legacy_classify_node_type(row.get("node_name", ""), is_header=True)
        new_type = row.get("node_type", "")
        if not (old_type == "drink" and new_type != "drink"):
            continue
        norm_name = _norm(row.get("node_name", ""))
        corrections.append(
            {
                "node_id": row.get("node_id", ""),
                "node_name": row.get("node_name", ""),
                "old_type": old_type,
                "new_type": new_type,
                "correction_reason": "drink_keyword_fragment_collision",
                "evidence": (
                    f"norm_name={norm_name};legacy_substring_match=ром;"
                    "hardened_token_check_ignores_ромиро_романо_family"
                ),
            }
        )
    return corrections


def _normalize_ingredient(value: str) -> str:
    text = _norm(value)
    text = re.sub(r"[^a-zа-я0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _apply_typo_fixes(value: str) -> str:
    result = value
    for bad, good in TYPO_FIXES.items():
        result = result.replace(_norm(bad), _norm(good))
    return result


def _ingredient_group(value: str) -> str:
    if _contains_any(value, ("говяд", "свинин", "кур", "индей", "бара", "утк")):
        return "protein_animal"
    if _contains_any(value, ("рыб", "кревет", "мид", "устриц", "лангуст")):
        return "fish_seafood"
    if _contains_any(value, ("молок", "сыр", "сливк", "сметан")):
        return "dairy"
    if _contains_any(value, ("рис", "лапш", "мука", "хлеб", "паста", "картоф")):
        return "grains_starch"
    if _contains_any(value, ("лук", "морков", "капуст", "томат", "огур", "зелень", "тыкв", "свекл")):
        return "vegetables"
    if "соус" in value:
        return "sauce"
    if _contains_any(value, ("сахар", "мед", "шоколад")):
        return "sweetener"
    return "other"


def _contains_any(value: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in value for pattern in patterns)


def _is_tech_text_line(line: str) -> bool:
    if "\t" in line:
        return False
    if len(line.split()) < 5:
        return False
    return bool(re.search(r"[,.]", line))


def _parse_number(value: str) -> float | None:
    numbers = re.findall(r"[0-9]+(?:[.,][0-9]+)?", value)
    if not numbers:
        return None
    return float(numbers[0].replace(",", "."))


def _safe_int(value: Any) -> int:
    try:
        return int(str(value).replace(" ", ""))
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return 0.0


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", str(value))
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return digits


def _fuzzy_match(value: str, candidates: list[str]) -> tuple[str, float] | None:
    if not candidates:
        return None
    import difflib

    best_name = ""
    best_score = 0.0
    for candidate in candidates:
        score = difflib.SequenceMatcher(None, value, candidate).ratio()
        if score > best_score:
            best_name = candidate
            best_score = score
    if best_score < 0.82:
        return None
    return best_name, best_score


def _alias_coverage_rows(order_item_match: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(order_item_match)
    by_method: dict[str, int] = {}
    for row in order_item_match:
        method = row["match_method"]
        by_method[method] = by_method.get(method, 0) + 1
    rows: list[dict[str, Any]] = []
    for method, count in sorted(by_method.items()):
        rows.append(
            {
                "match_method": method,
                "rows": count,
                "coverage_share": round(count / max(1, total), 6),
            }
        )
    return rows


def _build_item_domain_confusion(order_item_match: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node_by_id = {row["node_id"]: row for row in nodes}
    detail_rows: list[dict[str, Any]] = []
    for row in order_item_match:
        matched_id = row["matched_dish_id"]
        if not matched_id:
            continue
        matched_node = node_by_id.get(matched_id)
        if not matched_node:
            continue
        node_type = matched_node["node_type"]
        confusion_type = "ok"
        if row["item_type"] == "food" and node_type in {"drink", "service"}:
            confusion_type = "food_to_non_food"
        elif row["item_type"] in {"drink", "service"} and node_type == "dish":
            confusion_type = "non_food_to_food"
        if confusion_type == "ok":
            continue
        detail_rows.append(
            {
                "order_id": row["order_id"],
                "line_no": row["line_no"],
                "item_name_raw": row["item_name_raw"],
                "item_type": row["item_type"],
                "matched_dish_id": matched_id,
                "matched_dish_name": matched_node["node_name"],
                "matched_node_type": node_type,
                "match_method": row["match_method"],
                "match_confidence": row["match_confidence"],
                "confusion_type": confusion_type,
            }
        )
    summary_rows = [
        {
            "order_id": "summary",
            "line_no": 0,
            "item_name_raw": "",
            "item_type": "all_matched",
            "matched_dish_id": "",
            "matched_dish_name": "",
            "matched_node_type": "",
            "match_method": "",
            "match_confidence": "",
            "confusion_type": f"total_confusions={len(detail_rows)}",
        },
        {
            "order_id": "summary",
            "line_no": 0,
            "item_name_raw": "",
            "item_type": "food_to_non_food",
            "matched_dish_id": "",
            "matched_dish_name": "",
            "matched_node_type": "",
            "match_method": "",
            "match_confidence": "",
            "confusion_type": f"count={len([row for row in detail_rows if row['confusion_type'] == 'food_to_non_food'])}",
        },
        {
            "order_id": "summary",
            "line_no": 0,
            "item_name_raw": "",
            "item_type": "non_food_to_food",
            "matched_dish_id": "",
            "matched_dish_name": "",
            "matched_node_type": "",
            "match_method": "",
            "match_confidence": "",
            "confusion_type": f"count={len([row for row in detail_rows if row['confusion_type'] == 'non_food_to_food'])}",
        },
    ]
    return summary_rows + sorted(detail_rows, key=lambda item: (item["confusion_type"], item["order_id"], item["line_no"]))


def _build_top_order_items_match_sample(order_item_match: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node_by_id = {row["node_id"]: row for row in nodes}
    grouped: dict[str, dict[str, Any]] = {}
    for row in order_item_match:
        key = row["item_name_norm"]
        bucket = grouped.setdefault(
            key,
            {
                "item_name_norm": key,
                "example_item_name_raw": row["item_name_raw"],
                "hits": 0,
                "matched_hits": 0,
                "food_hits": 0,
                "drink_service_hits": 0,
                "matched_to_dish_hits": 0,
                "matched_to_non_food_hits": 0,
                "top_match": {},
            },
        )
        bucket["hits"] += 1
        if row["item_type"] == "food":
            bucket["food_hits"] += 1
        else:
            bucket["drink_service_hits"] += 1
        if row["matched_dish_id"]:
            bucket["matched_hits"] += 1
            node = node_by_id.get(row["matched_dish_id"])
            if node and node["node_type"] == "dish":
                bucket["matched_to_dish_hits"] += 1
            elif node:
                bucket["matched_to_non_food_hits"] += 1
            tag = f"{row['matched_dish_id']}|{row['match_method']}"
            bucket["top_match"][tag] = bucket["top_match"].get(tag, 0) + 1
    rows: list[dict[str, Any]] = []
    for item in grouped.values():
        if item["matched_hits"] == 0:
            continue
        top_key = ""
        top_count = 0
        for key, count in item["top_match"].items():
            if count > top_count:
                top_key = key
                top_count = count
        matched_dish_id, match_method = top_key.split("|") if top_key else ("", "")
        node_type = node_by_id.get(matched_dish_id, {}).get("node_type", "")
        food_precision = item["matched_to_dish_hits"] / max(1, item["matched_hits"])
        rows.append(
            {
                "item_name_norm": item["item_name_norm"],
                "example_item_name_raw": item["example_item_name_raw"],
                "hits": item["hits"],
                "matched_hits": item["matched_hits"],
                "top_matched_dish_id": matched_dish_id,
                "top_matched_node_type": node_type,
                "top_match_method": match_method,
                "food_vs_drink_precision_proxy": round(food_precision, 6),
            }
        )
    rows = sorted(rows, key=lambda row: (-row["hits"], row["item_name_norm"]))
    return rows[:80]


def _build_high_sales_unmatched_items(order_item_match: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in order_item_match:
        if row["item_type"] != "food":
            continue
        if row["matched_dish_id"]:
            continue
        key = row["item_name_norm"]
        bucket = grouped.setdefault(
            key,
            {
                "item_name_norm": key,
                "example_item_name_raw": row["item_name_raw"],
                "unmatched_orders": set(),
                "unmatched_count": 0,
                "first_order_id": row["order_id"],
            },
        )
        bucket["unmatched_count"] += 1
        bucket["unmatched_orders"].add(row["order_id"])
    rows = [
        {
            "item_name_norm": row["item_name_norm"],
            "example_item_name_raw": row["example_item_name_raw"],
            "unmatched_count": row["unmatched_count"],
            "distinct_orders": len(row["unmatched_orders"]),
            "review_priority": "high" if row["unmatched_count"] >= 2 else "medium",
            "first_order_id": row["first_order_id"],
        }
        for row in grouped.values()
    ]
    return sorted(rows, key=lambda item: (-item["unmatched_count"], item["item_name_norm"]))[:80]


def _build_drink_service_leakage(
    purchase_events: list[dict[str, Any]],
    order_item_match: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    node_by_id = {row["node_id"]: row for row in nodes}
    total_food_candidates = len([row for row in order_item_match if row["item_type"] == "food" and row["matched_dish_id"]])
    leaked = [row for row in purchase_events if row.get("dish_node_type") in {"drink", "service"}]
    rows: list[dict[str, Any]] = [
        {
            "metric": "food_matched_candidates_total",
            "value": total_food_candidates,
            "details": "",
        },
        {
            "metric": "leaked_events_into_profile",
            "value": len(leaked),
            "details": "",
        },
        {
            "metric": "leakage_ratio",
            "value": round(len(leaked) / max(1, total_food_candidates), 6),
            "details": "",
        },
    ]
    for event in sorted(leaked, key=lambda row: (row["order_datetime"], row["order_id"], row["dish_id"]))[:80]:
        node = node_by_id.get(event["dish_id"], {})
        rows.append(
            {
                "metric": "leak_event",
                "value": event["order_id"],
                "details": f"{event['dish_name']}|type={node.get('node_type','')}|user={event['user_id']}",
            }
        )
    return rows


def _build_composite_expansion_audits(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    ingredient_dict: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    node_by_id = {row["node_id"]: row for row in nodes}
    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        children_by_parent.setdefault(edge["parent_node_id"], []).append(edge)
    ingredient_lookup = {row["canonical_name"]: row["ingredient_id"] for row in ingredient_dict}
    target_norms = {_norm(name) for name in COMPOSITE_DISH_TARGETS}
    dish_candidates = [
        row
        for row in nodes
        if row["node_type"] == "dish" and (row["norm_name"] in target_norms or any(t in row["norm_name"] for t in target_norms))
    ]
    dish_candidates = sorted(dish_candidates, key=lambda row: row["node_name"])
    sample_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    seen_dishes: set[str] = set()
    for dish in dish_candidates:
        seen_dishes.add(dish["norm_name"])
        traced = _expand_atomic_with_trace(
            node_id=dish["node_id"],
            node_by_id=node_by_id,
            children_by_parent=children_by_parent,
            path=[],
            has_pf=False,
        )
        if not traced:
            hints = _name_hint_ingredients(dish["node_name"], ingredient_dict)
            if not hints:
                missing_rows.append(
                    {
                        "dish_id": dish["node_id"],
                        "dish_name": dish["node_name"],
                        "ingredient_name": "",
                        "canonical_found": False,
                        "provenance": "missing",
                        "path": dish["node_name"],
                        "reason": "no_atomic_and_no_name_hint",
                    }
                )
            for hint in hints:
                sample_rows.append(
                    {
                        "dish_id": dish["node_id"],
                        "dish_name": dish["node_name"],
                        "ingredient_name": hint,
                        "canonical_found": hint in ingredient_lookup,
                        "provenance": "name_hint",
                        "path": dish["node_name"],
                        "weight_g_est": 0.0,
                    }
                )
            continue
        for row in traced:
            canonical = _apply_typo_fixes(_normalize_ingredient(row["ingredient_name"]))
            canonical_found = canonical in ingredient_lookup
            sample_rows.append(
                {
                    "dish_id": dish["node_id"],
                    "dish_name": dish["node_name"],
                    "ingredient_name": row["ingredient_name"],
                    "canonical_found": canonical_found,
                    "provenance": row["provenance"],
                    "path": row["path"],
                    "weight_g_est": round(row["weight"], 4),
                }
            )
            if not canonical_found:
                missing_rows.append(
                    {
                        "dish_id": dish["node_id"],
                        "dish_name": dish["node_name"],
                        "ingredient_name": row["ingredient_name"],
                        "canonical_found": False,
                        "provenance": row["provenance"],
                        "path": row["path"],
                        "reason": "missing_in_ingredient_dictionary",
                    }
                )

    for required in sorted(target_norms):
        if required in seen_dishes:
            continue
        missing_rows.append(
            {
                "dish_id": "",
                "dish_name": required,
                "ingredient_name": "",
                "canonical_found": False,
                "provenance": "missing",
                "path": "",
                "reason": "target_dish_not_found",
            }
        )

    sorted_sample = sorted(sample_rows, key=lambda row: (row["dish_name"], row["provenance"], row["ingredient_name"]))
    sorted_missing = sorted(missing_rows, key=lambda row: (row["dish_name"], row["reason"], row["ingredient_name"]))
    if not sorted_missing:
        sorted_missing = [
            {
                "dish_id": "summary",
                "dish_name": "",
                "ingredient_name": "",
                "canonical_found": True,
                "provenance": "",
                "path": "",
                "reason": "none",
            }
        ]
    return (sorted_sample, sorted_missing)


def _expand_atomic_with_trace(
    node_id: str,
    node_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str, list[dict[str, Any]]],
    path: list[str],
    has_pf: bool,
) -> list[dict[str, Any]]:
    node = node_by_id.get(node_id)
    if not node:
        return []
    if node_id in path:
        return []
    current_path = path + [node["node_name"]]
    children = children_by_parent.get(node_id, [])
    if not children:
        if node["node_type"] in {"ingredient", "sauce", "garnish"}:
            return [
                {
                    "ingredient_name": node["node_name"],
                    "weight": 1.0,
                    "provenance": "expanded_from_pf" if has_pf else "direct",
                    "path": " -> ".join(current_path),
                }
            ]
        return []

    rows: list[dict[str, Any]] = []
    for edge in children:
        child = node_by_id.get(edge["child_node_id"])
        if not child:
            continue
        factor = edge["qty_num"] if edge["qty_num"] is not None else 1.0
        child_path = current_path + [child["node_name"]]
        child_has_pf = has_pf or child["node_type"] == "semi_finished"
        if child["node_type"] in {"ingredient", "sauce", "garnish"}:
            rows.append(
                {
                    "ingredient_name": child["node_name"],
                    "weight": factor,
                    "provenance": "expanded_from_pf" if child_has_pf else "direct",
                    "path": " -> ".join(child_path),
                }
            )
            continue
        nested = _expand_atomic_with_trace(
            node_id=child["node_id"],
            node_by_id=node_by_id,
            children_by_parent=children_by_parent,
            path=current_path,
            has_pf=child_has_pf,
        )
        for item in nested:
            rows.append(
                {
                    "ingredient_name": item["ingredient_name"],
                    "weight": item["weight"] * factor,
                    "provenance": item["provenance"],
                    "path": item["path"],
                }
            )
    return rows


def _name_hint_ingredients(dish_name: str, ingredient_dict: list[dict[str, Any]]) -> list[str]:
    text = _norm(dish_name)
    hints: list[str] = []
    for row in ingredient_dict:
        ingredient = row["canonical_name"]
        if len(ingredient) < 4:
            continue
        if ingredient in text:
            hints.append(ingredient)
    return sorted(set(hints))[:8]


def _build_method_tag_evidence_sample(method_rows: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_norms = {_norm(name) for name in COMPOSITE_DISH_TARGETS}
    node_name = {row["node_id"]: row["node_name"] for row in nodes}
    rows: list[dict[str, Any]] = []
    for row in method_rows:
        dish_name = row["dish_name"] or node_name.get(row["dish_id"], "")
        is_target = any(target in _norm(dish_name) for target in target_norms)
        if not is_target:
            continue
        rows.append(
            {
                "dish_id": row["dish_id"],
                "dish_name": dish_name,
                "method_tag": row["method_tag"],
                "evidence_text": row["evidence_text"],
                "confidence": row["confidence"],
            }
        )
    if not rows:
        rows = [
            {
                "dish_id": row["dish_id"],
                "dish_name": row["dish_name"],
                "method_tag": row["method_tag"],
                "evidence_text": row["evidence_text"],
                "confidence": row["confidence"],
            }
            for row in method_rows[:120]
        ]
    return sorted(rows, key=lambda row: (row["dish_name"], row["method_tag"], row["evidence_text"]))


def _build_ingredient_alias_top_uncovered(
    order_item_match: list[dict[str, Any]],
    ingredient_aliases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    alias_terms = {_norm(row["alias_normalized"]) for row in ingredient_aliases}
    grouped: dict[str, dict[str, Any]] = {}
    for row in order_item_match:
        if row["item_type"] != "food" or row["matched_dish_id"]:
            continue
        tokens = [token for token in re.split(r"[^a-zа-я0-9]+", row["item_name_norm"]) if len(token) >= 3]
        uncovered = [token for token in tokens if token not in alias_terms]
        for token in uncovered:
            bucket = grouped.setdefault(
                token,
                {
                    "alias_candidate": token,
                    "hits": 0,
                    "example_item_name_raw": row["item_name_raw"],
                },
            )
            bucket["hits"] += 1
    rows = sorted(grouped.values(), key=lambda item: (-item["hits"], item["alias_candidate"]))
    return rows[:120]


def _build_ingredient_typo_clusters(ingredient_aliases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ingredient: dict[str, list[str]] = {}
    for row in ingredient_aliases:
        by_ingredient.setdefault(row["ingredient_id"], []).append(row["alias_normalized"])
    clusters: list[dict[str, Any]] = []
    for ingredient_id, aliases in sorted(by_ingredient.items()):
        unique_aliases = sorted(set(aliases))
        if len(unique_aliases) < 2:
            continue
        base = unique_aliases[0]
        for alias in unique_aliases[1:]:
            score = _similarity(base, alias)
            if score < 0.6:
                continue
            clusters.append(
                {
                    "ingredient_id": ingredient_id,
                    "alias_base": base,
                    "alias_variant": alias,
                    "similarity": round(score, 4),
                    "cluster_hint": "possible_typo_or_synonym",
                }
            )
    return clusters[:200]


def _build_ingredient_dictionary_noise(ingredient_dict: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in ingredient_dict:
        canonical = row["canonical_name"]
        reasons: list[str] = []
        if bool(row["is_generic"]):
            reasons.append("generic_flag")
        if len(canonical) <= 3:
            reasons.append("very_short_token")
        if row["ingredient_group"] == "other":
            reasons.append("other_group")
        if not reasons:
            continue
        rows.append(
            {
                "ingredient_id": row["ingredient_id"],
                "canonical_name": canonical,
                "ingredient_group": row["ingredient_group"],
                "noise_reasons": "|".join(reasons),
            }
        )
    return sorted(rows, key=lambda item: (item["canonical_name"], item["ingredient_id"]))


def _build_user_profile_sanity_sample(
    user_profiles: list[dict[str, Any]],
    user_feature_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_user: dict[str, list[dict[str, Any]]] = {}
    for row in user_feature_rows:
        by_user.setdefault(str(row["user_id"]), []).append(row)
    rows: list[dict[str, Any]] = []
    for profile in user_profiles:
        user_id = str(profile["user_id"])
        features = by_user.get(user_id, [])
        long_features = [row for row in features if row["layer"] == "long_term"]
        long_features = sorted(long_features, key=lambda row: (-float(row["weight"]), row["axis"], row["feature_key"]))
        top = long_features[:8]
        top_str = "|".join(f"{row['axis']}:{row['feature_key']}={row['weight']}" for row in top)
        leakage = [row for row in long_features if row["axis"] in {"drink", "service"} or "drink" in row["feature_key"] or "service" in row["feature_key"]]
        rows.append(
            {
                "user_id": user_id,
                "orders_count": profile.get("meta", {}).get("orders_count", 0),
                "top_long_term_features": top_str,
                "drink_service_feature_hits": len(leakage),
                "sanity_status": "ok" if not leakage else "review",
            }
        )
    return sorted(rows, key=lambda item: item["user_id"])[:120]


def _build_user_top_items_vs_profile(
    purchase_events: list[dict[str, Any]],
    user_profiles: list[dict[str, Any]],
    dish_feature_rows: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    node_by_id = {row["node_id"]: row for row in nodes}
    features_by_dish: dict[str, list[dict[str, Any]]] = {}
    for row in dish_feature_rows:
        features_by_dish.setdefault(row["dish_id"], []).append(row)
    by_user_events: dict[str, list[dict[str, Any]]] = {}
    for event in purchase_events:
        by_user_events.setdefault(str(event["user_id"]), []).append(event)
    profile_lookup = {str(row["user_id"]): row for row in user_profiles}

    rows: list[dict[str, Any]] = []
    for user_id, events in sorted(by_user_events.items()):
        dish_counts: dict[str, int] = {}
        for event in events:
            dish_counts[event["dish_id"]] = dish_counts.get(event["dish_id"], 0) + 1
        top_dishes = sorted(dish_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        profile = profile_lookup.get(user_id, {})
        top_profile_keys = set()
        for axis, tags in profile.get("long_term", {}).items():
            sorted_tags = sorted(tags.items(), key=lambda x: (-float(x[1]), x[0]))[:10]
            for key, _ in sorted_tags:
                top_profile_keys.add(f"{axis}:{key}")
        for dish_id, count in top_dishes:
            dish_name = node_by_id.get(dish_id, {}).get("node_name", dish_id)
            dish_features = features_by_dish.get(dish_id, [])
            overlaps = []
            for feature in dish_features:
                key = f"{feature['axis']}:{feature['feature_key']}"
                if key in top_profile_keys:
                    overlaps.append(key)
            rows.append(
                {
                    "user_id": user_id,
                    "dish_id": dish_id,
                    "dish_name": dish_name,
                    "purchase_count": count,
                    "profile_overlap_features": "|".join(sorted(set(overlaps))[:8]),
                    "overlap_count": len(set(overlaps)),
                }
            )
    return sorted(rows, key=lambda item: (item["user_id"], -int(item["purchase_count"]), item["dish_name"]))[:240]


def _similarity(left: str, right: str) -> float:
    import difflib

    return float(difflib.SequenceMatcher(None, left, right).ratio())


def _layer_to_json(values: dict[tuple[str, str], float]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for (axis, key), value in sorted(values.items(), key=lambda x: (x[0][0], x[0][1])):
        result.setdefault(axis, {})[key] = round(_clip(value), 6)
    return result


def _clip(value: float, min_v: float = -1.0, max_v: float = 1.0) -> float:
    return max(min_v, min(max_v, value))


def _ingredient_name_by_id(rows: list[dict[str, Any]], ingredient_id: str) -> str:
    row = next((item for item in rows if item["ingredient_id"] == ingredient_id), None)
    if not row:
        return ingredient_id
    return row["canonical_name"]


def _stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _norm(value: str) -> str:
    return str(value).lower().replace("ё", "е").strip()


def _write_menu_parse_summary(path: Path, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], menu_docs: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> None:
    rows = [
        {"metric": "menu_sources", "value": len(menu_docs)},
        {"metric": "total_nodes", "value": len(nodes)},
        {"metric": "sellable_dishes", "value": len([row for row in nodes if row["is_sellable"] and row["node_type"] == "dish"])},
        {"metric": "semi_finished_nodes", "value": len([row for row in nodes if row["node_type"] == "semi_finished"])},
        {"metric": "ingredient_nodes", "value": len([row for row in nodes if row["node_type"] == "ingredient"])},
        {"metric": "recipe_edges", "value": len(edges)},
        {"metric": "skipped_lines", "value": len(skipped)},
    ]
    _write_csv(path, rows)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as file_obj:
            file_obj.write("")
        return
    headers = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
