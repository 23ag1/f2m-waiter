from pathlib import Path

from app.pipelines.txt_data_layer import build_text_data_layer


def _write_sources(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "изнес ланчи.txt").write_text(
        "\n".join(
            [
                "Борщ",
                "Свекла\t100",
                "Говядина\t80",
                "Выход\t300",
                "Варить и подать горячим.",
                "",
                "Соус Ранч",
                "Сметана\t30",
                "Майонез\t20",
                "Выход\t50",
            ]
        ),
        encoding="utf-8",
    )
    (root / "меню гц.txt").write_text(
        "\n".join(
            [
                "Тако с курицей",
                "Курица\t120",
                "Лепешка\t50",
                "Соус Ранч\t20",
                "Выход\t250",
                "",
                "Соус Ранч п/ф",
                "Сметана\t40",
                "Выход\t40",
            ]
        ),
        encoding="utf-8",
    )
    (root / "Менб хц.txt").write_text(
        "\n".join(
            [
                "Картофель Фри",
                "Картофель\t200",
                "Масло\t15",
                "Выход\t180",
            ]
        ),
        encoding="utf-8",
    )
    (root / "данные заказ-пользователи.txt").write_text(
        "\n".join(
            [
                "Пример данных заказ",
                "Дата,Время,Номер заказа,Гостей,Чистые блюда,Список блюд",
                "01.01.2026,19:32,1001,2,2,\"['Борщ', 'Тако с курицей', 'Чай']\"",
                "01.01.2026,19:50,1002,1,1,\"['Картофель Фри']\"",
                "Пример данных пользователь",
                "Время визита\tНомер заказа\tId клиента\tИмя клиента\tТелефон\tНомер карты\tСумма чека\tСкидка\tСкидка, %\tОплачено\tОплачено бонусами\tНачислено бонусов\tОфициант\tЗаведение\tВсего потрачено\tЧеков\tДата регистрации",
                "01.01.2026 19:32\t1001\t501\tТест\t+79999999999\t1\t1000,00\t0,00\t0,00\t1000,00\t0\t10,00\tA\tGC\t1000,00\t1\t01.01.2026",
                "01.01.2026 19:50\t1002\t502\tТест2\t+78888888888\t2\t500,00\t0,00\t0,00\t500,00\t0\t5,00\tB\tHC\t1500,00\t1\t01.01.2026",
            ]
        ),
        encoding="utf-8",
    )


def test_build_text_data_layer_outputs_and_determinism(tmp_path: Path) -> None:
    source_dir = tmp_path / "menu files"
    _write_sources(source_dir)
    derived = tmp_path / "derived"

    stats_first = build_text_data_layer(source_dir, derived)
    first_summary = (derived / "audit" / "item_match_summary.csv").read_text(encoding="utf-8")
    first_profiles = (derived / "user_profiles.json").read_text(encoding="utf-8")
    first_demo = (derived / "demo_report.md").read_text(encoding="utf-8")

    stats_second = build_text_data_layer(source_dir, derived)
    second_summary = (derived / "audit" / "item_match_summary.csv").read_text(encoding="utf-8")
    second_profiles = (derived / "user_profiles.json").read_text(encoding="utf-8")
    second_demo = (derived / "demo_report.md").read_text(encoding="utf-8")

    assert stats_first.sellable_dishes >= 3
    assert stats_first.users_with_profiles >= 2
    assert stats_second.item_match_coverage == stats_first.item_match_coverage
    assert first_summary == second_summary
    assert first_profiles == second_profiles
    assert first_demo == second_demo

    required_outputs = [
        "raw_documents.jsonl",
        "raw_records.jsonl",
        "menu_nodes.csv",
        "menu_edges.csv",
        "ingredient_dictionary.csv",
        "ingredient_aliases.csv",
        "ingredient_stats.csv",
        "order_headers.csv",
        "order_item_raw.csv",
        "order_user_link.csv",
        "user_identity.csv",
        "order_item_match.csv",
        "purchase_events.csv",
        "dish_flat_ingredients.csv",
        "dish_method_tags.csv",
        "dish_restaurant_tags.csv",
        "dish_feature_values.csv",
        "user_feature_values.csv",
        "user_profiles.json",
        "demo_report.md",
    ]
    for file_name in required_outputs:
        assert (derived / file_name).exists()
    for file_name in [
        "menu_parse_summary.csv",
        "menu_parse_skipped.csv",
        "order_parse_summary.csv",
        "item_match_summary.csv",
        "unmatched_order_items.csv",
        "item_match_review_queue.csv",
        "alias_coverage_summary.csv",
        "item_domain_confusion.csv",
        "top_order_items_match_sample.csv",
        "high_sales_unmatched_items.csv",
        "drink_service_leakage.csv",
        "composite_dish_expansion_sample.csv",
        "missing_ingredient_provenance.csv",
        "method_tag_evidence_sample.csv",
        "ingredient_alias_top_uncovered.csv",
        "ingredient_typo_clusters.csv",
        "ingredient_dictionary_noise.csv",
        "user_profile_sanity_sample.csv",
        "user_top_items_vs_profile.csv",
        "profile_summary_by_user.csv",
        "sample_dish_expansion.csv",
        "sample_user_profiles.csv",
    ]:
        assert (derived / "audit" / file_name).exists()
