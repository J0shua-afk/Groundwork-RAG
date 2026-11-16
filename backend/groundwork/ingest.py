"""Syncs a postings folder into its database: embeds new or edited postings, drops deleted ones.

python -m groundwork.ingest private     data/postings -> PRIVATE_DATABASE_URL
python -m groundwork.ingest public      samples       -> PUBLIC_DATABASE_URL
"""

import argparse
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import psycopg

from groundwork import config
from groundwork.chunk import chunk_posting
from groundwork.embed import VoyageEmbedder
from groundwork.postings import load_postings
from groundwork.store import IngestedPosting, Store

logger = logging.getLogger(__name__)


class IngestError(Exception):
    """Ingest refused to run."""


@dataclass(frozen=True)
class SyncPlan:
    new: list[str]
    changed: list[str]
    unchanged: list[str]
    deleted: list[str]
    kept: list[str]  # broken now but already in the db, left alone until fixed


@dataclass(frozen=True)
class IngestResult:
    plan: SyncPlan
    tokens_counted: int
    tokens_estimated: int


def current_settings() -> str:
    # anything that changes the stored chunks or vectors belongs here, so changing it re-embeds
    return (
        f"{config.EMBEDDING_MODEL}/{config.EMBEDDING_DIMENSIONS} chunk={config.CHUNK_TOKENS} "
        f"overlap={config.CHUNK_OVERLAP_TOKENS} tpw={config.TOKENS_PER_WORD} "
        f"heading={config.HEADING_MAX_WORDS}"
    )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan_sync(
    on_disk: dict[str, str],
    broken: set[str],
    ingested: dict[str, IngestedPosting],
    settings: str,
    force: bool = False,
) -> SyncPlan:
    new: list[str] = []
    changed: list[str] = []
    unchanged: list[str] = []
    for source_id, digest in sorted(on_disk.items()):
        stored = ingested.get(source_id)
        if stored is None:
            new.append(source_id)
        elif force or stored.file_hash != digest or stored.settings != settings:
            changed.append(source_id)
        else:
            unchanged.append(source_id)

    gone = sorted(ingested.keys() - on_disk.keys())
    # a typo in a file shouldn't pull its posting off the site, so broken files aren't deleted
    kept = [source_id for source_id in gone if source_id in broken]
    deleted = [source_id for source_id in gone if source_id not in broken]
    return SyncPlan(new, changed, unchanged, deleted, kept)


def run_ingest(
    folder: Path,
    store: Store,
    embedder: VoyageEmbedder,
    *,
    dry_run: bool = False,
    force: bool = False,
    allow_empty: bool = False,
) -> IngestResult:
    """Bring the database in line with the folder. Embeds everything before writing anything."""
    loaded = load_postings(folder)
    postings = {posting.source_id: posting for posting in loaded.postings}
    hashes = {source_id: file_hash(folder / f"{source_id}.txt") for source_id in postings}
    broken = {Path(name).stem for name in loaded.skipped}
    ingested = store.ingested()
    settings = current_settings()
    plan = plan_sync(hashes, broken, ingested, settings, force=force)

    if ingested and not postings and not plan.kept and not allow_empty:
        raise IngestError(
            f"the folder has no valid postings, so this would remove all {len(ingested)} "
            "postings from the database. rerun with --yes if that's really what you want"
        )
    if dry_run:
        return IngestResult(plan, 0, 0)

    to_embed = [postings[source_id] for source_id in plan.new + plan.changed]
    chunked = [(posting, chunk_posting(posting)) for posting in to_embed]
    texts = [chunk.text for _, chunks in chunked for chunk in chunks]
    # one batched Voyage call up front, so an API failure leaves the database untouched
    embeddings = embedder.embed_documents(texts)

    vectors = iter(embeddings.vectors)
    for posting, chunks in chunked:
        posting_vectors = [next(vectors) for _ in chunks]
        store.save_posting(posting, hashes[posting.source_id], settings, chunks, posting_vectors)
        logger.info("saved %s, %d chunk(s)", posting.source_id, len(chunks))
    for source_id in plan.deleted:
        store.delete_posting(source_id)
        logger.info("removed %s", source_id)
    for source_id in plan.kept:
        logger.warning("%s has errors, keeping the version already in the database", source_id)

    estimated = round(sum(len(text.split()) for text in texts) * config.TOKENS_PER_WORD)
    return IngestResult(plan, embeddings.tokens, estimated)


def print_summary(result: IngestResult, total: int, dry_run: bool) -> None:
    plan = result.plan
    print("dry run, nothing written" if dry_run else "done")
    for label, source_ids in [
        ("new", plan.new),
        ("changed", plan.changed),
        ("removed", plan.deleted),
        ("kept despite errors", plan.kept),
    ]:
        if source_ids:
            print(f"  {label}: {', '.join(source_ids)}")
    print(f"  unchanged: {len(plan.unchanged)}")
    if result.tokens_counted:
        print(
            f"  voyage counted {result.tokens_counted} tokens "
            f"(estimate was {result.tokens_estimated})"
        )
    print(f"  {total} postings in the database")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Sync a postings folder into its database.")
    parser.add_argument("corpus", choices=sorted(config.CORPORA), help="private or public")
    parser.add_argument("--dry-run", action="store_true", help="show the plan, write nothing")
    parser.add_argument(
        "--all", action="store_true", help="re-embed everything, e.g. after code edits"
    )
    parser.add_argument("--yes", action="store_true", help="allow removing every posting")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # it logs every request at INFO

    folder, url_name = config.CORPORA[args.corpus]
    try:
        embedder = VoyageEmbedder(config.require_env("VOYAGE_API_KEY"))
        store = Store.connect(config.require_env(url_name))
    except (config.MissingEnvError, psycopg.OperationalError) as error:
        # bad password, paused free-tier project, missing .env line: one line beats a traceback
        raise SystemExit(f"stopped: {error}") from None

    try:
        result = run_ingest(
            folder,
            store,
            embedder,
            dry_run=args.dry_run,
            force=args.all,
            allow_empty=args.yes,
        )
        total = store.count_postings()
    except IngestError as error:
        raise SystemExit(f"stopped: {error}") from None
    finally:
        store.close()
    print_summary(result, total, args.dry_run)


if __name__ == "__main__":
    main()
