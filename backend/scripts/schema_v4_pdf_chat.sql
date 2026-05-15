-- =============================================================================
-- Schema v4 — PDF Chat Sessions (temporary, research-purpose)
-- Run AFTER schema.sql, schema_v2_routine_teacher.sql, schema_v3_community_notices.sql
-- =============================================================================

-- ---------------------------------------------------------------------------
-- PDF SESSIONS — one row per uploaded PDF, expires after 7 days
-- ---------------------------------------------------------------------------

create table if not exists public.pdf_sessions (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references public.profiles(id) on delete cascade,
    filename    text not null,
    file_size   bigint,
    page_count  int  default 0,
    chunk_count int  default 0,
    summary     text,                              -- cached summary (null until generated)
    status      text default 'processing'
                check (status in ('processing', 'ready', 'failed')),
    expires_at  timestamptz default (now() + interval '7 days'),
    created_at  timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- PDF SESSION CHUNKS — hybrid-chunked + embedded content from each PDF
-- ---------------------------------------------------------------------------

create table if not exists public.pdf_session_chunks (
    id          uuid primary key default gen_random_uuid(),
    session_id  uuid not null references public.pdf_sessions(id) on delete cascade,
    content     text not null,
    chunk_index int  not null,
    page_number int  default 0,
    embedding   vector(384),
    created_at  timestamptz default now()
);

-- pgvector HNSW index for fast similarity search per session
create index if not exists pdf_session_chunks_embedding_idx
    on public.pdf_session_chunks
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 50);

-- Fast lookup: all chunks for a given session (ordered by chunk_index)
create index if not exists pdf_session_chunks_session_idx
    on public.pdf_session_chunks (session_id, chunk_index);

-- Auto-expire index: helps a cleanup cron query pdf_sessions by expires_at
create index if not exists pdf_sessions_expires_idx
    on public.pdf_sessions (expires_at)
    where status = 'ready';

-- ---------------------------------------------------------------------------
-- ROW LEVEL SECURITY
-- ---------------------------------------------------------------------------

alter table public.pdf_sessions       enable row level security;
alter table public.pdf_session_chunks enable row level security;

-- Users can only see and manage their own sessions
create policy "pdf_sessions: own"
    on public.pdf_sessions for all
    using (auth.uid() = user_id);

-- Chunks are accessible only through their parent session owner
create policy "pdf_chunks: own via session"
    on public.pdf_session_chunks for all
    using (
        exists (
            select 1 from public.pdf_sessions s
            where s.id = session_id
              and s.user_id = auth.uid()
        )
    );

-- ---------------------------------------------------------------------------
-- PGVECTOR SIMILARITY SEARCH FUNCTION
-- ---------------------------------------------------------------------------

-- Match chunks for a specific PDF session (user-scoped search, not global)
create or replace function match_pdf_session_chunks(
    p_session_id    uuid,
    query_embedding vector(384),
    match_count     int   default 6,
    match_threshold float default 0.3
)
returns table (
    id          uuid,
    content     text,
    chunk_index int,
    page_number int,
    similarity  float
)
language sql stable
as $$
    select
        c.id,
        c.content,
        c.chunk_index,
        c.page_number,
        1 - (c.embedding <=> query_embedding) as similarity
    from public.pdf_session_chunks c
    where c.session_id = p_session_id
      and 1 - (c.embedding <=> query_embedding) > match_threshold
    order by c.embedding <=> query_embedding
    limit match_count;
$$;
