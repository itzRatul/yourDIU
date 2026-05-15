# yourDIU — Virtual Assistant for Daffodil International University

> An AI-powered assistant for DIU students and teachers — class routines, teacher availability, university notices, community discussions, and intelligent chat. Built with FastAPI + Next.js + Supabase + LLaMA 3.3 70B.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Supabase Setup](#supabase-setup)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [AI System](#ai-system)
- [Routine System](#routine-system)
- [Database Schema](#database-schema)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## Overview

**yourDIU** is a full-stack virtual assistant built specifically for [Daffodil International University (DIU)](https://daffodilvarsity.edu.bd), Bangladesh. It serves three types of users:

| User Type | Access |
|-----------|--------|
| **Guest** | Basic info only — no login required, no history saved |
| **Student / Teacher** | Full access — login with `@diu.edu.bd` Google account, chat history, community |
| **Admin** | All of the above + upload routines, post notices, manage users |

Login is restricted to `@diu.edu.bd` email addresses — enforced on both the frontend (UI warning) and backend (hard 403 block).

---

## Features

### AI Chat
- Streaming responses via Server-Sent Events (SSE) — text appears word by word
- Smart query routing: routine queries → DB, DIU info → RAG, fresh info → web search
- Bangla and English both supported
- Chat history saved per session (logged-in users only)
- Guest users can chat without logging in — no history saved

### Class Routine
- Admin uploads PDF routine → system parses it automatically using `pdfplumber`
- Gemini Vision fallback for complex or scanned PDF pages
- Query slots by teacher initials, day, room, batch, section
- Teacher self-update: mark yourself unavailable/busy for specific time slots

### Teacher Availability
- Real-time availability check combining base schedule + manual overrides
- Status types: `available`, `in_class`, `unavailable` (canceled), `busy` (not in office)
- Students can ask "Is Sir MAK free tomorrow at 10am?" and get an accurate answer

### Community
- Post feed with category filtering (general, question, resource, event)
- Six reaction types: like, love, haha, wow, sad, angry
- Threaded comments (nested replies)
- Teacher posts get a ⭐ star badge
- Teacher/admin comments are automatically pinned to the top

### Notices
- Admin posts notices with categories, department filter, pin/unpin
- Soft delete (notices are never permanently removed from DB)
- Auto-broadcasts a notification to all users when a new notice is posted

### Notifications
- Personal + broadcast (null user_id) notification system
- Unread badge count endpoint for frontend polling
- Mark one or all as read
- Supabase Realtime enabled — frontend gets push updates without polling

### RAG Knowledge Base
- DIU website scraped with BeautifulSoup (22+ seed URLs)
- Hybrid chunking: semantic cosine-similarity split → recursive character split
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, L2-normalized)
- Vector search via pgvector's `match_document_chunks()` RPC function
- Better than fixed-size chunking (preserves semantic boundaries)

---

## Tech Stack

### Backend
| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.111+ |
| Language | Python 3.11+ |
| Settings | Pydantic v2 + python-dotenv |
| Auth | Supabase Auth (JWT) + Google OAuth |
| Database | Supabase PostgreSQL + pgvector |
| Storage | Supabase Storage (routine PDFs) |
| Realtime | Supabase Realtime |
| AI — LLM | Groq (LLaMA 3.3 70B) + Google Gemini 2.0 Flash |
| AI — Embeddings | sentence-transformers/all-MiniLM-L6-v2 (local) |
| Web Search | Tavily (primary, 900/day limit) → Brave Search (fallback) |
| PDF Parsing | pdfplumber + Gemini Vision fallback |
| Scraping | httpx + BeautifulSoup4 + Playwright |
| Chunking | langchain-text-splitters + custom semantic pass |

### Frontend *(in progress)*
| Layer | Technology |
|-------|-----------|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS |
| UI Theme | diutoolkit.xyz color palette + Dark mode |
| Auth | Supabase Auth (Google OAuth) |
| State | React Context / Zustand |
| Streaming | EventSource (SSE) for chat |

### Infrastructure
| Service | Use |
|---------|-----|
| Supabase | PostgreSQL + pgvector + Auth + Storage + Realtime |
| GitHub | Version control (frequent meaningful commits) |
| Vercel | Frontend deployment |
| HuggingFace Spaces | Backend deployment (testing) |
| Hostinger | Final production deployment |

---

## Project Structure

```
yourDIU/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py            # /auth — login, profile, domain verify
│   │   │       ├── chat.py            # /chat — streaming AI chat + sessions
│   │   │       ├── community.py       # /community — posts, reactions, comments
│   │   │       ├── notices.py         # /notices — notice board
│   │   │       ├── notifications.py   # /notifications — push notifications
│   │   │       ├── routines.py        # /routines — PDF upload + slot queries
│   │   │       ├── teachers.py        # /teachers — teacher info + availability
│   │   │       └── router.py          # Main router (includes all sub-routers)
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic settings (all env vars)
│   │   │   ├── security.py            # JWT verification, role guards
│   │   │   └── supabase.py            # Supabase anon + admin client singletons
│   │   ├── models/
│   │   │   ├── user.py                # UserRole, ProfileCreate/Response
│   │   │   └── chat.py                # ChatMessage, Session, AIResponse
│   │   ├── services/
│   │   │   ├── ai/
│   │   │   │   ├── groq_service.py    # LLaMA 3.3 70B streaming, round-robin keys
│   │   │   │   ├── gemini_service.py  # Gemini fallback + Vision API
│   │   │   │   └── brain_service.py   # Query router (intent → context → LLM)
│   │   │   ├── rag/
│   │   │   │   ├── chunking.py        # Hybrid semantic + recursive chunker
│   │   │   │   ├── embeddings.py      # Sentence-transformers embedding service
│   │   │   │   └── retriever.py       # pgvector similarity search
│   │   │   ├── routine/
│   │   │   │   ├── parser.py          # PDF routine parser (pdfplumber + Gemini)
│   │   │   │   └── availability.py    # Teacher availability logic
│   │   │   ├── search/
│   │   │   │   ├── tavily_service.py  # Tavily web search + daily counter
│   │   │   │   ├── brave_service.py   # Brave Search fallback (plain httpx)
│   │   │   │   └── search_router.py   # Auto Tavily → Brave fallback
│   │   │   └── scraper/
│   │   │       └── diu_scraper.py     # DIU website scraper (22+ pages)
│   │   └── main.py                    # FastAPI app, CORS, lifespan
│   ├── scripts/
│   │   ├── schema.sql                 # Phase 1: base tables (profiles, chat, RAG)
│   │   ├── schema_v2_routine_teacher.sql  # Phase 2: routine + teacher tables
│   │   ├── schema_v3_community_notices.sql # Phase 3: community/notice alignment
│   │   └── scrape_and_index.py        # CLI: scrape DIU website → index to pgvector
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                          # Next.js app (in progress)
│   └── .env.example
│
└── data/                              # Scraped DIU data (gitignored)
    ├── raw/                           # Raw HTML pages
    └── processed/                     # Extracted text JSON
```

---

## Architecture

### AI Query Flow

```
User Message
     │
     ▼
Brain Service (intent detection)
     │
     ├── "routine / class / slot" ────────► routine_slots DB → inject context
     │
     ├── "teacher / sir / available" ──────► teacher_info + teacher_availability DB → inject context
     │
     ├── "DIU info / rules / academic" ────► pgvector semantic search → inject top-K chunks
     │
     ├── "news / notice / latest / 2026" ──► Tavily Search → Brave fallback → inject results
     │
     └── general question ─────────────────► No extra context
                                                    │
                                                    ▼
                                          Groq (LLaMA 3.3 70B)
                                          ↓ fails / rate-limit?
                                          Gemini 2.0 Flash fallback
                                                    │
                                                    ▼
                                           SSE Stream → Frontend
```

### Teacher Availability Logic

```
check_teacher_availability(initials, teacher_id, date, start, end)
     │
     ├── Step 1: Check routine_slots (base schedule)
     │           → class exists at this time? → status: "in_class"
     │
     ├── Step 2: Check teacher_availability (override exceptions)
     │           → override exists? → status: "unavailable" or "busy"
     │
     └── Step 3: Final answer
                 "available"    — free, likely in office
                 "in_class"     — teaching (course, batch, section, room shown)
                 "unavailable"  — has class but marked absent (class canceled)
                 "busy"         — no class but not in office
```

### Web Search Fallback

```
web_search(query)
     │
     ├── Tavily (primary) — daily counter < 900?
     │       ├── Success → return results, provider="tavily"
     │       └── TavilyLimitError / failure → fallback
     │
     └── Brave Search (fallback)
             ├── Success → return results, provider="brave"
             └── Failure → return [], provider="none"
```

### Auth Flow

```
Frontend (Google OAuth via Supabase Auth)
     │
     ▼
Supabase Auth issues JWT
     │
     ▼
Backend: get_current_user()
     ├── Verify JWT → supabase_admin.auth.get_user(token)
     ├── Check email domain → must be @diu.edu.bd → else 403
     └── Load profile from profiles table → return user object

require_role("admin") → extra check on profiles.role column
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project (free tier works)
- [Groq](https://console.groq.com) API key (free)
- [Google AI Studio](https://aistudio.google.com) API key (Gemini, free)
- [Tavily](https://app.tavily.com) API key (free, 1000 req/month)
- [Brave Search API](https://api.search.brave.com) key (fallback, free tier available)
- Google OAuth credentials (Google Cloud Console)

---

### Supabase Setup

1. Create a new Supabase project at [supabase.com](https://supabase.com).

2. Go to **SQL Editor** and run the schema files **in order**:

```sql
-- Step 1: Base schema (profiles, chat, RAG knowledge base)
-- Paste contents of: backend/scripts/schema.sql

-- Step 2: Routine + Teacher tables
-- Paste contents of: backend/scripts/schema_v2_routine_teacher.sql

-- Step 3: Community + Notices alignment
-- Paste contents of: backend/scripts/schema_v3_community_notices.sql
```

3. Enable **pgvector** extension:
   - Go to **Database → Extensions** → search `vector` → enable it.
   - (The schema.sql already runs `create extension if not exists vector` but enabling via UI is safer.)

4. Enable **Google OAuth** in Supabase:
   - Go to **Authentication → Providers → Google**
   - Add your Google Client ID and Secret
   - Set the redirect URL in your Google Cloud Console

5. Get your keys from **Project Settings → API**:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY` (for frontend)
   - `SUPABASE_SERVICE_ROLE_KEY` (for backend only — never expose to browser)

---

### Backend Setup

```bash
# 1. Clone the repo
git clone https://github.com/itzRatul/yourDIU.git
cd yourDIU/backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
# Note: torch is installed CPU-only (no GPU needed)
pip install -r requirements.txt

# 4. Install Playwright browsers (for scraping, optional)
playwright install chromium

# 5. Copy and fill environment variables
cp .env.example .env
# Edit .env with your keys

# 6. Run the server
uvicorn app.main:app --reload --port 8000
```

**Swagger UI (no frontend needed):**
Open [http://localhost:8000/docs](http://localhost:8000/docs) — all endpoints are testable here.

**Optional: Scrape and index DIU website**
```bash
# Scrape DIU website and index to pgvector
python scripts/scrape_and_index.py

# Skip scraping, use cached data from data/processed/
python scripts/scrape_and_index.py --local

# Dry run — don't write to DB
python scripts/scrape_and_index.py --dry-run
```

---

### Frontend Setup

```bash
cd yourDIU/frontend

# Install dependencies
npm install

# Copy and fill environment variables
cp .env.example .env.local
# Edit .env.local with your keys

# Run dev server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**Frontend-only testing (no backend needed):**
```bash
# Set in .env.local:
NEXT_PUBLIC_USE_MOCK=true
```
This enables mock API responses so you can develop the UI without a running backend.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_ENV` | ✓ | `development` or `production` |
| `APP_PORT` | ✓ | Server port (default: `8000`) |
| `APP_SECRET_KEY` | ✓ | Random secret key |
| `SUPABASE_URL` | ✓ | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | ✓ | Supabase public anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | ✓ | Supabase service role key (backend only!) |
| `DATABASE_URL` | ✓ | PostgreSQL connection URI |
| `GOOGLE_CLIENT_ID` | ✓ | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | ✓ | Google OAuth client secret |
| `GROQ_API_KEY` | ✓ | Groq primary API key |
| `GROQ_API_KEY_2` | — | Second Groq key (round-robin rotation) |
| `GROQ_API_KEY_3` | — | Third Groq key (round-robin rotation) |
| `GROQ_MODEL` | ✓ | Model name (default: `llama-3.3-70b-versatile`) |
| `GEMINI_API_KEY` | ✓ | Google Gemini API key |
| `GEMINI_MODEL` | ✓ | Model name (default: `gemini-2.0-flash`) |
| `TAVILY_API_KEY` | ✓ | Tavily search API key |
| `TAVILY_DAILY_LIMIT` | ✓ | Switch to Brave before this (default: `900`) |
| `BRAVE_SEARCH_API_KEY` | ✓ | Brave Search API key (fallback) |
| `EMBEDDING_MODEL` | ✓ | HuggingFace model name for embeddings |
| `EMBEDDING_DIMENSION` | ✓ | Embedding vector size (default: `384`) |
| `SEMANTIC_CHUNK_THRESHOLD` | ✓ | Cosine similarity breakpoint (default: `0.75`) |
| `MAX_CHUNK_SIZE` | ✓ | Max chars per chunk (default: `800`) |
| `RAG_TOP_K` | ✓ | Chunks to retrieve per query (default: `8`) |
| `PORTAL_ENABLED` | — | Enable student portal scraping (default: `false`) |
| `CORS_ORIGINS` | ✓ | Comma-separated allowed origins |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | ✓ | Backend URL (e.g., `http://localhost:8000/api/v1`) |
| `NEXT_PUBLIC_USE_MOCK` | — | `true` to use mock data (no backend needed) |
| `NEXT_PUBLIC_SUPABASE_URL` | ✓ | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✓ | Supabase anon key (**never** service role key) |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | ✓ | Google OAuth client ID |
| `NEXT_PUBLIC_ALLOWED_EMAIL_DOMAIN` | ✓ | `diu.edu.bd` |
| `NEXT_PUBLIC_ENABLE_COMMUNITY` | — | Feature flag for community tab |
| `NEXT_PUBLIC_ENABLE_PORTAL` | — | Feature flag for student portal |

---

## API Reference

Base URL: `http://localhost:8000/api/v1`

Full interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Auth — `/auth`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/auth/me` | Required | Get current user profile |
| `PATCH` | `/auth/me` | Required | Update own profile |
| `POST` | `/auth/verify-domain` | — | Check if email is @diu.edu.bd |
| `PATCH` | `/auth/admin/role` | Admin | Change a user's role |

### Chat — `/chat`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/chat/message` | Optional | **SSE streaming** AI response |
| `POST` | `/chat/message/sync` | Optional | Full response (non-streaming) |
| `GET` | `/chat/sessions` | Required | List all my chat sessions |
| `GET` | `/chat/sessions/{id}` | Required | Get session + all messages |
| `POST` | `/chat/sessions` | Required | Create new session |
| `DELETE` | `/chat/sessions/{id}` | Required | Delete a session |
| `GET` | `/chat/debug/search-usage` | Required | Tavily daily usage stats |

**Streaming example (JavaScript):**
```javascript
const source = new EventSource('/api/v1/chat/message', {
  method: 'POST',
  body: JSON.stringify({ message: "MAK sir ki kal free achen?" })
});

source.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === 'chunk') process.stdout.write(data.text);
  if (data.type === 'done') source.close();
};
```

### Routines — `/routines`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/routines/upload` | Admin | Upload routine PDF |
| `GET` | `/routines/active` | — | Get active routine metadata |
| `GET` | `/routines/slots` | — | Query slots (day/teacher/room/batch) |
| `GET` | `/routines/teacher/{initials}/schedule` | — | Full teacher weekly schedule |
| `GET` | `/routines/teacher/{initials}/availability?date=YYYY-MM-DD` | — | Availability on a date |
| `POST` | `/routines/teacher/override` | Teacher | Mark self unavailable/busy |
| `DELETE` | `/routines/teacher/override/{id}` | Teacher | Remove override |

**Example — check teacher availability:**
```
GET /routines/teacher/MAK/availability?date=2026-05-20

Response:
{
  "date": "2026-05-20",
  "day": "Wednesday",
  "teacher": "MAK",
  "slots": [
    { "time": "08:00-09:30", "status": "in_class", "message": "Teaching CSE315 (Batch 66, Section E) in Room 410" },
    { "time": "09:30-11:00", "status": "available", "message": "Available" },
    ...
  ],
  "free_slots": [{"time_start": "09:30", "time_end": "11:00"}, ...],
  "ai_context": "MAK — Schedule for Wednesday (2026-05-20):\n  08:00-09:30: ✗ Busy..."
}
```

### Teachers — `/teachers`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/teachers` | — | List all teachers (search, dept filter) |
| `GET` | `/teachers/{id}` | — | Get one teacher's full info |
| `PUT` | `/teachers/me` | Teacher | Update own room, office hours |
| `PUT` | `/teachers/{id}` | Admin | Update any teacher |

### Community — `/community`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/community/posts` | — | List posts (category filter, paginated) |
| `POST` | `/community/posts` | Required | Create a post |
| `GET` | `/community/posts/{id}` | — | Get post + comments + reaction counts |
| `DELETE` | `/community/posts/{id}` | Owner/Admin | Delete post |
| `POST` | `/community/posts/{id}/react` | Required | Toggle reaction |
| `POST` | `/community/posts/{id}/comments` | Required | Add comment |
| `DELETE` | `/community/posts/{id}/comments/{cid}` | Owner/Admin | Delete comment |

### Notices — `/notices`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/notices` | — | List notices (pinned first, filters) |
| `POST` | `/notices` | Admin | Create notice + auto-notify all users |
| `GET` | `/notices/{id}` | — | Get single notice |
| `PATCH` | `/notices/{id}` | Admin | Update notice |
| `DELETE` | `/notices/{id}` | Admin | Soft-delete notice |
| `POST` | `/notices/{id}/pin` | Admin | Toggle pin status |

### Notifications — `/notifications`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/notifications` | Required | List my notifications + broadcasts |
| `GET` | `/notifications/unread-count` | Required | Badge count |
| `PATCH` | `/notifications/{id}/read` | Required | Mark one as read |
| `POST` | `/notifications/read-all` | Required | Mark all as read |
| `DELETE` | `/notifications/{id}` | Required | Delete notification |
| `POST` | `/notifications/send` | Admin | Send targeted or broadcast notification |

---

## AI System

### LLM Stack

| Model | Role |
|-------|------|
| **LLaMA 3.3 70B** (via Groq) | Primary LLM — fast, free, excellent Bangla support |
| **Gemini 2.0 Flash** | Fallback when Groq fails or rate-limits |
| **Gemini Vision** | PDF page image analysis (routine parser fallback) |

**Round-robin key rotation:** Up to 3 Groq API keys can be configured. The system rotates through them to avoid rate limits.

### RAG Pipeline

```
DIU Website (22+ pages)
     │
     ▼
DIUScraper (httpx + BeautifulSoup)
     │  rate-limited, extracts main content, saves to data/
     ▼
HybridChunker
     │  Pass 1: Semantic split — group sentences while cosine sim ≥ 0.75
     │  Pass 2: RecursiveCharacterTextSplitter — split chunks > 800 chars
     ▼
EmbeddingService (all-MiniLM-L6-v2, 384-dim, L2-normalized)
     │
     ▼
Supabase pgvector (document_chunks table)
     │
     ▼
match_document_chunks() — SQL RPC function
     │  cosine similarity search, threshold 0.45, top-K=8
     ▼
Context injected into LLM prompt
```

Why hybrid chunking? Fixed-size chunking (like DAIC's `chunk_size=1000`) splits mid-sentence and breaks semantic meaning. Our approach:
1. Group adjacent sentences while they stay on the same topic (cosine similarity)
2. Only split when topic changes or chunk gets too large

### Web Search

- **Tavily** — primary, 1000 req/month free plan, daily limit set to 900
- **Brave Search** — fallback, triggered automatically when Tavily approaches limit
- Both use `prefer_diu=True` to bias results toward `diu.edu.bd` domains

---

## Routine System

### PDF Parsing

The admin uploads a class routine PDF (DIU's landscape format with multi-level headers). The parser:

1. Opens PDF with `pdfplumber`
2. Detects metadata: title, version, semester, effective date
3. Iterates pages, detects day headers (Saturday, Sunday, ...)
4. Extracts tables using line-based strategy
5. Parses course cells: `"CSE315(66_E)"` → `course_code=CSE315, batch=66, section=E`
6. Falls back to **Gemini Vision** if a page fails to parse

### Time Slots

| Slot | Time |
|------|------|
| 1 | 08:00 – 09:30 |
| 2 | 09:30 – 11:00 |
| 3 | 11:00 – 12:30 |
| 4 | 12:30 – 14:00 |
| 5 | 14:00 – 15:30 |
| 6 | 15:30 – 17:00 |

### Auto-deactivation

When a new routine is uploaded for a department, a database trigger automatically sets all previous routines for that department to `is_active = false`. No manual cleanup needed.

---

## Database Schema

Three migration files, run in order:

### schema.sql (Phase 1)
- `profiles` — user profiles, linked to Supabase Auth via trigger
- `chat_sessions` — one per conversation thread
- `chat_messages` — individual messages (role: user/assistant)
- `community_posts`, `post_reactions`, `post_comments`
- `notices`, `notifications`
- `diu_knowledge` — scraped DIU pages (title, url, content)
- `document_chunks` — vector(384) embeddings for RAG
- `match_document_chunks()` — pgvector RPC function
- All RLS policies + Realtime enabled

### schema_v2_routine_teacher.sql (Phase 2)
- `routines` — routine metadata (title, dept, semester, version, file_url, is_active)
- `routine_slots` — individual class slots linked to a routine
- `teacher_info` — extra teacher data (initials, designation, room, office_hours JSONB)
- `teacher_availability` — override exceptions (unavailable/busy on specific dates)
- Auto-deactivate trigger for old routines

### schema_v3_community_notices.sql (Phase 3)
- `community_posts`: added `is_teacher_post`, `image_url`, optional `title`, expanded categories
- `post_reactions`: renamed `reaction_type → reaction`, added haha/wow/sad/angry
- `post_comments`: added `is_teacher_comment` for pinning logic
- `notices`: added `created_by`, `department`, `attachment_url`, `is_pinned`, `is_active`, `expires_at`
- `notifications`: nullable `user_id` (broadcasts), added `is_read`, `ref_id`, `ref_type`
- Updated RLS policies to allow guest reads + broadcast notifications

---

## Deployment

### Local Development
```
Backend:   http://localhost:8000   (FastAPI + uvicorn)
Frontend:  http://localhost:3000   (Next.js)
Docs:      http://localhost:8000/docs
```

### Staging (Testing)
| Service | Platform | Notes |
|---------|----------|-------|
| Frontend | Vercel | Auto-deploy from `main` branch |
| Backend | HuggingFace Spaces | Free GPU/CPU space (FastAPI) |

### Production
| Service | Platform |
|---------|----------|
| Frontend | Vercel |
| Backend | Hostinger VPS |
| Database | Supabase (same project) |

### HuggingFace Spaces Deployment
```bash
# Create a Dockerfile for the backend
# HuggingFace Spaces runs on port 7860 by default
APP_PORT=7860
```

---

## Contributing

This project is built by [MD Ratul Hossen](https://github.com/itzRatul) for Daffodil International University.

If you're a DIU student or teacher and want to contribute:

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes and commit with a clear message
4. Open a Pull Request

**Commit convention used in this project:**
```
feat: add new feature
fix: bug fix
refactor: code improvement without feature change
docs: documentation update
chore: setup, config, dependencies
```

---

## Security Notes

- `SUPABASE_SERVICE_ROLE_KEY` is used **only** in the backend. Never put it in the frontend or commit it to git.
- Google OAuth is restricted to `@diu.edu.bd` — enforced at the backend with a hard 403 block, not just a UI hint.
- All database tables have **Row Level Security (RLS)** enabled.
- JWT tokens are verified via `supabase_admin.auth.get_user(token)` on every protected request.
- Groq API keys are rotated in a round-robin cycle — even if one key leaks, the others still work.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  Built with ❤️ for DIU — Daffodil International University, Bangladesh
</div>
