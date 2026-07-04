from pathlib import Path
import json

from app.config.taxonomy import load_runtime_taxonomy
from app.pipelines.questionnaire_seed import run_seed_questionnaire_extraction
from app.repositories.file_repository import FileRepository


def test_seed_questionnaire_extraction_writes_outputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "derived"
    repo = FileRepository(base_dir=out_dir)
    taxonomy = load_runtime_taxonomy(Path("docs/runtime_taxonomy_resolved_v1.json"))

    stats = run_seed_questionnaire_extraction(
        users_path=Path("docs/cust.json"),
        repository=repo,
        taxonomy=taxonomy,
    )

    assert stats.users_processed > 0
    assert repo.questionnaire_submissions_path.exists()
    assert repo.user_constraints_path.exists()
    assert repo.user_features_path.exists()


def test_required_users_have_hard_constraints(tmp_path: Path) -> None:
    out_dir = tmp_path / "derived"
    repo = FileRepository(base_dir=out_dir)
    taxonomy = load_runtime_taxonomy(Path("docs/runtime_taxonomy_resolved_v1.json"))
    run_seed_questionnaire_extraction(
        users_path=Path("docs/cust.json"),
        repository=repo,
        taxonomy=taxonomy,
    )

    rows = [
        json.loads(line.strip())
        for line in repo.user_constraints_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    required = {1, 3, 5, 8, 9}
    users_with_hard: set[int] = set()
    for row in rows:
        if row.get("scope") != "hard":
            continue
        users_with_hard.add(int(row["user_id"]))

    assert required.issubset(users_with_hard)


def test_alpha_gal_is_not_mapped_to_pork(tmp_path: Path) -> None:
    out_dir = tmp_path / "derived"
    repo = FileRepository(base_dir=out_dir)
    taxonomy = load_runtime_taxonomy(Path("docs/runtime_taxonomy_resolved_v1.json"))
    run_seed_questionnaire_extraction(
        users_path=Path("docs/cust.json"),
        repository=repo,
        taxonomy=taxonomy,
    )
    rows = [
        json.loads(line.strip())
        for line in repo.user_constraints_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    user9 = [row for row in rows if int(row["user_id"]) == 9]
    keys = {row["constraint_key"] for row in user9}
    assert "mammalian_red_meat" in keys
    assert "pork" not in keys
