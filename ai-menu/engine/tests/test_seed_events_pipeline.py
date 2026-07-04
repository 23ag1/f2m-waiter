from pathlib import Path

from app.pipelines.seed_events import ingest_seed_purchase_events
from app.repositories.file_repository import FileRepository


def test_seed_event_ingestion_writes_events_and_items(tmp_path: Path) -> None:
    repo = FileRepository(base_dir=tmp_path / "derived")
    stats = ingest_seed_purchase_events(
        users_path=Path("docs/cust.json"),
        repository=repo,
    )

    assert stats.users_processed > 0
    assert stats.events_written > 0
    assert stats.items_written == stats.events_written
    assert repo.events_path.exists()
    assert repo.event_items_path.exists()
