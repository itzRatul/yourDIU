-- =============================================================================
-- Schema v3 — Community, Notices & Notifications alignment
-- Run AFTER schema.sql and schema_v2_routine_teacher.sql
-- =============================================================================

-- ---------------------------------------------------------------------------
-- COMMUNITY POSTS — add missing columns
-- ---------------------------------------------------------------------------

-- Make title optional (community is Twitter-style, content-only is fine)
alter table public.community_posts
    alter column title drop not null,
    alter column title set default null;

-- Teacher-post badge (shown as ⭐ in frontend)
alter table public.community_posts
    add column if not exists is_teacher_post boolean default false;

-- Optional image attachment
alter table public.community_posts
    add column if not exists image_url text;

-- Expand category constraint
alter table public.community_posts
    drop constraint if exists community_posts_category_check;

alter table public.community_posts
    add constraint community_posts_category_check
    check (category in ('general', 'academic', 'event', 'question', 'resource', 'announcement'));

-- ---------------------------------------------------------------------------
-- POST REACTIONS — rename reaction_type → reaction, expand allowed values
-- ---------------------------------------------------------------------------

-- Add new column with broader options
alter table public.post_reactions
    add column if not exists reaction text;

-- Copy existing data
update public.post_reactions
    set reaction = reaction_type
    where reaction is null;

-- Set not null
alter table public.post_reactions
    alter column reaction set not null;

-- Drop old column
alter table public.post_reactions
    drop column if exists reaction_type;

-- Update unique constraint (one reaction per user per post, any type)
alter table public.post_reactions
    drop constraint if exists post_reactions_post_id_user_id_key;

alter table public.post_reactions
    add constraint post_reactions_post_id_user_id_key unique (post_id, user_id);

-- Reaction value check
alter table public.post_reactions
    add constraint post_reactions_reaction_check
    check (reaction in ('like', 'love', 'haha', 'wow', 'sad', 'angry', 'insightful'));

-- ---------------------------------------------------------------------------
-- POST COMMENTS — add teacher comment flag for pinning
-- ---------------------------------------------------------------------------

alter table public.post_comments
    add column if not exists is_teacher_comment boolean default false;

-- ---------------------------------------------------------------------------
-- NOTICES — full schema alignment
-- ---------------------------------------------------------------------------

-- Add created_by (consistent naming; author_id stays for backwards compat)
alter table public.notices
    add column if not exists created_by uuid references public.profiles(id) on delete set null;

-- Copy author_id → created_by for existing rows
update public.notices set created_by = author_id where created_by is null;

-- New columns needed by the API
alter table public.notices
    add column if not exists department     text;

alter table public.notices
    add column if not exists attachment_url text;

alter table public.notices
    add column if not exists is_pinned      boolean default false;

alter table public.notices
    add column if not exists is_active      boolean default true;

alter table public.notices
    add column if not exists expires_at     timestamptz;

-- Sync is_active from is_published for existing rows
update public.notices set is_active = is_published where is_active is null or is_active = true;

-- Expand category constraint to include 'admission' and 'department'
alter table public.notices
    drop constraint if exists notices_category_check;

alter table public.notices
    add constraint notices_category_check
    check (category in ('general', 'academic', 'exam', 'event', 'urgent', 'admission', 'department'));

-- ---------------------------------------------------------------------------
-- NOTIFICATIONS — allow broadcasts + add is_read + ref columns
-- ---------------------------------------------------------------------------

-- Allow NULL user_id for broadcast notifications
alter table public.notifications
    alter column user_id drop not null;

-- Add is_read (simpler than read_at for polling count queries)
alter table public.notifications
    add column if not exists is_read boolean default false;

-- Sync is_read from read_at for existing rows
update public.notifications
    set is_read = (read_at is not null)
    where is_read is null or is_read = false;

-- ref_id + ref_type: pointer to the thing that triggered the notification
alter table public.notifications
    add column if not exists ref_id   uuid;

alter table public.notifications
    add column if not exists ref_type text;

-- Expand type constraint
alter table public.notifications
    drop constraint if exists notifications_type_check;

-- (no check added — type is free-form text for flexibility)

-- Add index on is_read for fast badge queries
create index if not exists notifications_is_read_idx
    on public.notifications(user_id, is_read)
    where is_read = false;

-- Broadcast notifications (user_id IS NULL) index
create index if not exists notifications_broadcast_idx
    on public.notifications(is_read)
    where user_id is null;

-- ---------------------------------------------------------------------------
-- RLS updates
-- ---------------------------------------------------------------------------

-- community_posts: allow guests to read posts (for public community feed)
drop policy if exists "community_posts: read all auth" on public.community_posts;
create policy "community_posts: read all"
    on public.community_posts for select using (true);

-- notices: already open (true) — nothing to change

-- notifications: allow broadcast rows (user_id IS NULL) to be readable
drop policy if exists "notifications: own" on public.notifications;
create policy "notifications: own or broadcast"
    on public.notifications for select
    using (auth.uid() = user_id or user_id is null);

create policy "notifications: insert service"
    on public.notifications for insert
    with check (true);  -- service role handles inserts

create policy "notifications: update own"
    on public.notifications for update
    using (auth.uid() = user_id or user_id is null);

create policy "notifications: delete own"
    on public.notifications for delete
    using (auth.uid() = user_id or user_id is null);
