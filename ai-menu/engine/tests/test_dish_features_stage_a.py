import json
from pathlib import Path

from openpyxl import Workbook

from app.config.taxonomy import load_runtime_taxonomy
from app.pipelines.dish_features_stage_a import build_dish_features_stage_a


def _write_menu(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Меню"
    ws.append(
        [
            "Ресторан",
            "ID блюда",
            "Название блюда",
            "Описание",
            "Категория",
            "Ингредиенты",
            "Ккал",
            "Вес",
        ]
    )
    ws.append(
        [
            "KoreanChick",
            "d1",
            "Аутентичный Том-Ям",
            "Острый азиатский суп",
            "Суп",
            "Креветки, кокосовое молоко, чили, рыбный соус",
            "К: 8 г, Б: 12 г, Ж: 6 г, Э: 180 ккал",
            "200",
        ]
    )
    ws.append(
        [
            "Дом",
            "d2",
            "Борщ с говядиной",
            "Традиционный домашний суп",
            "Суп",
            "Говядина, капуста, свекла, сметана",
            "К: 35 г, Б: 18 г, Ж: 8 г, Э: 320 ккал",
            "120",
        ]
    )
    ws.append(
        [
            "Italia",
            "d3",
            "Пицца Маргарита",
            "Классическая итальянская пицца",
            "Пицца",
            "Пшеничное тесто, томаты, сыр моцарелла, базилик",
            "К: 31 г, Б: 11 г, Ж: 9 г, Э: 290 ккал",
            "280",
        ]
    )
    ws.append(
        [
            "Geo",
            "d4",
            "Хачапури по-аджарски",
            "Грузинская выпечка",
            "Выпечка",
            "Тесто, сыр сулугуни, яйцо, масло",
            "К: 40 г, Б: 19 г, Ж: 15 г, Э: 420 ккал",
            "120",
        ]
    )
    ws.append(
        [
            "Fit",
            "d5",
            "Салат с индейкой",
            "Легкий полезный салат",
            "Салат",
            "Индейка, салат, огурец",
            "К: 12 г, Б: 17 г, Ж: 4 г, Э: 190 ккал",
            "100",
        ]
    )
    wb.save(path)


def test_stage_a_golden_dishes(tmp_path: Path) -> None:
    menu = tmp_path / "menu_export.xlsx"
    out = tmp_path / "derived"
    _write_menu(menu)
    taxonomy = load_runtime_taxonomy(Path("docs/runtime_taxonomy_resolved_v1.json"))

    stats = build_dish_features_stage_a(menu_path=menu, output_dir=out, taxonomy=taxonomy)
    assert stats.dishes_processed == 5
    assert stats.parsed_rows == 5
    assert stats.cache_rows_written == stats.unique_dish_ids
    assert stats.nutrition_parse_success_rate == 1.0
    assert (out / "audit" / "dish_stage_a_summary.csv").exists()

    cache = json.loads((out / "dish_features_cache.json").read_text(encoding="utf-8"))
    by_id = {row["dish_id"]: row for row in cache}

    tom_yam = by_id["d1"]
    assert "asian" in tom_yam["cuisine"]
    assert "soup" in tom_yam["format_texture"]
    assert tom_yam["taste"].get("spicy", 0) > 0

    borscht = by_id["d2"]
    assert "soup" in borscht["format_texture"]
    assert "home_style" in borscht["cuisine"] or "russian_home" in borscht["cuisine"]
    assert borscht["nutrition"]["satiety_class"] == "hearty"

    margherita = by_id["d3"]
    assert "italian" in margherita["cuisine"]
    assert "tomato" in margherita["ingredient"]
    assert "cheese" in margherita["ingredient"]
    assert "baked" in margherita["format_texture"]

    khachapuri = by_id["d4"]
    assert "georgian_caucasian" in khachapuri["cuisine"]
    assert khachapuri["nutrition"]["satiety_class"] == "hearty"

    healthy = by_id["d5"]
    assert healthy["nutrition"]["high_protein"] is True
    assert healthy["nutrition"]["low_calorie"] is True


def test_salad_not_from_ingredient_phrase_and_weight_gate(tmp_path: Path) -> None:
    menu = tmp_path / "menu_export.xlsx"
    out = tmp_path / "derived"
    wb = Workbook()
    ws = wb.active
    ws.title = "Меню"
    ws.append(["Ресторан", "ID блюда", "Название блюда", "Категория", "Ингредиенты", "Ккал", "Вес"])
    ws.append(
        [
            "KoreanChick",
            "w1",
            "Вок с курицей",
            "Вок",
            "Курица, листья салата, соевый соус",
            "К: 20 г, Б: 18 г, Ж: 7 г, Э: 240 ккал",
            "",
        ]
    )
    wb.save(menu)
    taxonomy = load_runtime_taxonomy(Path("docs/runtime_taxonomy_resolved_v1.json"))

    build_dish_features_stage_a(menu_path=menu, output_dir=out, taxonomy=taxonomy)
    cache = json.loads((out / "dish_features_cache.json").read_text(encoding="utf-8"))
    dish = cache[0]
    assert "salad" not in dish["format_texture"]
    assert dish["nutrition"]["high_protein"] is None
    assert dish["nutrition"]["weight_needs_review"] is True
