"""Asks Claude to answer from the retrieved chunks, with numbered citations."""

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic

from groundwork import config
from groundwork.store import Hit

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "answer.md").read_text(encoding="utf-8")

# structured output, so "is it in the postings?" comes back as a field, not a phrase to grep for
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "in_postings": {
            "type": "boolean",
            "description": "true only if the sources contain the answer",
        },
        "answer": {
            "type": "string",
            "description": "the answer with [n] citations, or empty when in_postings is false",
        },
    },
    "required": ["in_postings", "answer"],
    "additionalProperties": False,
}

# [1], [2][3] or [1, 2]
CITATION_PATTERN = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


class GenerationError(Exception):
    """Claude didn't give a usable answer."""


@dataclass(frozen=True)
class Generation:
    in_postings: bool
    answer: str  # citations renumbered [1], [2]... in order of first mention
    cited: list[Hit]  # cited[0] is what [1] points at, and so on
    input_tokens: int
    output_tokens: int


def generate(client: anthropic.Anthropic, question: str, hits: list[Hit]) -> Generation:
    """Answer the question from the hits, or report that they don't contain the answer."""
    response = client.messages.create(
        model=config.GENERATION_MODEL,
        max_tokens=config.MAX_OUTPUT_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": format_prompt(question, hits)}],
        output_config={
            "effort": config.GENERATION_EFFORT,
            "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
        },
    )
    # anything but end_turn means no trustworthy JSON: a safety refusal, or cut off at max_tokens
    if response.stop_reason != "end_turn":
        raise GenerationError(f"Claude stopped early ({response.stop_reason})")
    text = next((block.text for block in response.content if block.type == "text"), None)
    try:
        reply = json.loads(text)
    except (TypeError, ValueError):
        raise GenerationError("Claude's reply wasn't the JSON that was asked for") from None

    answer, numbers = renumber_citations(reply["answer"], len(hits))
    return Generation(
        in_postings=reply["in_postings"],
        answer=answer,
        cited=[hits[number - 1] for number in numbers],
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def format_prompt(question: str, hits: list[Hit]) -> str:
    sources = "\n".join(format_source(number, hit) for number, hit in enumerate(hits, start=1))
    question = html.escape(question, quote=False)
    return f"<sources>\n{sources}\n</sources>\n\n<question>\n{question}\n</question>"


def format_source(number: int, hit: Hit) -> str:
    attributes = {
        "number": number,
        "posting": hit.source_id,
        "company": hit.company,
        "title": hit.title,
        "location": hit.location,
        "work_model": hit.work_model,
        "term": hit.term,
    }
    tag = " ".join(f'{name}="{html.escape(str(value))}"' for name, value in attributes.items())
    # escaped so a posting can't close its own <source> tag and pass itself off as instructions
    return f"<source {tag}>\n{html.escape(hit.text, quote=False)}\n</source>"


def renumber_citations(answer: str, source_count: int) -> tuple[str, list[int]]:
    """Keep only real source numbers and renumber them 1, 2, 3 in the order they're first used."""
    order: list[int] = []

    def replace(match: re.Match) -> str:
        numbers = [int(number) for number in re.findall(r"\d+", match.group(1))]
        kept = list(dict.fromkeys(n for n in numbers if 1 <= n <= source_count))
        for number in kept:
            if number not in order:
                order.append(number)
        return "".join(f"[{order.index(number) + 1}]" for number in kept)

    return CITATION_PATTERN.sub(replace, answer).strip(), order
