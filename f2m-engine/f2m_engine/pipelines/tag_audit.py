from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from f2m_engine.domain.tag_localization import localize_tag, missing_taxonomy_labels

DISPLAY_NUTRITION_KEYS = {"low_calorie", "high_protein", "low_fat", "high_carb"}
DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "data" / "taxonomy.json"


@dataclass(frozen=True)
class TagAuditStats:
    dishes: int
    missing_label_rows: int
    anomaly_rows: int
    questionable_dishes: int = 0
    questionable_tag_rows: int = 0


def audit_menu_tags(
    derived_dir: Path | str,
    taxonomy_path: Path | str = DEFAULT_TAXONOMY_PATH,
) -> TagAuditStats:
    base = Path(derived_dir)
    audit_dir = base / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    cache_path = base / "dish_features_cache.json"
    dishes = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else []

    missing_rows = missing_taxonomy_labels(taxonomy_path)
    missing_rows.extend(_missing_labels_for_seen_dish_tags(dishes=dishes))
    missing_rows = _dedupe_rows(missing_rows)
    anomaly_rows = [
        row
        for dish in dishes
        for row in detect_tag_anomalies_for_dish(dish)
    ]
    questionable_by_dish, questionable_rows = build_questionable_tag_reports(dishes=dishes)

    _write_csv(
        audit_dir / "tag_localization_audit.csv",
        ["axis", "key", "issue"],
        missing_rows,
    )
    _write_csv(
        audit_dir / "tag_anomaly_audit.csv",
        ["dish_id", "dish_name", "axis", "key", "issue", "evidence"],
        anomaly_rows,
    )
    _write_csv(
        audit_dir / "questionable_tag_rows.csv",
        ["dish_id", "dish_name", "category", "axis", "key", "issue", "evidence"],
        questionable_rows,
    )
    _write_csv(
        audit_dir / "questionable_tags_by_dish.csv",
        [
            "dish_id",
            "dish_name",
            "category",
            "questionable_tag_count",
            "questionable_tags",
            "issues",
            "evidence",
        ],
        questionable_by_dish,
    )
    return TagAuditStats(
        dishes=len(dishes),
        missing_label_rows=len(missing_rows),
        anomaly_rows=len(anomaly_rows),
        questionable_dishes=len([row for row in questionable_by_dish if int(row["questionable_tag_count"]) > 0]),
        questionable_tag_rows=len(questionable_rows),
    )


def detect_tag_anomalies_for_dish(dish: dict[str, Any]) -> list[dict[str, str]]:
    return [
        _to_anomaly_row(row)
        for row in detect_questionable_tags_for_dish(dish)
        if row["issue"] in {"fried_on_bar_like_item", "low_calorie_with_high_kcal"}
    ]


def build_questionable_tag_reports(dishes: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    detail_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []
    for dish in sorted(dishes, key=lambda row: (str(row.get("meta", {}).get("category", "")), str(row.get("meta", {}).get("name", "")), str(row.get("dish_id", "")))):
        questionable = detect_questionable_tags_for_dish(dish)
        detail_rows.extend(questionable)
        summary_rows.append(_summarize_questionable_tags(dish=dish, rows=questionable))
    return summary_rows, detail_rows


def detect_questionable_tags_for_dish(dish: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    dish_id = str(dish.get("dish_id", ""))
    display_name = str(dish.get("meta", {}).get("name", "") or dish.get("dish_name", ""))
    display_category = str(dish.get("meta", {}).get("category", "") or dish.get("category", ""))
    name = _norm(display_name)
    category = _norm(display_category)
    merged = f"{name} {category}"
    format_texture = dish.get("format_texture", {}) or dish.get("format_texture_features", {}) or {}
    nutrition = dish.get("nutrition", {}) or dish.get("nutrition_features", {}) or {}
    cuisine = dish.get("cuisine", {}) or dish.get("cuisine_features", {}) or {}
    hard_flags = dish.get("hard_flags", {}) or dish.get("constraint_flags", {}) or {}

    if _safe_float(format_texture.get("fried")) > 0.0 and any(
        token in merged
        for token in ("батончик", "bar", "протеинов", "мюсли", "granola")
    ):
        rows.append(_questionable_row(
            dish_id=dish_id,
            dish_name=display_name,
            category=display_category,
            axis="format_texture",
            key="fried",
            issue="fried_on_bar_like_item",
            evidence="name_or_category_contains_bar_marker",
        ))

    if _safe_float(format_texture.get("fried")) > 0.0 and not _has_any(
        merged,
        (
            "жар",
            "фри",
            "фритюр",
            "панир",
            "наггет",
            "байтс",
            "котлет",
            "биточ",
            "бифштекс",
            "блин",
            "сырник",
            "картофельный олад",
            "fried",
            "fries",
            "nugget",
            "cutlet",
        ),
    ):
        rows.append(_questionable_row(
            dish_id=dish_id,
            dish_name=display_name,
            category=display_category,
            axis="format_texture",
            key="fried",
            issue="fried_without_name_or_category_evidence",
            evidence="fried>0 but no fried-like marker in name/category",
        ))

    _flag_format_without_evidence(
        rows=rows,
        dish_id=dish_id,
        dish_name=display_name,
        category=display_category,
        merged=merged,
        format_texture=format_texture,
        key="soup",
        markers=("суп", "борщ", "рамен", "шурпа", "щи", "уха", "solyanka", "soup"),
    )
    _flag_format_without_evidence(
        rows=rows,
        dish_id=dish_id,
        dish_name=display_name,
        category=display_category,
        merged=merged,
        format_texture=format_texture,
        key="salad",
        markers=("салат", "винегрет", "нисуаз", "цезарь", "поке", "salad", "poke"),
    )
    _flag_format_without_evidence(
        rows=rows,
        dish_id=dish_id,
        dish_name=display_name,
        category=display_category,
        merged=merged,
        format_texture=format_texture,
        key="dessert",
        markers=("десерт", "торт", "пирож", "чизкейк", "эклер", "маффин", "кекс", "печень", "батончик", "пирог", "dessert", "cake"),
    )

    if _safe_float(cuisine.get("asian")) > 0.0 and not _has_any(
        merged,
        (
            "азиат",
            "вок",
            "ролл",
            "суши",
            "кимчи",
            "том ям",
            "рамен",
            "терияки",
            "лапша",
            "поке",
            "thai",
            "asian",
            "korean",
            "japanese",
        ),
    ):
        rows.append(_questionable_row(
            dish_id=dish_id,
            dish_name=display_name,
            category=display_category,
            axis="cuisine",
            key="asian",
            issue="asian_without_name_or_category_evidence",
            evidence="asian>0 but no Asian cuisine marker in name/category",
        ))

    if _safe_float(cuisine.get("fast_food")) > 0.0 and not _has_any(
        merged,
        ("бургер", "фри", "наггет", "байтс", "сэндвич", "чиабат", "шаурм", "хот-дог", "fast", "burger", "sandwich"),
    ):
        rows.append(_questionable_row(
            dish_id=dish_id,
            dish_name=display_name,
            category=display_category,
            axis="cuisine",
            key="fast_food",
            issue="fast_food_without_name_or_category_evidence",
            evidence="fast_food>0 but no fast-food marker in name/category",
        ))

    if bool(hard_flags.get("peanut")) and not _has_any(
        merged,
        ("арахис", "орех", "peanut", "nut", "сатай", "батончик", "raw to go"),
    ):
        rows.append(_questionable_row(
            dish_id=dish_id,
            dish_name=display_name,
            category=display_category,
            axis="hard_flags",
            key="peanut",
            issue="peanut_flag_unexpected_for_name_category",
            evidence="peanut hard flag true but name/category lacks nut marker",
        ))

    if bool(nutrition.get("low_calorie")) and _safe_float(nutrition.get("kcal_per_portion")) >= 700:
        rows.append(_questionable_row(
            dish_id=dish_id,
            dish_name=display_name,
            category=display_category,
            axis="nutrition",
            key="low_calorie",
            issue="low_calorie_with_high_kcal",
            evidence=f"kcal_per_portion={nutrition.get('kcal_per_portion')}",
        ))

    if (
        _norm(str(nutrition.get("satiety_class", ""))) == "snack"
        and _safe_float(nutrition.get("weight_g")) >= 180
        and _has_any(category, ("вторые блюда", "супы", "салаты"))
    ):
        rows.append(_questionable_row(
            dish_id=dish_id,
            dish_name=display_name,
            category=display_category,
            axis="nutrition",
            key="satiety_class",
            issue="main_menu_item_marked_snack",
            evidence=f"category={display_category}; weight_g={nutrition.get('weight_g')}; kcal_per_portion={nutrition.get('kcal_per_portion')}",
        ))

    rows.sort(key=lambda row: (row["axis"], row["key"], row["issue"]))
    return rows


def _flag_format_without_evidence(
    rows: list[dict[str, str]],
    dish_id: str,
    dish_name: str,
    category: str,
    merged: str,
    format_texture: dict[str, Any],
    key: str,
    markers: tuple[str, ...],
) -> None:
    if _safe_float(format_texture.get(key)) <= 0.0:
        return
    if _has_any(merged, markers):
        return
    rows.append(
        _questionable_row(
            dish_id=dish_id,
            dish_name=dish_name,
            category=category,
            axis="format_texture",
            key=key,
            issue=f"{key}_without_name_or_category_evidence",
            evidence=f"{key}>0 but no {key}-like marker in name/category",
        )
    )


def _questionable_row(
    dish_id: str,
    dish_name: str,
    category: str,
    axis: str,
    key: str,
    issue: str,
    evidence: str,
) -> dict[str, str]:
    return {
        "dish_id": dish_id,
        "dish_name": dish_name,
        "category": category,
        "axis": axis,
        "key": key,
        "issue": issue,
        "evidence": evidence,
    }


def _to_anomaly_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "dish_id": row["dish_id"],
        "dish_name": row["dish_name"],
        "axis": row["axis"],
        "key": row["key"],
        "issue": row["issue"],
        "evidence": row["evidence"],
    }


def _summarize_questionable_tags(dish: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, str]:
    dish_name = str(dish.get("meta", {}).get("name", "") or dish.get("dish_name", ""))
    category = str(dish.get("meta", {}).get("category", "") or dish.get("category", ""))
    return {
        "dish_id": str(dish.get("dish_id", "")),
        "dish_name": dish_name,
        "category": category,
        "questionable_tag_count": str(len(rows)),
        "questionable_tags": "|".join(f"{row['axis']}:{row['key']}" for row in rows),
        "issues": "|".join(row["issue"] for row in rows),
        "evidence": "|".join(row["evidence"] for row in rows),
    }


def _missing_labels_for_seen_dish_tags(dishes: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for dish in dishes:
        for axis in ("taste", "cuisine", "format_texture", "context", "restriction", "nutrition"):
            values = _axis_values(dish=dish, axis=axis)
            for key, value in values.items():
                if not _has_signal(value):
                    continue
                if localize_tag(axis=axis, key=str(key)) == str(key):
                    rows.append({"axis": axis, "key": str(key), "issue": "missing_ru_label_for_seen_tag"})
    return rows


def _axis_values(dish: dict[str, Any], axis: str) -> dict[str, Any]:
    if axis == "restriction":
        return dish.get("hard_flags", {}) or dish.get("constraint_flags", {}) or {}
    if axis == "nutrition":
        nutrition = dish.get("nutrition", {}) or dish.get("nutrition_features", {}) or {}
        values = {key: nutrition.get(key) for key in DISPLAY_NUTRITION_KEYS if key in nutrition}
        satiety = str(nutrition.get("satiety_class", "") or "").strip()
        if satiety:
            values[satiety] = True
        return values
    return dish.get(axis, {}) or dish.get(f"{axis}_features", {}) or {}


def _has_signal(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _safe_float(value) > 0.0


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda item: (item["axis"], item["key"], item["issue"])):
        key = (row["axis"], row["key"], row["issue"])
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _norm(value: str) -> str:
    return str(value or "").lower().replace("ё", "е").strip()


def _has_any(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
