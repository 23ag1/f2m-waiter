import csv
import subprocess
from pathlib import Path

_READY = False


def test_canonical_request_id_is_consistent_across_artifacts() -> None:
    _ensure_generated()
    root = Path.cwd()
    rows = _read_csv(root / "questionnaire_trace_consistency_report.csv")
    assert rows
    assert all(row["status"] == "pass" for row in rows)
    mapping = _read_csv(root / "questionnaire_request_id_mapping.csv")
    assert mapping
    for row in mapping:
        canonical = row["canonical_request_id"]
        if canonical:
            assert canonical.startswith("qreq_")


def test_repeated_generation_is_deterministic_for_consistency_exports() -> None:
    _ensure_generated(force=True)
    root = Path.cwd()
    first_trace = (root / "questionnaire_trace_consistency_report.csv").read_text(encoding="utf-8")
    first_map = (root / "questionnaire_request_id_mapping.csv").read_text(encoding="utf-8")
    _ensure_generated(force=True)
    second_trace = (root / "questionnaire_trace_consistency_report.csv").read_text(encoding="utf-8")
    second_map = (root / "questionnaire_request_id_mapping.csv").read_text(encoding="utf-8")
    assert first_trace == second_trace
    assert first_map == second_map


def _ensure_generated(force: bool = False) -> None:
    global _READY
    if _READY and not force:
        return
    root = Path.cwd()
    subprocess.run(["venv\\Scripts\\python.exe", "scripts\\generate_qa_cleanup_artifacts.py"], cwd=root, check=True)
    _READY = True


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        return [dict(row) for row in csv.DictReader(file_obj)]
