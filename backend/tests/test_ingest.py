import pytest

from groundwork import config
from groundwork.ingest import (
    IngestError,
    SyncPlan,
    current_settings,
    file_hash,
    plan_sync,
    run_ingest,
)
from groundwork.store import IngestedPosting

SETTINGS = "test-settings"

POSTING = """company: Fixture Foods (Sample)
title: Inventory Analyst Co-op
location: Mississauga, ON
work_model: hybrid
term: not stated
url: none
---
{text}
"""


def write_posting(folder, source_id: str, text: str = "About us:\nWe make tools."):
    path = folder / f"{source_id}.txt"
    path.write_text(POSTING.format(text=text), encoding="utf-8")
    return path


def stored(digest: str, settings: str = SETTINGS) -> IngestedPosting:
    return IngestedPosting(digest, settings)


# --- planning ----------------------------------------------------------------------------------


def test_file_not_in_the_database_is_new():
    assert plan_sync({"alpha": "h1"}, set(), {}, SETTINGS).new == ["alpha"]


def test_same_hash_and_settings_is_left_alone():
    plan = plan_sync({"alpha": "h1"}, set(), {"alpha": stored("h1")}, SETTINGS)
    assert plan.unchanged == ["alpha"]
    assert plan.changed == []


def test_edited_file_is_changed():
    plan = plan_sync({"alpha": "h2"}, set(), {"alpha": stored("h1")}, SETTINGS)
    assert plan.changed == ["alpha"]


def test_new_settings_mark_every_posting_changed():
    ingested = {"alpha": stored("h1", "old"), "bravo": stored("h2", "old")}
    plan = plan_sync({"alpha": "h1", "bravo": "h2"}, set(), ingested, SETTINGS)
    assert plan.changed == ["alpha", "bravo"]


def test_force_marks_every_posting_changed():
    plan = plan_sync({"alpha": "h1"}, set(), {"alpha": stored("h1")}, SETTINGS, force=True)
    assert plan.changed == ["alpha"]


def test_file_gone_from_the_folder_is_deleted():
    plan = plan_sync({}, set(), {"alpha": stored("h1")}, SETTINGS)
    assert plan.deleted == ["alpha"]


def test_broken_file_keeps_its_old_version_instead_of_being_deleted():
    plan = plan_sync({}, {"alpha"}, {"alpha": stored("h1")}, SETTINGS)
    assert plan.kept == ["alpha"]
    assert plan.deleted == []


def test_settings_label_changes_when_a_chunk_setting_does(monkeypatch):
    before = current_settings()
    monkeypatch.setattr(config, "CHUNK_TOKENS", 300)
    assert current_settings() != before


def test_file_hash_changes_when_the_file_does(tmp_path):
    path = write_posting(tmp_path, "alpha", text="One.")
    before = file_hash(path)
    write_posting(tmp_path, "alpha", text="Two.")
    assert file_hash(path) != before


# --- running a sync ----------------------------------------------------------------------------


def test_first_run_saves_every_posting_with_a_vector_per_chunk(tmp_path, fake_store, fake_embedder):
    write_posting(tmp_path, "alpha")
    write_posting(tmp_path, "bravo")

    result = run_ingest(tmp_path, fake_store, fake_embedder)

    assert result.plan.new == ["alpha", "bravo"]
    assert fake_store.count_postings() == 2
    for _, chunks, vectors in fake_store.rows.values():
        # fake vectors are text lengths, so this checks every chunk got its own vector
        assert [vector[0] for vector in vectors] == [len(chunk.text) for chunk in chunks]


def test_second_run_embeds_nothing(tmp_path, fake_store, fake_embedder):
    write_posting(tmp_path, "alpha")
    run_ingest(tmp_path, fake_store, fake_embedder)

    result = run_ingest(tmp_path, fake_store, fake_embedder)

    assert result.plan.unchanged == ["alpha"]
    assert fake_embedder.calls[1] == []


def test_edited_posting_is_re_embedded_and_replaced(tmp_path, fake_store, fake_embedder):
    write_posting(tmp_path, "alpha", text="Old text.")
    run_ingest(tmp_path, fake_store, fake_embedder)
    old_hash = fake_store.ingested()["alpha"].file_hash

    write_posting(tmp_path, "alpha", text="New text.")
    result = run_ingest(tmp_path, fake_store, fake_embedder)

    record, chunks, _ = fake_store.rows["alpha"]
    assert result.plan.changed == ["alpha"]
    assert record.file_hash != old_hash
    assert chunks[0].text.endswith("New text.")


def test_deleted_file_is_removed_from_the_database(tmp_path, fake_store, fake_embedder):
    write_posting(tmp_path, "alpha")
    write_posting(tmp_path, "bravo")
    run_ingest(tmp_path, fake_store, fake_embedder)

    (tmp_path / "bravo.txt").unlink()
    result = run_ingest(tmp_path, fake_store, fake_embedder)

    assert result.plan.deleted == ["bravo"]
    assert list(fake_store.ingested()) == ["alpha"]


def test_broken_edit_keeps_the_last_good_version(tmp_path, fake_store, fake_embedder):
    write_posting(tmp_path, "alpha", text="Good text.")
    run_ingest(tmp_path, fake_store, fake_embedder)

    (tmp_path / "alpha.txt").write_text("header and divider got deleted", encoding="utf-8")
    result = run_ingest(tmp_path, fake_store, fake_embedder)

    assert result.plan.kept == ["alpha"]
    assert fake_store.rows["alpha"][1][0].text.endswith("Good text.")


def test_bad_file_does_not_stop_the_good_ones(tmp_path, fake_store, fake_embedder):
    write_posting(tmp_path, "alpha")
    (tmp_path / "broken.txt").write_text("not a posting", encoding="utf-8")

    run_ingest(tmp_path, fake_store, fake_embedder)

    assert list(fake_store.ingested()) == ["alpha"]


def test_empty_folder_wont_wipe_the_database_without_permission(
    tmp_path, fake_store, fake_embedder
):
    write_posting(tmp_path, "alpha")
    run_ingest(tmp_path, fake_store, fake_embedder)
    (tmp_path / "alpha.txt").unlink()

    with pytest.raises(IngestError, match="--yes"):
        run_ingest(tmp_path, fake_store, fake_embedder)
    assert fake_store.count_postings() == 1

    run_ingest(tmp_path, fake_store, fake_embedder, allow_empty=True)
    assert fake_store.count_postings() == 0


def test_empty_folder_and_empty_database_is_fine(tmp_path, fake_store, fake_embedder):
    result = run_ingest(tmp_path, fake_store, fake_embedder)
    assert result.plan == SyncPlan([], [], [], [], [])


def test_dry_run_writes_nothing_and_embeds_nothing(tmp_path, fake_store, fake_embedder):
    write_posting(tmp_path, "alpha")

    result = run_ingest(tmp_path, fake_store, fake_embedder, dry_run=True)

    assert result.plan.new == ["alpha"]
    assert fake_store.count_postings() == 0
    assert fake_embedder.calls == []
