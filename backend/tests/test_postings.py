import logging
from pathlib import Path

import pytest

from groundwork.postings import PostingFormatError, WorkModel, load_postings, parse_posting

VALID_HEADER = """company: Fixture Foods (Sample)
title: Inventory Analyst Co-op
location: Mississauga, ON
work_model: hybrid
term: not stated
url: none
"""


def write_file(folder: Path, name: str, content: str, encoding: str = "utf-8") -> Path:
    path = folder / name
    path.write_text(content, encoding=encoding)
    return path


# --- valid postings ----------------------------------------------------------------------------


def test_valid_posting_keeps_every_header_field_and_the_text(fixtures_dir):
    posting = parse_posting(fixtures_dir / "valid-posting.txt")

    assert posting.source_id == "valid-posting"
    assert posting.company == "Fixture Foods (Sample)"
    assert posting.title == "Inventory Analyst Co-op"
    assert posting.location == "Mississauga, ON"
    assert posting.work_model is WorkModel.HYBRID  # file says "Hybrid"
    assert posting.term == "January 4, 2027 to April 30, 2027"
    assert posting.url == "https://example.com/postings/inventory-analyst"
    assert posting.text.startswith("About the role:")
    assert posting.text.endswith("- SQL and Excel")


def test_url_none_is_stored_as_no_link(tmp_path):
    path = write_file(tmp_path, "no-link.txt", VALID_HEADER + "---\nPosting text.")
    assert parse_posting(path).url is None


def test_byte_order_mark_from_notepad_is_ignored(tmp_path):
    path = write_file(tmp_path, "bom.txt", VALID_HEADER + "---\nText.", encoding="utf-8-sig")
    assert parse_posting(path).company == "Fixture Foods (Sample)"


def test_brackets_in_the_posting_text_are_allowed(tmp_path):
    path = write_file(tmp_path, "brackets.txt", VALID_HEADER + "---\nLocation: [Hybrid] Toronto")
    assert parse_posting(path).text == "Location: [Hybrid] Toronto"


# --- template checks ---------------------------------------------------------------------------


def test_leftover_placeholder_in_the_header_is_rejected(fixtures_dir):
    with pytest.raises(PostingFormatError, match="field 'title' still has a template placeholder"):
        parse_posting(fixtures_dir / "leftover-placeholder.txt")


def test_file_without_the_divider_line_is_rejected(fixtures_dir):
    with pytest.raises(PostingFormatError, match="missing the --- line"):
        parse_posting(fixtures_dir / "missing-divider.txt")


def test_missing_field_is_rejected_and_named(fixtures_dir):
    with pytest.raises(PostingFormatError, match=r"missing field\(s\): term"):
        parse_posting(fixtures_dir / "missing-field.txt")


def test_empty_field_counts_as_missing(tmp_path):
    header = VALID_HEADER.replace("Fixture Foods (Sample)", "")
    path = write_file(tmp_path, "empty.txt", header + "---\nText.")
    with pytest.raises(PostingFormatError, match=r"missing field\(s\): company"):
        parse_posting(path)


def test_work_model_outside_the_list_is_rejected(fixtures_dir):
    with pytest.raises(PostingFormatError, match="work_model is 'flexible'"):
        parse_posting(fixtures_dir / "bad-work-model.txt")


def test_posting_text_left_as_the_template_placeholder_is_rejected(fixtures_dir):
    with pytest.raises(PostingFormatError, match="still the template placeholder"):
        parse_posting(fixtures_dir / "placeholder-text.txt")


def test_empty_posting_text_is_rejected(tmp_path):
    path = write_file(tmp_path, "no-text.txt", VALID_HEADER + "---\n\n")
    with pytest.raises(PostingFormatError, match="is empty"):
        parse_posting(path)


def test_misspelled_header_field_is_rejected(tmp_path):
    header = VALID_HEADER.replace("location", "loaction")
    path = write_file(tmp_path, "typo.txt", header + "---\nText.")
    with pytest.raises(PostingFormatError, match="isn't one of the template fields"):
        parse_posting(path)


def test_field_written_twice_is_rejected(tmp_path):
    path = write_file(tmp_path, "twice.txt", VALID_HEADER + "title: Second Title\n---\nText.")
    with pytest.raises(PostingFormatError, match="field 'title' appears twice"):
        parse_posting(path)


def test_file_that_isnt_utf8_is_rejected_instead_of_crashing(tmp_path):
    path = tmp_path / "ansi.txt"
    path.write_bytes((VALID_HEADER + "---\nCafé posting").encode("cp1252"))
    with pytest.raises(PostingFormatError, match="isn't UTF-8"):
        parse_posting(path)


def test_file_name_that_cannot_be_a_source_id_is_rejected(tmp_path):
    path = write_file(tmp_path, "Fixture Foods.txt", VALID_HEADER + "---\nText.")
    with pytest.raises(PostingFormatError, match="lowercase words joined by dashes"):
        parse_posting(path)


# --- loading a folder --------------------------------------------------------------------------


def test_empty_folder_loads_nothing_and_skips_nothing(tmp_path):
    result = load_postings(tmp_path)
    assert result.postings == []
    assert result.skipped == {}


def test_one_bad_file_never_stops_the_rest(fixtures_dir):
    result = load_postings(fixtures_dir)

    assert [posting.source_id for posting in result.postings] == ["valid-posting"]
    # notes.md isn't a .txt, so it shouldn't show up as skipped either
    assert sorted(result.skipped) == [
        "bad-work-model.txt",
        "leftover-placeholder.txt",
        "missing-divider.txt",
        "missing-field.txt",
        "placeholder-text.txt",
    ]


def test_each_skipped_file_is_logged_with_its_reason(fixtures_dir, caplog):
    with caplog.at_level(logging.WARNING):
        load_postings(fixtures_dir)
    assert "Skipped missing-divider.txt: missing the --- line" in caplog.text


def test_missing_folder_stops_the_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="postings folder not found"):
        load_postings(tmp_path / "does-not-exist")


# --- public samples ----------------------------------------------------------------------------


def test_every_sample_posting_passes_validation(samples_dir):
    result = load_postings(samples_dir)
    assert result.skipped == {}
    assert len(result.postings) == len(list(samples_dir.glob("*.txt")))


def test_every_sample_is_labelled_as_a_sample(samples_dir):
    for posting in load_postings(samples_dir).postings:
        assert posting.source_id.startswith("sample-")
        assert posting.company.endswith("(Sample)")
