/**
 * Typed API client for yourDIU backend.
 * Reads the JWT from Supabase session and attaches it as Bearer token.
 */
import { config } from "./config";
import { supabase } from "./supabase";

async function getToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${config.apiUrl}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Chat ─────────────────────────────────────────────────────────────────────

export type ChatMessage = { role: "user" | "assistant"; content: string };

export async function streamChat(
  message: string,
  history: ChatMessage[],
  onChunk: (text: string) => void,
  onDone: (mode: string) => void,
  onError: (msg: string) => void,
  signal?: AbortSignal,
) {
  const token = await getToken();
  const res = await fetch(`${config.apiUrl}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, history }),
    signal,
  });

  if (!res.ok || !res.body) {
    onError(`Server error: ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let mode = "direct";
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const ev = JSON.parse(line.slice(6));
        if (ev.type === "meta")  mode = ev.mode ?? mode;
        if (ev.type === "chunk") onChunk(ev.content ?? "");
        if (ev.type === "done")  onDone(mode);
        if (ev.type === "error") onError(ev.message ?? "Unknown error");
      } catch { /* skip malformed */ }
    }
  }
}

// ── PDF Chat ──────────────────────────────────────────────────────────────────

export interface PDFSession {
  id: string; filename: string; file_size: number; page_count: number;
  chunk_count: number; status: "processing" | "ready" | "failed";
  summary?: string; has_summary: boolean; expires_at: string; created_at: string;
}

export const pdf = {
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ session_id: string; status: string; filename: string; message: string }>(
      "/pdf-chat/sessions",
      { method: "POST", body: fd, headers: {} },
    );
  },
  list: () => request<{ sessions: PDFSession[]; count: number }>("/pdf-chat/sessions"),
  get:  (id: string) => request<PDFSession>(`/pdf-chat/sessions/${id}`),
  delete: (id: string) => request<{ message: string }>(`/pdf-chat/sessions/${id}`, { method: "DELETE" }),
  summarize: (id: string) => request<{ summary: string; cached: boolean }>(`/pdf-chat/sessions/${id}/summarize`, { method: "POST" }),

  async streamChat(
    sessionId: string,
    message: string,
    history: ChatMessage[],
    allowWebSearch: boolean,
    onChunk: (text: string) => void,
    onNeedsPermission: (query: string) => void,
    onDone: (mode: string) => void,
    onError: (msg: string) => void,
    signal?: AbortSignal,
  ) {
    const token = await getToken();
    const res = await fetch(`${config.apiUrl}/pdf-chat/sessions/${sessionId}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, history, allow_web_search: allowWebSearch }),
      signal,
    });

    if (!res.ok || !res.body) { onError(`Server error: ${res.status}`); return; }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let mode = "pdf_rag";
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const ev = JSON.parse(line.slice(6));
          if (ev.type === "meta")             mode = ev.mode ?? mode;
          if (ev.type === "chunk")            onChunk(ev.content ?? "");
          if (ev.type === "needs_permission") onNeedsPermission(ev.search_query ?? message);
          if (ev.type === "done")             onDone(mode);
          if (ev.type === "error")            onError(ev.message ?? "Unknown error");
        } catch { /* skip */ }
      }
    }
  },
};

// ── Community ─────────────────────────────────────────────────────────────────

export interface Post {
  id: string; user_id: string; content: string; image_url?: string;
  likes_count: number; comments_count: number; created_at: string;
  author?: { full_name: string; avatar_url?: string };
  is_liked?: boolean;
}

export const community = {
  list:   (page = 0) => request<{ posts: Post[]; count: number }>(`/community/posts?offset=${page * 20}`),
  create: (content: string, imageUrl?: string) =>
    request<Post>("/community/posts", { method: "POST", body: JSON.stringify({ content, image_url: imageUrl }) }),
  like:   (id: string) => request<{ liked: boolean; likes_count: number }>(`/community/posts/${id}/like`, { method: "POST" }),
  delete: (id: string) => request<{ message: string }>(`/community/posts/${id}`, { method: "DELETE" }),
};

// ── Notices ───────────────────────────────────────────────────────────────────

export interface Notice {
  id: string; title: string; content: string; category: string;
  source_url?: string; published_at: string; created_at: string;
}

export const notices = {
  list: (page = 0, category?: string) =>
    request<{ notices: Notice[]; count: number }>(
      `/notices?offset=${page * 20}${category ? `&category=${category}` : ""}`,
    ),
};

// ── Notifications ─────────────────────────────────────────────────────────────

export interface Notification {
  id: string; title: string; body: string; type: string;
  is_read: boolean; created_at: string;
}

export const notifications = {
  list:       () => request<{ notifications: Notification[]; unread_count: number }>("/notifications"),
  markRead:   (id: string) => request<{ message: string }>(`/notifications/${id}/read`, { method: "POST" }),
  markAllRead:() => request<{ message: string }>("/notifications/read-all", { method: "POST" }),
};
