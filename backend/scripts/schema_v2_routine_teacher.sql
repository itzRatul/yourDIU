-- =============================================================================
-- yourDIU — Schema v2: Routine & Teacher System
-- =============================================================================
-- Run AFTER schema.sql in Supabase Dashboard → SQL Editor
-- =============================================================================


-- ---------------------------------------------------------------------------
-- ROUTINES  (uploaded PDF metadata)
-- ---------------------------------------------------------------------------
create table if not exists public.routines (
    id              uuid        default gen_random_uuid() primary key,
    title           text        not null,               -- "CSE Class Routine V2.1 Summer-2026"
    department      text        not null default 'CSE',
    version         text,                               -- "V2.1"
    semester        text,                               -- "Summer-2026"
    effective_from  date,
    file_url        text,                               -- Supabase Storage URL (original PDF)
    is_active       boolean     default true,           -- only one active per dept at a time
    uploaded_by     uuid        references public.profiles(id) on delete set null,
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create trigger routines_updated_at
    before update on public.routines
    for each row execute procedure public.set_updated_at();

create index if not exists routines_dept_active_idx on public.routines(department, is_active);


-- ---------------------------------------------------------------------------
-- ROUTINE SLOTS  (each parsed class entry from the PDF)
-- ---------------------------------------------------------------------------
create table if not exists public.routine_slots (
    id               uuid    default gen_random_uuid() primary key,
    routine_id       uuid    references public.routines(id) on delete cascade not null,
    day              text    not null
                             check (day in ('Saturday','Sunday','Monday','Tuesday','Wednesday','Thursday')),
    time_start       time    not null,                  -- 08:30
    time_end         time    not null,                  -- 10:00
    room             text    not null,                  -- "KT-201", "G1-001 (COM LAB)"
    course_code      text    not null,                  -- "CSE315"
    batch            text,                              -- "66" (kept as text for "RE" cases)
    section          text,                              -- "E"
    teacher_initials text,                              -- "MAK"
    raw_course_text  text,                              -- "CSE315(66_E)" original
    created_at       timestamptz default now()
);

create index if not exists routine_slots_routine_id_idx      on public.routine_slots(routine_id);
create index if not exists routine_slots_teacher_initials_idx on public.routine_slots(teacher_initials);
create index if not exists routine_slots_day_time_idx        on public.routine_slots(day, time_start);
create index if not exists routine_slots_room_idx            on public.routine_slots(room);


-- ---------------------------------------------------------------------------
-- TEACHER INFO  (extended profile — admin or teacher can update)
-- ---------------------------------------------------------------------------
create table if not exists public.teacher_info (
    id               uuid    references public.profiles(id) on delete cascade primary key,
    employee_id      text    unique,
    initials         text    unique,                    -- "MAK" — links to routine_slots
    designation      text,                              -- "Associate Professor", "Lecturer"
    department       text,
    room_number      text,                              -- office room e.g. "KT-301"
    office_building  text,                              -- "KT Building", "AB5"
    office_hours     jsonb   default '[]',
    -- format: [{"day":"Sunday","start":"10:00","end":"12:00"},...]
    phone            text,
    personal_website text,
    created_at       timestamptz default now(),
    updated_at       timestamptz default now()
);

create trigger teacher_info_updated_at
    before update on public.teacher_info
    for each row execute procedure public.set_updated_at();

create index if not exists teacher_info_initials_idx on public.teacher_info(initials);


-- ---------------------------------------------------------------------------
-- TEACHER AVAILABILITY OVERRIDES
-- ---------------------------------------------------------------------------
-- Teachers can mark exceptions to their routine schedule:
--   'unavailable' → has class in routine but won't be there (students notified)
--   'busy'        → no class but not free either (don't come to room)
-- ---------------------------------------------------------------------------
create table if not exists public.teacher_availability (
    id           uuid    default gen_random_uuid() primary key,
    teacher_id   uuid    references public.profiles(id) on delete cascade not null,
    date         date    not null,
    time_start   time    not null,
    time_end     time    not null,
    status       text    not null
                         check (status in ('unavailable', 'busy')),
    reason       text,                                  -- internal: "Conference", "Sick leave"
    public_note  text,                                  -- shown to students: "Not available"
    created_by   text    not null default 'teacher'
                         check (created_by in ('teacher', 'admin')),
    created_at   timestamptz default now(),
    updated_at   timestamptz default now(),

    -- no two overlapping entries for the same teacher+date
    unique (teacher_id, date, time_start, time_end)
);

create trigger teacher_availability_updated_at
    before update on public.teacher_availability
    for each row execute procedure public.set_updated_at();

create index if not exists teacher_avail_teacher_date_idx on public.teacher_availability(teacher_id, date);
create index if not exists teacher_avail_date_idx         on public.teacher_availability(date);


-- =============================================================================
-- RLS POLICIES
-- =============================================================================

alter table public.routines              enable row level security;
alter table public.routine_slots         enable row level security;
alter table public.teacher_info          enable row level security;
alter table public.teacher_availability  enable row level security;

-- ── ROUTINES ──────────────────────────────────────────────────────────────
create policy "routines: read all"
    on public.routines for select using (true);

create policy "routines: write admin only"
    on public.routines for all
    using (auth.uid() in (select id from public.profiles where role = 'admin'));

-- ── ROUTINE SLOTS ─────────────────────────────────────────────────────────
create policy "routine_slots: read all"
    on public.routine_slots for select using (true);

create policy "routine_slots: write admin only"
    on public.routine_slots for all
    using (auth.uid() in (select id from public.profiles where role = 'admin'));

-- ── TEACHER INFO ──────────────────────────────────────────────────────────
create policy "teacher_info: read all auth"
    on public.teacher_info for select using (auth.role() = 'authenticated');

create policy "teacher_info: update own"
    on public.teacher_info for update
    using (auth.uid() = id);

create policy "teacher_info: admin full"
    on public.teacher_info for all
    using (auth.uid() in (select id from public.profiles where role = 'admin'));

-- ── TEACHER AVAILABILITY ──────────────────────────────────────────────────
create policy "teacher_avail: read all auth"
    on public.teacher_availability for select using (auth.role() = 'authenticated');

create policy "teacher_avail: manage own"
    on public.teacher_availability for all
    using (auth.uid() = teacher_id);

create policy "teacher_avail: admin full"
    on public.teacher_availability for all
    using (auth.uid() in (select id from public.profiles where role = 'admin'));


-- =============================================================================
-- REALTIME
-- =============================================================================
alter publication supabase_realtime add table public.routines;
alter publication supabase_realtime add table public.teacher_availability;


-- =============================================================================
-- HELPER: deactivate old routines when a new one is uploaded for same dept
-- =============================================================================
create or replace function public.deactivate_old_routines()
returns trigger
language plpgsql
security definer
as $$
begin
    update public.routines
    set is_active = false
    where department = new.department
      and id != new.id
      and is_active = true;
    return new;
end;
$$;

create trigger on_routine_inserted
    after insert on public.routines
    for each row execute procedure public.deactivate_old_routines();
