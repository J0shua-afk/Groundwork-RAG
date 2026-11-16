"""Loads posting .txt files and validates them against the template."""

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)

HEADER_FIELDS = ("company", "title", "location", "work_model", "term", "url")

# separates the header from the posting text.
DIVIDER = "---"

# file names double as source IDs in citations, so keep them clean
SOURCE_ID_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


class WorkModel(StrEnum):
    ON_SITE = "on-site"
    HYBRID = "hybrid"
    REMOTE = "remote"
    NOT_STATED = "not stated"


class PostingFormatError(Exception):
    """Posting file doesn't match the template."""


@dataclass(frozen=True)
class Posting:
    source_id: str
    company: str
    title: str
    location: str
    work_model: WorkModel
    term: str
    url: str | None  # None when the header says "none"
    text: str


@dataclass(frozen=True)
class LoadResult:
    postings: list[Posting]
    skipped: dict[str, str]  # file name -> reason


def load_postings(folder: str | Path) -> LoadResult:
    """Parse every .txt posting in a folder. Bad files get logged and skipped, not raised."""
    folder = Path(folder)
    if not folder.is_dir():
        # wrong path is a setup problem, not a bad posting, so fail loudly
        raise FileNotFoundError(f"postings folder not found: {folder}")

    postings: list[Posting] = []
    skipped: dict[str, str] = {}
    for path in sorted(folder.glob("*.txt")):
        try:
            postings.append(parse_posting(path))
        except PostingFormatError as error:
            skipped[path.name] = str(error)
            logger.warning("Skipped %s: %s", path.name, error)
    return LoadResult(postings, skipped)


def parse_posting(path: str | Path) -> Posting:
    """Read and validate one posting file. Raises PostingFormatError on the first problem."""
    path = Path(path)
    if not SOURCE_ID_PATTERN.fullmatch(path.stem):
        raise PostingFormatError(
            "file name must be lowercase words joined by dashes, like loblaw-applied-ml.txt"
        )

    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise PostingFormatError("file isn't UTF-8, re-save it with UTF-8 encoding") from None

    header_lines, text = split_at_divider(raw)
    header = parse_header(header_lines)
    check_posting_text(text)

    try:
        work_model = WorkModel(header["work_model"].lower())
    except ValueError:
        allowed = " | ".join(model.value for model in WorkModel)
        raise PostingFormatError(
            f"work_model is {header['work_model']!r}, but it must be one of: {allowed}"
        ) from None

    return Posting(
        source_id=path.stem,
        company=header["company"],
        title=header["title"],
        location=header["location"],
        work_model=work_model,
        term=header["term"],
        url=None if header["url"].lower() == "none" else header["url"],
        text=text,
    )


def split_at_divider(raw: str) -> tuple[list[str], str]:
    lines = raw.splitlines()
    for number, line in enumerate(lines):
        # first one wins, the posting itself might use --- as a separator
        if line.strip() == DIVIDER:
            return lines[:number], "\n".join(lines[number + 1 :]).strip()
    raise PostingFormatError("missing the --- line between the header and the posting text")


def parse_header(lines: list[str]) -> dict[str, str]:
    header: dict[str, str] = {}
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        # partition, not split, so the colon in "https://" stays in the value
        name, colon, value = line.partition(":")
        name = name.strip().lower()
        if not colon or name not in HEADER_FIELDS:
            raise PostingFormatError(
                f"header line {number} isn't one of the template fields: {line.strip()!r}"
            )
        if name in header:
            raise PostingFormatError(f"field '{name}' appears twice")
        header[name] = value.strip()

    missing = [name for name in HEADER_FIELDS if not header.get(name)]
    if missing:
        raise PostingFormatError(f"missing field(s): {', '.join(missing)}")

    # header only, real postings sometimes have brackets in the text ("[Hybrid]" etc.)
    for name, value in header.items():
        if "[" in value:
            raise PostingFormatError(f"field '{name}' still has a template placeholder: {value}")
    return header


def check_posting_text(text: str) -> None:
    if not text:
        raise PostingFormatError("the posting text after the --- line is empty")
    if text.startswith("[") and text.endswith("]") and "\n" not in text:
        raise PostingFormatError("the posting text is still the template placeholder")
