"""Splits a posting into ~500-token chunks for embedding, cutting at headings where it can."""

import re
from dataclasses import dataclass

from groundwork import config
from groundwork.postings import Posting

# word + its trailing whitespace, so "".join() gives back the original text, line breaks and all
WORD_PATTERN = re.compile(r"\S+\s*")
BULLET_PATTERN = re.compile(r"([-*•]|\d+[.)])\s")


@dataclass(frozen=True)
class Chunk:
    source_id: str
    index: int
    text: str


def chunk_posting(
    posting: Posting,
    max_tokens: int = config.CHUNK_TOKENS,
    overlap_tokens: int = config.CHUNK_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Pack whole sections into chunks. Only a section too big for one chunk gets split."""
    max_words = tokens_to_words(max_tokens)
    overlap_words = tokens_to_words(overlap_tokens)
    if overlap_words >= max_words:
        raise ValueError("the overlap must be smaller than the chunk size")

    finished: list[list[str]] = []
    current: list[str] = []
    for section in split_sections(posting.text):
        words = WORD_PATTERN.findall(section)
        if len(current) + len(words) <= max_words:
            current += words
            continue
        if current:
            finished.append(current)  # cutting at a heading, so no overlap needed
        windows = split_into_windows(words, max_words, overlap_words)
        finished += windows[:-1]
        current = windows[-1]  # might still have room for the next section
    if current:
        finished.append(current)

    # postings from the same company share a ton of boilerplate, the prefix keeps them apart
    prefix = f"{posting.company} — {posting.title}"
    return [
        Chunk(posting.source_id, index, f"{prefix}\n\n{''.join(words).strip()}")
        for index, words in enumerate(finished)
    ]


def split_sections(text: str) -> list[str]:
    sections: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if is_heading(line) and current.strip():
            sections.append(current)
            current = ""
        current += line
    if current.strip():
        sections.append(current)
    return sections


def is_heading(line: str) -> bool:
    # pasting into a .txt loses bold and font sizes, so this is a best guess. being a bit
    # loose is fine, a false positive just adds a spot where a chunk *could* be cut
    text = line.strip()
    if not text or len(text.split()) > config.HEADING_MAX_WORDS or BULLET_PATTERN.match(text):
        return False
    if text.startswith("#") or text.endswith(":"):
        return True
    if text[-1] in ".!?,;":
        return False
    if text.isupper():
        return True
    # title case, ignoring little words like "to" and "and"
    long_words = [word for word in re.findall(r"[A-Za-z']+", text) if len(word) >= 4]
    return bool(long_words) and all(word[0].isupper() for word in long_words)


def split_into_windows(words: list[str], max_words: int, overlap_words: int) -> list[list[str]]:
    windows: list[list[str]] = []
    start = 0
    while True:
        windows.append(words[start : start + max_words])
        if start + max_words >= len(words):
            return windows
        start += max_words - overlap_words


def tokens_to_words(tokens: int) -> int:
    # ballpark is fine here, the embedding model takes way more than 500 tokens anyway
    return max(1, round(tokens / config.TOKENS_PER_WORD))
