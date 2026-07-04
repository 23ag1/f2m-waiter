import csv
import subprocess
from pathlib import Path

_READY = False


def test_strict_case_has_no_blocked_leak_and_no_bread_like_items() -> None:
    _ensure_generated()
    root = Path.cwd()
    md = (root / "questionnaire_strict_case_validation.md").read_text(encoding="utf-8")
    assert "pass: `yes`" in md
    rows = _read_csv(root / "questionnaire_strict_case_blocked_vs_presented.csv")
    assert rows
    assert all(row["status"] != "fail" for row in rows)


def test_strict_case_expected_conflicts_are_blocked() -> None:
    _ensure_generated()
    root = Path.cwd()
    blocked = _read_csv(root / "questionnaire_blocked_dishes_sample.csv")
    strict_rows = [row for row in blocked if row["request_id"] == "qreq_000003"]
    keys = {row["blocked_reason_key"] for row in strict_rows}
    assert any("hard_gluten" in key for key in keys)
    assert any("hard_mushroom" in key for key in keys)


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
