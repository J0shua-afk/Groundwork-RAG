import os
import re

import pytest

from groundwork import config
from groundwork.chunk import Chunk
from groundwork.postings import Posting, WorkModel
from groundwork.store import Store, to_vector

SOURCE_ID = "test-integration-posting"


def make_posting() -> Posting:
    return Posting(
        source_id=SOURCE_ID,
        company="Fixture Foods (Sample)",
        title="Inventory Analyst Co-op",
        location="Mississauga, ON",
        work_model=WorkModel.HYBRID,
        term="not stated",
        url=None,
        text="not stored, chunks hold the text",
    )


def make_chunks(count: int) -> tuple[list[Chunk], list[list[float]]]:
    chunks = [Chunk(SOURCE_ID, index, f"chunk {index}") for index in range(count)]
    vectors = [[(index + 1) / 1000] * config.EMBEDDING_DIMENSIONS for index in range(count)]
    return chunks, vectors


def chunk_count(store: Store) -> int:
    query = "select count(*) from chunks where source_id = %s"
    return store.conn.execute(query, (SOURCE_ID,)).fetchone()[0]


def project_ref(url: str) -> str | None:
    # one project can have several URLs (session/transaction port, new password), but the
    # project ref is in all of them: pooler user "postgres.<ref>", or host "db.<ref>.supabase.co".
    # parsed by hand because urlsplit blows up on a password with [ ] in it
    userinfo, _, rest = url.strip().split("://", 1)[-1].rpartition("@")
    user, _, ref = userinfo.partition(":")[0].partition(".")
    if user and ref:
        return ref.lower()
    host = rest.split("/")[0].split(":")[0].lower()
    match = re.fullmatch(r"db\.([a-z0-9]+)\.supabase\.co", host)
    return match.group(1) if match else None


def test_vector_is_sent_as_pgvector_text():
    assert to_vector([1.0, 0.5, -2.0]) == "[1.0,0.5,-2.0]"


# --- the private-project guard -----------------------------------------------------------------

SESSION = "postgresql://postgres.abcref:pw1@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
TRANSACTION = "postgresql://postgres.abcref:pw2@aws-0-us-east-1.pooler.supabase.com:6543/postgres"


def test_session_and_transaction_urls_of_one_project_share_a_ref():
    assert project_ref(SESSION) == project_ref(TRANSACTION) == "abcref"


def test_whitespace_and_case_dont_hide_a_match():
    assert project_ref(f"  {SESSION.replace('abcref', 'ABCREF')}\n") == "abcref"


def test_password_with_an_unescaped_at_sign_still_parses():
    assert project_ref(SESSION.replace("pw1", "p@ss")) == "abcref"


def test_password_left_in_template_brackets_still_parses():
    assert project_ref(SESSION.replace("pw1", "[pw1]")) == "abcref"


def test_direct_connection_ref_comes_from_the_host():
    assert project_ref("postgresql://postgres:pw@db.xyzref.supabase.co:5432/postgres") == "xyzref"


def test_url_without_a_project_ref_gives_none():
    assert project_ref("postgresql://someone:pw@localhost:5432/postgres") is None


# --- against a real database -------------------------------------------------------------------


@pytest.fixture
def store():
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_URL isn't set")
    private_url = os.environ.get("PRIVATE_DATABASE_URL", "").strip()
    if private_url:
        test_ref, private_ref = project_ref(url), project_ref(private_url)
        # can't tell which project one of them is? don't risk it
        if test_ref is None or private_ref is None or test_ref == private_ref:
            pytest.exit(
                "refusing to run: TEST_DATABASE_URL may point at the private project. "
                "point it at the public one",
                returncode=1,
            )
    store = Store.connect(url)
    # everything a test writes is rolled back, so this is safe against a real project
    with store.conn.transaction(force_rollback=True):
        yield store
    store.close()


@pytest.mark.integration
def test_saved_posting_is_listed_with_its_hash_and_settings(store):
    store.save_posting(make_posting(), "hash-1", "settings-1", *make_chunks(2))

    record = store.ingested()[SOURCE_ID]
    assert (record.file_hash, record.settings) == ("hash-1", "settings-1")
    assert chunk_count(store) == 2


@pytest.mark.integration
def test_saving_again_replaces_the_chunks_instead_of_adding_to_them(store):
    store.save_posting(make_posting(), "hash-1", "settings-1", *make_chunks(3))
    store.save_posting(make_posting(), "hash-2", "settings-1", *make_chunks(2))

    assert chunk_count(store) == 2
    assert store.ingested()[SOURCE_ID].file_hash == "hash-2"


@pytest.mark.integration
def test_deleting_a_posting_removes_its_chunks(store):
    store.save_posting(make_posting(), "hash-1", "settings-1", *make_chunks(2))
    store.delete_posting(SOURCE_ID)

    assert SOURCE_ID not in store.ingested()
    assert chunk_count(store) == 0


@pytest.mark.integration
def test_count_goes_up_by_one_per_posting(store):
    before = store.count_postings()
    store.save_posting(make_posting(), "hash-1", "settings-1", *make_chunks(1))
    assert store.count_postings() == before + 1


@pytest.mark.integration
def test_vectors_and_work_model_are_stored_as_expected(store):
    store.save_posting(make_posting(), "hash-1", "settings-1", *make_chunks(1))

    dims = store.conn.execute(
        "select extensions.vector_dims(embedding) from chunks where source_id = %s", (SOURCE_ID,)
    ).fetchone()[0]
    work_model = store.conn.execute(
        "select work_model from postings where source_id = %s", (SOURCE_ID,)
    ).fetchone()[0]
    assert dims == config.EMBEDDING_DIMENSIONS
    assert work_model == "hybrid"
