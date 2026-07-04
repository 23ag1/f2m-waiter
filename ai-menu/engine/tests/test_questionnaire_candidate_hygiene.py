import csv
import subprocess
from pathlib import Path

_READY = False


def test_non_recommendable_leaks_are_zero_in_main_topn() -> None:
    _ensure_generated()
    root = Path.cwd()
    rows = _read_csv(root / "questionnaire_non_recommendable_leaks.csv")
    assert rows
    assert all(int(row["leaked_item_count"]) == 0 for row in rows)
    assert all(row["status"] == "pass" for row in rows)


def test_candidate_hygiene_report_is_green() -> None:
    _ensure_generated()
    root = Path.cwd()
    rows = _read_csv(root / "questionnaire_candidate_hygiene_report.csv")
    status = {row["metric"]: row["value"] for row in rows}
    assert status.get("status") == "pass"
    assert int(status.get("total_leaked_items", "1")) == 0


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
