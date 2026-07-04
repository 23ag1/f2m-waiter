import subprocess
from pathlib import Path

_READY = False


def test_markdown_reports_are_generated() -> None:
    _ensure_generated()
    root = Path.cwd()
    assert (root / "questionnaire_run_report.md").exists()
    assert (root / "questionnaire_validation_report.md").exists()
    assert (root / "questionnaire_reports_index.md").exists()
    req_dir = root / "questionnaire_request_reports"
    assert req_dir.exists()
    request_files = sorted(req_dir.glob("qreq_*.md"))
    assert request_files


def test_request_reports_match_request_count_and_trace_visibility() -> None:
    _ensure_generated()
    root = Path.cwd()
    req_count = _count_jsonl_rows(root / "questionnaire_requests.jsonl")
    request_files = sorted((root / "questionnaire_request_reports").glob("qreq_*.md"))
    assert len(request_files) == req_count
    run_report = (root / "questionnaire_run_report.md").read_text(encoding="utf-8")
    assert "inconsistent_trace_cases" in run_report


def test_blocked_dishes_do_not_appear_in_main_recommendation_tables() -> None:
    _ensure_generated()
    root = Path.cwd()
    blocked_pairs = _load_blocked_pairs(root / "questionnaire_candidate_filter_decisions.jsonl")
    recommendations = _read_csv(root / "questionnaire_recommendations_sample.csv")
    for row in recommendations:
        pair = (row.get("request_id", ""), row.get("dish_id", ""))
        assert pair not in blocked_pairs


def test_missing_source_is_reported_as_warning() -> None:
    _ensure_generated()
    root = Path.cwd()
    target = root / "questionnaire_gate_results.csv"
    backup = root / "questionnaire_gate_results.csv.bak_test"
    if backup.exists():
        backup.unlink()
    target.rename(backup)
    try:
        subprocess.run(["venv\\Scripts\\python.exe", "scripts\\generate_questionnaire_reports.py"], cwd=root, check=True)
        report = (root / "questionnaire_run_report.md").read_text(encoding="utf-8")
        assert "missing source artifact" in report
    finally:
        backup.rename(target)
    subprocess.run(["venv\\Scripts\\python.exe", "scripts\\generate_questionnaire_reports.py"], cwd=root, check=True)


def test_report_outputs_are_deterministic_on_rerun() -> None:
    _ensure_generated()
    root = Path.cwd()
    first = _snapshot_reports(root)
    subprocess.run(["venv\\Scripts\\python.exe", "scripts\\generate_questionnaire_reports.py"], cwd=root, check=True)
    second = _snapshot_reports(root)
    assert first == second


def _ensure_generated() -> None:
    global _READY
    if _READY:
        return
    root = Path.cwd()
    subprocess.run(["venv\\Scripts\\python.exe", "scripts\\generate_qa_cleanup_artifacts.py"], cwd=root, check=True)
    _READY = True


def _snapshot_reports(root: Path) -> dict[str, str]:
    snapshot = {
        "run": (root / "questionnaire_run_report.md").read_text(encoding="utf-8"),
        "validation": (root / "questionnaire_validation_report.md").read_text(encoding="utf-8"),
        "index": (root / "questionnaire_reports_index.md").read_text(encoding="utf-8"),
    }
    for path in sorted((root / "questionnaire_request_reports").glob("qreq_*.md")):
        snapshot[path.name] = path.read_text(encoding="utf-8")
    return snapshot


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])


def _read_csv(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open("r", encoding="utf-8", newline="") as file_obj:
        return [dict(row) for row in csv.DictReader(file_obj)]


def _load_blocked_pairs(path: Path) -> set[tuple[str, str]]:
    import json

    if not path.exists():
        return set()
    pairs: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not bool(row.get("hard_filter_pass", False)):
            pairs.add((str(row.get("request_id", "")), str(row.get("dish_id", ""))))
    return pairs
