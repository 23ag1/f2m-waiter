import csv
import subprocess
from pathlib import Path


def test_m6_business_and_quality_artifacts_are_generated(tmp_path: Path) -> None:
    root = Path.cwd()
    subprocess.run(["venv\\Scripts\\python.exe", "scripts\\generate_m5_artifacts.py"], cwd=root, check=True)
    subprocess.run(["venv\\Scripts\\python.exe", "scripts\\generate_m6_artifacts.py"], cwd=root, check=True)
    required = [
        "questionnaire_quality_gate_report.md",
        "questionnaire_quality_summary.csv",
        "questionnaire_gate_results.csv",
        "questionnaire_leakage_checks.csv",
        "questionnaire_zero_safe_examples.csv",
        "questionnaire_explainability_checks.csv",
        "questionnaire_business_demo_story.md",
        "questionnaire_demo_examples.md",
        "questionnaire_business_faq.md",
        "questionnaire_known_limitations.md",
        "questionnaire_demo_metrics_summary.csv",
        "questionnaire_tester_pack.xlsx",
        "questionnaire_tester_guide.md",
        "questionnaire_tag_categories.csv",
        "questionnaire_all_tags.csv",
        "questionnaire_ingredient_tags.csv",
        "questionnaire_hypothesis_examples.csv",
        "questionnaire_score_review_sample.csv",
    ]
    for rel in required:
        assert (root / rel).exists(), f"Missing artifact: {rel}"


def test_quality_gates_have_no_blocked_or_nonrec_leaks() -> None:
    root = Path.cwd()
    rows = _read_csv_rows(root / "questionnaire_leakage_checks.csv")
    assert rows
    assert all(int(row["leaked_blocked_item_count"]) == 0 for row in rows)
    assert all(int(row["leaked_non_recommendable_item_count"]) == 0 for row in rows)


def test_demo_topn_has_no_non_recommendable_entities() -> None:
    root = Path.cwd()
    rows = _read_csv_rows(root / "questionnaire_recommendations_sample.csv")
    assert rows
    topn = [row for row in rows if int(row.get("rank", "9999")) <= 5]
    banned = ("соус", "sauce", "service", "ingredient", "ингредиент", "addon", "add-on", "полуфаб", "condiment")
    for row in topn:
        lowered = row["dish_name"].lower().replace("ё", "е")
        assert not any(token in lowered for token in banned), row["dish_name"]


def test_score_review_sample_has_required_columns_and_explanations() -> None:
    root = Path.cwd()
    rows = _read_csv_rows(root / "questionnaire_score_review_sample.csv")
    assert rows
    headers = set(rows[0].keys())
    required = {
        "request_id",
        "dish_name",
        "hard_filter_pass",
        "blocked_reasons",
        "desired_content_match",
        "satiety_match",
        "nutrition_match",
        "cuisine_match",
        "familiarity_novelty_match",
        "soft_negative_penalty",
        "diversity_bonus",
        "venue_boost",
        "final_score",
        "explanation",
        "rank",
    }
    assert required.issubset(headers)
    assert all(str(row["explanation"]).strip() for row in rows[:20])


def test_m6_artifacts_are_stable_across_reruns() -> None:
    root = Path.cwd()
    subprocess.run(["venv\\Scripts\\python.exe", "scripts\\generate_m6_artifacts.py"], cwd=root, check=True)
    first = (root / "questionnaire_quality_summary.csv").read_text(encoding="utf-8")
    first_demo = (root / "questionnaire_demo_metrics_summary.csv").read_text(encoding="utf-8")
    subprocess.run(["venv\\Scripts\\python.exe", "scripts\\generate_m6_artifacts.py"], cwd=root, check=True)
    second = (root / "questionnaire_quality_summary.csv").read_text(encoding="utf-8")
    second_demo = (root / "questionnaire_demo_metrics_summary.csv").read_text(encoding="utf-8")
    assert first == second
    assert first_demo == second_demo


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        return [dict(row) for row in csv.DictReader(file_obj)]
