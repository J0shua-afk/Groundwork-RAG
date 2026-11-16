-- Run once per Supabase project, in the dashboard's SQL editor.

create extension if not exists vector with schema extensions;

create table if not exists postings (
    source_id   text primary key,
    company     text not null,
    title       text not null,
    location    text not null,
    work_model  text not null check (work_model in ('on-site', 'hybrid', 'remote', 'not stated')),
    term        text not null,
    url         text,
    file_hash   text not null,  -- sha256 of the .txt, how ingest notices edits
    settings    text not null,  -- chunk + embedding settings used; if they change, re-embed
    ingested_at timestamptz not null default now()
);

create table if not exists chunks (
    source_id   text not null references postings (source_id) on delete cascade,
    chunk_index integer not null,
    text        text not null,
    embedding   extensions.vector(1024) not null,  -- voyage-4-lite, see EMBEDDING_DIMENSIONS
    primary key (source_id, chunk_index)
);

-- no vector index on purpose: a few hundred chunks scan exactly in a few ms, and hnsw would
-- trade that for approximate results. worth adding once there are thousands of chunks

-- RLS with no policies shuts off Supabase's auto-generated REST API for these tables.
-- we connect as the table owner, which RLS doesn't apply to
alter table postings enable row level security;
alter table chunks enable row level security;
