import csv
import statistics
import subprocess
from pathlib import Path

_READY = False


def test_nutrition_match_has_meaningful_variation() -> None:
    _ensure_generated()
    root = Path.cwd()
    rows = _read_csv(root / "questionnaire_nutrition_match_audit.csv")
    assert rows
    values = [float(row["nutrition_match"]) for row in rows]
    assert max(values) > min(values)
    assert statistics.pstdev(values) > 0.05


def test_nutrition_case_doc_reports_variability() -> None:
    _ensure_generated()
    root = Path.cwd()
    text = (root / "questionnaire_nutrition_case_examples.md").read_text(encoding="utf-8")
    assert "nutrition_match_std" in text
    assert "explanation now reflects more discriminative nutrition signal" in text


def _ensure_generated() -> None:
    global _READY
    if _READY:
        return
    root = Path.cwd()
    subprocess.run(["venv\\Scripts\\python.exe", "scripts\\generate_qa_cleanup_artifacts.py"], cwd=root, check=True)
    _READY = True


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        return [dict(row) for row in csv.DictReader(file_obj)]
