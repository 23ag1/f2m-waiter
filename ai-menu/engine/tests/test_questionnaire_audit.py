from pathlib import Path

from app.pipelines.questionnaire_audit import run_questionnaire_audit
from app.pipelines.questionnaire_seed import run_seed_questionnaire_extraction
from app.repositories.file_repository import FileRepository
from app.config.taxonomy import load_runtime_taxonomy


def test_audit_writes_requested_artifacts(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    repo = FileRepository(base_dir=derived)
    taxonomy = load_runtime_taxonomy(Path("docs/runtime_taxonomy_resolved_v1.json"))
    run_seed_questionnaire_extraction("docs/cust.json", repository=repo, taxonomy=taxonomy)

    stats = run_questionnaire_audit(source_users_path="docs/cust.json", derived_dir=derived)

    assert stats.hard_constraints_total > 0
    assert (derived / "audit" / "questionnaire_constraints_by_user.csv").exists()
    assert (derived / "audit" / "questionnaire_features_by_user.csv").exists()
    assert (derived / "audit" / "questionnaire_unmapped_phrases.csv").exists()
    assert (derived / "audit" / "seed_events_summary.csv").exists()
