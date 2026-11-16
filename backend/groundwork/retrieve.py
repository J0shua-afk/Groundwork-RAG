"""Finds the chunks closest to a question, narrowed to a company when the question names one."""

import re
from dataclasses import dataclass

from groundwork import config
from groundwork.store import Hit, Store

# no apostrophe, so "loblaw's" splits into "loblaw" + "s"; & stays so "at&t" isn't "at"
WORD_PATTERN = re.compile(r"[a-z0-9&]+")


@dataclass(frozen=True)
class Retrieval:
    hits: list[Hit]
    companies: list[str]  # the filter that was used, empty for none


def retrieve(store: Store, question: str, vector: list[float], companies: list[str]) -> Retrieval:
    named = companies_named(question, companies)
    return Retrieval(store.search(vector, config.TOP_K, named or None), named)


def companies_named(question: str, companies: list[str]) -> list[str]:
    # a company counts as named when its first word shows up as a whole word ("Loblaw" for
    # "Loblaw Companies Limited"). covers how people actually ask. the weak spot is a generic
    # first word like "Ontario", so check it against the real company list
    words = set(WORD_PATTERN.findall(question.lower()))
    return [company for company in companies if first_word(company) in words]


def first_word(company: str) -> str | None:
    words = WORD_PATTERN.findall(company.lower())
    return words[0] if words else None


def below_threshold(hits: list[Hit]) -> bool:
    return not hits or hits[0].score < config.REFUSAL_THRESHOLD
