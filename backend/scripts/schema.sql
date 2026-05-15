-- =============================================================================
-- yourDIU — Supabase Schema
-- =============================================================================
-- Run this in: Supabase Dashboard → SQL Editor → New Query → Run
-- Order matters — run top to bottom.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- EXTENSIONS
-- ---------------------------------------------------------------------------
create extension if not exists vector;            -- pgvector for embeddings
create extension if not exists "uuid-ossp";       -- gen_random_uuid fallback


-- ---------------------------------------------------------------------------
-- PROFILES  (extends auth.users)
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
    id              uuid        references auth.users(id) on delete cascade primary key,
    email           text        unique not null,
    full_name       text,
    avatar_url      text,
    role            text        not null default 'student'
                                check (role in ('student', 'teacher', 'admin')),
    student_id      text,
    department      text,
    batch           text,
    is_verified     boolean     default false,
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

-- Auto-create profile on new signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.profiles (id, email, full_name, avatar_url)
    values (
        new.id,
        new.email,
        new.raw_user_meta_data->>'full_name',
        new.raw_user_meta_data->>'avatar_url'
    )
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();

-- Auto-update updated_at on profiles
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger profiles_updated_at
    before update on public.profiles
    for each row execute procedure public.set_updated_at();


-- ---------------------------------------------------------------------------
-- CHAT SESSIONS
-- ---------------------------------------------------------------------------
create table if not exists public.chat_sessions (
    id          uuid        default gen_random_uuid() primary key,
    user_id     uuid        references public.profiles(id) on delete cascade not null,
    title       text        default 'New Chat',
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);

create trigger chat_sessions_updated_at
    before update on public.chat_sessions
    for each row execute procedure public.set_updated_at();

create index if not exists chat_sessions_user_id_idx on public.chat_sessions(user_id);


-- ---------------------------------------------------------------------------
-- CHAT MESSAGES
-- ---------------------------------------------------------------------------
create table if not exists public.chat_messages (
    id          uuid        default gen_random_uuid() primary key,
    session_id  uuid        references public.chat_sessions(id) on delete cascade not null,
    role        text        not null check (role in ('user', 'assistant')),
    content     text        not null,
    created_at  timestamptz default now()
);

create index if not exists chat_messages_session_id_idx on public.chat_messages(session_id);


-- ---------------------------------------------------------------------------
-- COMMUNITY POSTS
-- ---------------------------------------------------------------------------
create table if not exists public.community_posts (
    id              uuid        default gen_random_uuid() primary key,
    user_id         uuid        references public.profiles(id) on delete cascade not null,
    title           text        not null,
    content         text        not null,
    category        text        default 'general'
                                check (category in ('general', 'academic', 'event', 'question', 'announcement')),
    is_pinned       boolean     default false,   -- admin/teacher can pin
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create trigger community_posts_updated_at
    before update on public.community_posts
    for each row execute procedure public.set_updated_at();

create index if not exists community_posts_user_id_idx    on public.community_posts(user_id);
create index if not exists community_posts_created_at_idx on public.community_posts(created_at desc);


-- ---------------------------------------------------------------------------
-- POST REACTIONS
-- ---------------------------------------------------------------------------
create table if not exists public.post_reactions (
    id              uuid        default gen_random_uuid() primary key,
    post_id         uuid        references public.community_posts(id) on delete cascade not null,
    user_id         uuid        references public.profiles(id) on delete cascade not null,
    reaction_type   text        not null check (reaction_type in ('like', 'love', 'insightful')),
    created_at      timestamptz default now(),
    unique (post_id, user_id)   -- one reaction per user per post
);

create index if not exists post_reactions_post_id_idx on public.post_reactions(post_id);


-- ---------------------------------------------------------------------------
-- POST COMMENTS  (supports threaded replies via parent_id)
-- ---------------------------------------------------------------------------
create table if not exists public.post_comments (
    id          uuid        default gen_random_uuid() primary key,
    post_id     uuid        references public.community_posts(id) on delete cascade not null,
    user_id     uuid        references public.profiles(id) on delete cascade not null,
    content     text        not null,
    parent_id   uuid        references public.post_comments(id) on delete cascade,  -- null = top-level
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);

create trigger post_comments_updated_at
    before update on public.post_comments
    for each row execute procedure public.set_updated_at();

create index if not exists post_comments_post_id_idx   on public.post_comments(post_id);
create index if not exists post_comments_parent_id_idx on public.post_comments(parent_id);


-- ---------------------------------------------------------------------------
-- NOTICES
-- ---------------------------------------------------------------------------
create table if not exists public.notices (
    id          uuid        default gen_random_uuid() primary key,
    title       text        not null,
    content     text        not null,
    author_id   uuid        references public.profiles(id) on delete set null,
    category    text        default 'general'
                            check (category in ('general', 'academic', 'exam', 'event', 'urgent')),
    priority    integer     default 0,           -- higher = shown first
    is_published boolean    default true,
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);

create trigger notices_updated_at
    before update on public.notices
    for each row execute procedure public.set_updated_at();

create index if not exists notices_created_at_idx on public.notices(created_at desc);
create index if not exists notices_priority_idx   on public.notices(priority desc);


-- ---------------------------------------------------------------------------
-- NOTIFICATIONS
-- ---------------------------------------------------------------------------
create table if not exists public.notifications (
    id          uuid        default gen_random_uuid() primary key,
    user_id     uuid        references public.profiles(id) on delete cascade not null,
    type        text        not null,            -- 'notice', 'comment', 'reaction', 'announcement'
    title       text        not null,
    body        text,
    payload     jsonb       default '{}',        -- extra data (post_id, notice_id, etc.)
    read_at     timestamptz,                     -- null = unread
    created_at  timestamptz default now()
);

create index if not exists notifications_user_id_idx   on public.notifications(user_id);
create index if not exists notifications_read_at_idx   on public.notifications(read_at) where read_at is null;


-- ---------------------------------------------------------------------------
-- DIU KNOWLEDGE BASE  (RAG source documents)
-- ---------------------------------------------------------------------------
create table if not exists public.diu_knowledge (
    id          uuid        default gen_random_uuid() primary key,
    title       text        not null,
    content     text        not null,
    source_url  text,
    doc_type    text        default 'general'
                            check (doc_type in ('general', 'academic', 'faculty', 'event', 'notice', 'course', 'department')),
    metadata    jsonb       default '{}',        -- department, semester, tags, etc.
    scraped_at  timestamptz default now(),
    created_at  timestamptz default now()
);

create index if not exists diu_knowledge_doc_type_idx on public.diu_knowledge(doc_type);


-- ---------------------------------------------------------------------------
-- DOCUMENT CHUNKS  (pgvector embeddings)
-- ---------------------------------------------------------------------------
create table if not exists public.document_chunks (
    id          uuid        default gen_random_uuid() primary key,
    doc_id      uuid        references public.diu_knowledge(id) on delete cascade not null,
    chunk_text  text        not null,
    chunk_index integer     not null,
    embedding   vector(384),                     -- sentence-transformers/all-MiniLM-L6-v2 = 384 dim
    metadata    jsonb       default '{}',
    created_at  timestamptz default now()
);

-- IVFFlat index for fast approximate nearest-neighbor search
-- Run AFTER inserting data (needs rows to train on)
-- create index on public.document_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

create index if not exists document_chunks_doc_id_idx on public.document_chunks(doc_id);


-- ---------------------------------------------------------------------------
-- SEARCH FUNCTION  (called from backend for RAG retrieval)
-- ---------------------------------------------------------------------------
create or replace function public.match_document_chunks(
    query_embedding vector(384),
    match_threshold float   default 0.5,
    match_count     int     default 8,
    filter_doc_type text    default null
)
returns table (
    id          uuid,
    doc_id      uuid,
    chunk_text  text,
    metadata    jsonb,
    similarity  float
)
language sql stable
as $$
    select
        dc.id,
        dc.doc_id,
        dc.chunk_text,
        dc.metadata,
        1 - (dc.embedding <=> query_embedding) as similarity
    from public.document_chunks dc
    join public.diu_knowledge dk on dk.id = dc.doc_id
    where
        dc.embedding is not null
        and (filter_doc_type is null or dk.doc_type = filter_doc_type)
        and 1 - (dc.embedding <=> query_embedding) > match_threshold
    order by dc.embedding <=> query_embedding
    limit match_count;
$$;


-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- =============================================================================

alter table public.profiles          enable row level security;
alter table public.chat_sessions     enable row level security;
alter table public.chat_messages     enable row level security;
alter table public.community_posts   enable row level security;
alter table public.post_reactions    enable row level security;
alter table public.post_comments     enable row level security;
alter table public.notices           enable row level security;
alter table public.notifications     enable row level security;
alter table public.diu_knowledge     enable row level security;
alter table public.document_chunks   enable row level security;

-- ── PROFILES ────────────────────────────────────────────────────────────────
create policy "profiles: read own"    on public.profiles for select using (auth.uid() = id);
create policy "profiles: update own"  on public.profiles for update using (auth.uid() = id);

-- ── CHAT SESSIONS ────────────────────────────────────────────────────────────
create policy "chat_sessions: own"    on public.chat_sessions for all  using (auth.uid() = user_id);

-- ── CHAT MESSAGES ────────────────────────────────────────────────────────────
create policy "chat_messages: own"    on public.chat_messages for all
    using (session_id in (select id from public.chat_sessions where user_id = auth.uid()));

-- ── COMMUNITY POSTS ──────────────────────────────────────────────────────────
create policy "community_posts: read all auth"  on public.community_posts for select using (auth.role() = 'authenticated');
create policy "community_posts: insert own"     on public.community_posts for insert with check (auth.uid() = user_id);
create policy "community_posts: update own"     on public.community_posts for update using (auth.uid() = user_id);
create policy "community_posts: delete own"     on public.community_posts for delete using (auth.uid() = user_id);

-- ── REACTIONS ────────────────────────────────────────────────────────────────
create policy "post_reactions: read all auth"   on public.post_reactions for select using (auth.role() = 'authenticated');
create policy "post_reactions: manage own"      on public.post_reactions for all   using (auth.uid() = user_id);

-- ── COMMENTS ─────────────────────────────────────────────────────────────────
create policy "post_comments: read all auth"    on public.post_comments for select using (auth.role() = 'authenticated');
create policy "post_comments: insert own"       on public.post_comments for insert with check (auth.uid() = user_id);
create policy "post_comments: update own"       on public.post_comments for update using (auth.uid() = user_id);
create policy "post_comments: delete own"       on public.post_comments for delete using (auth.uid() = user_id);

-- ── NOTICES ──────────────────────────────────────────────────────────────────
create policy "notices: read all"               on public.notices for select using (true);
create policy "notices: write admin teacher"    on public.notices for all
    using (auth.uid() in (select id from public.profiles where role in ('admin', 'teacher')));

-- ── NOTIFICATIONS ────────────────────────────────────────────────────────────
create policy "notifications: own"              on public.notifications for all  using (auth.uid() = user_id);

-- ── KNOWLEDGE BASE ───────────────────────────────────────────────────────────
create policy "diu_knowledge: read all"         on public.diu_knowledge     for select using (true);
create policy "document_chunks: read all"       on public.document_chunks   for select using (true);
-- insert/update only from service role (backend) — no user policy needed


-- =============================================================================
-- REALTIME  (Supabase Realtime subscriptions)
-- =============================================================================
alter publication supabase_realtime add table public.notifications;
alter publication supabase_realtime add table public.notices;
alter publication supabase_realtime add table public.community_posts;
