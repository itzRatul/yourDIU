"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import {
  Upload, FileText, Trash2, Send, Square, Globe, X,
  Loader2, BookOpen, BookMarked, ChevronRight, PanelLeftClose,
} from "lucide-react";
import { clsx } from "clsx";
import toast from "react-hot-toast";
import { pdf, type PDFSession, type ChatMessage } from "@/lib/api";
import { config } from "@/lib/config";
import { mockPDFSessions, mockChatResponses } from "@/lib/mock";

// ── helpers ───────────────────────────────────────────────────────────────────

function renderContent(text: string) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

function formatBytes(b: number) {
  if (b < 1024)    return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
}

// ── types ─────────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: string;
  streaming?: boolean;
  sources?: Source[];
}

interface Source {
  page: number;
  snippet: string;
}

const MOCK_SOURCES: Source[] = [
  { page: 3,  snippet: "A data structure is a way of organizing data in a computer so that it can be accessed and modified efficiently..." },
  { page: 7,  snippet: "Linked lists are dynamic data structures. The size is allocated at runtime. Each node stores data and a pointer to the next node..." },
  { page: 12, snippet: "The time complexity of binary search is O(log n) because the algorithm halves the search space with each iteration..." },
];

// ── Session card ──────────────────────────────────────────────────────────────

function SessionCard({ session, active, onClick, onDelete }: {
  session: PDFSession; active: boolean; onClick: () => void; onDelete: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        "group flex items-center gap-2.5 p-2.5 rounded-[10px] cursor-pointer transition-all border",
        active
          ? "bg-accent/15 border-accent/30"
          : "bg-glass-fill border-glass-border hover:bg-bg-hover hover:border-glass-border-strong",
        session.status !== "ready" && "cursor-default opacity-80",
      )}
    >
      <div className={clsx(
        "w-8 h-8 rounded-[8px] flex items-center justify-center flex-shrink-0 border",
        active
          ? "bg-accent/25 border-accent/40"
          : "bg-glass-fill border-glass-border",
      )}>
        {session.status === "processing"
          ? <Loader2 size={13} className="text-accent animate-spin" />
          : <FileText size={13} className={active ? "text-accent-secondary" : "text-ink-dim"} />
        }
      </div>

      <div className="flex-1 min-w-0">
        <p className={clsx("text-[0.75rem] font-medium truncate", active ? "text-ink" : "text-ink-dim")}>
          {session.filename}
        </p>
        <p className="text-[0.62rem] text-ink-muted mt-0.5">
          {session.status === "processing"
            ? "Processing…"
            : `${session.page_count}p · ${formatBytes(session.file_size)}`}
        </p>
      </div>

      {session.status === "ready" && (
        <button
          onClick={e => { e.stopPropagation(); onDelete(); }}
          className="text-ink-muted hover:text-status-danger transition-colors p-1 rounded-[6px] hover:bg-status-danger/10 opacity-0 group-hover:opacity-100"
        >
          <Trash2 size={12} />
        </button>
      )}
    </div>
  );
}

// ── Web search permission card ────────────────────────────────────────────────

function WebSearchCard({ query, onAllow, onDeny }: {
  query: string; onAllow: () => void; onDeny: () => void;
}) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[82%] glass-panel border border-amber-500/30 bg-amber-500/5 rounded-2xl rounded-bl-sm px-4 py-3.5">
        <div className="flex items-center gap-2 mb-1.5">
          <Globe size={13} className="text-amber-400" />
          <p className="text-[0.75rem] font-semibold text-amber-300">Not in PDF</p>
        </div>
        <p className="text-[0.72rem] text-ink-dim mb-3">
          Search the web for: <span className="text-amber-300 font-medium">{query}</span>?
        </p>
        <div className="flex gap-2">
          <button
            onClick={onAllow}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[0.72rem] font-medium rounded-[8px] hover:bg-amber-500/30 transition-colors"
          >
            <Globe size={11} /> Search web
          </button>
          <button
            onClick={onDeny}
            className="px-3 py-1.5 text-[0.72rem] text-ink-dim border border-glass-border rounded-[8px] hover:bg-bg-hover transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Source panel ──────────────────────────────────────────────────────────────

function SourcePanel({ sources, filename, onClose }: {
  sources: Source[]; filename: string; onClose: () => void;
}) {
  return (
    <aside className="w-[248px] flex-shrink-0 flex flex-col border-l border-glass-border glass-panel overflow-hidden">
      <div className="flex items-center justify-between px-3.5 py-3 border-b border-glass-border flex-shrink-0">
        <span className="text-[0.72rem] font-semibold text-ink-dim uppercase tracking-wider flex items-center gap-1.5">
          <BookMarked size={12} />
          Sources
        </span>
        <button
          onClick={onClose}
          className="w-6 h-6 flex items-center justify-center rounded-[6px] text-ink-muted hover:text-ink hover:bg-bg-hover transition-all"
        >
          <X size={12} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-2.5 py-2.5 space-y-2">
        <p className="text-[0.62rem] text-ink-muted px-1 truncate">From: {filename}</p>
        {sources.map((src, i) => (
          <div key={i} className="bg-glass-fill border border-glass-border rounded-[8px] p-2.5">
            <div className="flex items-center gap-1.5 mb-1.5">
              <div className="w-5 h-5 rounded-[5px] bg-accent/15 border border-accent/30 flex items-center justify-center flex-shrink-0">
                <span className="text-[0.6rem] font-bold text-accent-secondary">{i + 1}</span>
              </div>
              <span className="text-[0.65rem] font-medium text-ink-dim">Page {src.page}</span>
            </div>
            <p className="text-[0.66rem] text-ink-muted leading-relaxed line-clamp-4">{src.snippet}</p>
          </div>
        ))}
      </div>
    </aside>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface PageProps {
  sidebarOpen?: boolean;
  onCloseSidebar?: () => void;
  autoOpenSources?: boolean;
}

export default function PDFScrapperPage({
  sidebarOpen = true,
  onCloseSidebar,
  autoOpenSources = true,
}: PageProps) {
  const [sessions, setSessions]       = useState<PDFSession[]>([]);
  const [activeId, setActiveId]       = useState<string | null>(null);
  const [messages, setMessages]       = useState<Message[]>([]);
  const [input, setInput]             = useState("");
  const [streaming, setStreaming]     = useState(false);
  const [uploading, setUploading]     = useState(false);
  const [summary, setSummary]         = useState<string | null>(null);
  const [showSummary, setShowSummary] = useState(false);
  const [permQuery, setPermQuery]     = useState<string | null>(null);
  const [pendingMsg, setPendingMsg]   = useState<string | null>(null);
  const [sources, setSources]         = useState<Source[] | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef     = useRef<AbortController | null>(null);
  const bottomRef    = useRef<HTMLDivElement>(null);
  const textareaRef  = useRef<HTMLTextAreaElement>(null);

  const activeSession = sessions.find(s => s.id === activeId);

  useEffect(() => {
    if (config.useMock) { setSessions(mockPDFSessions); return; }
    pdf.list().then(r => setSessions(r.sessions)).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleUpload = async (file: File) => {
    if (file.size > 20 * 1024 * 1024) { toast.error("File too large (max 20 MB)"); return; }
    if (!file.name.toLowerCase().endsWith(".pdf")) { toast.error("Only PDF files accepted"); return; }
    setUploading(true);
    try {
      if (config.useMock) {
        const mock: PDFSession = {
          id: Date.now().toString(), filename: file.name, file_size: file.size,
          page_count: 0, chunk_count: 0, status: "processing", has_summary: false,
          expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
          created_at: new Date().toISOString(),
        };
        setSessions(p => [mock, ...p]);
        setTimeout(() => {
          setSessions(p => p.map(s => s.id === mock.id
            ? { ...s, status: "ready", page_count: 12, chunk_count: 45 } : s));
          setActiveId(mock.id);
          toast.success("PDF ready!");
        }, 2000);
        return;
      }
      const res = await pdf.upload(file);
      const newSession: PDFSession = {
        id: res.session_id, filename: file.name, file_size: file.size,
        page_count: 0, chunk_count: 0, status: "processing", has_summary: false,
        expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
        created_at: new Date().toISOString(),
      };
      setSessions(p => [newSession, ...p]);
      toast.success("Uploaded! Processing…");
      const poll = setInterval(async () => {
        try {
          const s = await pdf.get(res.session_id);
          setSessions(p => p.map(ps => ps.id === s.id ? s : ps));
          if (s.status === "ready") {
            clearInterval(poll); setActiveId(s.id); setMessages([]);
            toast.success("PDF ready to chat!");
          } else if (s.status === "failed") {
            clearInterval(poll); toast.error("Processing failed");
          }
        } catch { clearInterval(poll); }
      }, 3000);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const selectSession = (id: string) => {
    setActiveId(id); setMessages([]); setSummary(null);
    setShowSummary(false); setPermQuery(null); setSources(null);
  };

  const deleteSession = async (id: string) => {
    if (!config.useMock) {
      try { await pdf.delete(id); } catch { toast.error("Delete failed"); return; }
    }
    setSessions(p => p.filter(s => s.id !== id));
    if (activeId === id) { setActiveId(null); setMessages([]); setSources(null); }
    toast.success("Session deleted");
  };

  const loadSummary = async () => {
    if (!activeId || activeSession?.status !== "ready") return;
    if (summary) { setShowSummary(true); return; }
    try {
      if (config.useMock) {
        setSummary("**Main Topic**\nMock PDF summary for testing.\n\n**Key Points**\n- Point 1\n- Point 2");
        setShowSummary(true); return;
      }
      const res = await pdf.summarize(activeId);
      setSummary(res.summary); setShowSummary(true);
    } catch { toast.error("Summary failed"); }
  };

  const sendMessage = useCallback(async (text: string, allowWeb = false) => {
    if (!activeId || !text.trim() || streaming) return;
    setPermQuery(null); setPendingMsg(null);

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: text };
    setMessages(p => [...p, userMsg]);
    setInput("");
    setStreaming(true);
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    const assistantId = (Date.now() + 1).toString();
    setMessages(p => [...p, { id: assistantId, role: "assistant", content: "", streaming: true }]);

    const history: ChatMessage[] = messages.map(m => ({ role: m.role, content: m.content }));

    if (config.useMock) {
      const resp = mockChatResponses[Math.floor(Math.random() * mockChatResponses.length)];
      let i = 0;
      const iv = setInterval(() => {
        setMessages(p => p.map(m => m.id === assistantId ? { ...m, content: m.content + resp.slice(i, i + 5) } : m));
        i += 5;
        if (i >= resp.length) {
          clearInterval(iv);
          setMessages(p => p.map(m => m.id === assistantId
            ? { ...m, streaming: false, mode: "pdf_rag", sources: MOCK_SOURCES } : m));
          if (autoOpenSources) setSources(MOCK_SOURCES);
          setStreaming(false);
        }
      }, 40);
      return;
    }

    abortRef.current = new AbortController();
    await pdf.streamChat(
      activeId, text, history, allowWeb,
      (chunk) => setMessages(p => p.map(m => m.id === assistantId ? { ...m, content: m.content + chunk } : m)),
      (query) => {
        setMessages(p => p.filter(m => m.id !== assistantId));
        setStreaming(false); setPermQuery(query); setPendingMsg(text);
      },
      (mode) => {
        setMessages(p => p.map(m => m.id === assistantId ? { ...m, streaming: false, mode } : m));
        if (mode === "pdf_rag" && autoOpenSources) setSources(MOCK_SOURCES);
        setStreaming(false);
      },
      (err) => {
        toast.error(err);
        setMessages(p => p.map(m => m.id === assistantId
          ? { ...m, content: "Error. Try again.", streaming: false } : m));
        setStreaming(false);
      },
      abortRef.current.signal,
    );
  }, [activeId, streaming, messages]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); }
  };

  return (
    <div className="flex h-full bg-bg-base overflow-hidden">

      {/* ── Left sidebar: PDF list ─────────────────────────────────────────── */}
      <div className={clsx(
        "flex-shrink-0 overflow-hidden transition-[width] duration-300 ease-in-out",
        sidebarOpen ? "w-[248px]" : "w-0",
      )}>
      <div className="w-[248px] h-full flex flex-col border-r border-glass-border glass-panel">
        {/* Header */}
        <div className="px-3.5 pt-4 pb-3 border-b border-glass-border">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[0.65rem] text-ink-muted uppercase tracking-wider flex items-center gap-1.5">
              <FileText size={10} /> Your PDFs
            </p>
            <button
              onClick={onCloseSidebar}
              title="Close panel"
              className="w-6 h-6 flex items-center justify-center rounded-[6px] text-ink-muted hover:text-ink hover:bg-bg-hover transition-all"
            >
              <PanelLeftClose size={13} />
            </button>
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-accent text-white text-[0.76rem] font-medium rounded-[10px] hover:bg-accent-dark disabled:opacity-50 transition-colors"
          >
            {uploading
              ? <><Loader2 size={13} className="animate-spin" /> Uploading…</>
              : <><Upload size={13} strokeWidth={2.5} /> Upload PDF</>}
          </button>
          <input
            ref={fileInputRef} type="file" accept=".pdf" className="hidden"
            onChange={e => e.target.files?.[0] && handleUpload(e.target.files[0])}
          />
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto scrollbar-thin px-2.5 py-2.5 space-y-1.5">
          {sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-center pb-8">
              <FileText size={22} className="text-ink-muted" />
              <p className="text-[0.73rem] text-ink-dim">No PDFs yet</p>
              <p className="text-[0.62rem] text-ink-muted">Upload your first to start chatting</p>
            </div>
          ) : sessions.map(s => (
            <SessionCard
              key={s.id} session={s} active={s.id === activeId}
              onClick={() => s.status === "ready" && selectSession(s.id)}
              onDelete={() => deleteSession(s.id)}
            />
          ))}
        </div>

        <div className="px-3.5 py-2.5 border-t border-glass-border">
          <p className="text-[0.6rem] text-ink-muted flex items-center gap-1">
            <ChevronRight size={9} />PDFs auto-expire after 7 days
          </p>
        </div>
      </div>
      </div>

      {/* ── Center: chat area ──────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {!activeSession || activeSession.status !== "ready" ? (

          /* Welcome / no PDF selected */
          <div className="h-full flex flex-col items-center justify-center text-center px-6 gap-5 select-none">
            <div className="w-16 h-16 rounded-2xl bg-accent/20 border border-accent/30 flex items-center justify-center">
              <FileText size={28} className="text-accent-secondary" />
            </div>
            <div className="flex flex-col gap-2">
              <h2 className="text-2xl font-semibold text-gradient">PDF Scrapper</h2>
              <p className="text-ink-dim text-sm">Upload a PDF and chat with its content</p>
              <p className="text-ink-muted text-[0.72rem]">AI answers only from your PDF · optional web search</p>
            </div>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-5 py-2.5 bg-accent text-white text-sm font-medium rounded-[12px] hover:bg-accent-dark transition-colors"
            >
              <Upload size={15} strokeWidth={2.5} /> Upload PDF
            </button>
          </div>

        ) : (

          /* Active PDF chat */
          <>
            {/* PDF header bar */}
            <div className="flex items-center justify-between px-5 py-2.5 border-b border-glass-border flex-shrink-0">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-[7px] bg-accent/20 border border-accent/30 flex items-center justify-center flex-shrink-0">
                  <FileText size={12} className="text-accent-secondary" />
                </div>
                <div className="min-w-0">
                  <p className="text-[0.78rem] font-semibold text-ink truncate max-w-xs">{activeSession.filename}</p>
                  <p className="text-[0.62rem] text-ink-muted">{activeSession.page_count} pages · {formatBytes(activeSession.file_size)}</p>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={loadSummary}
                  className="flex items-center gap-1.5 text-[0.7rem] px-2.5 py-1.5 rounded-[8px] bg-glass-fill border border-glass-border text-ink-dim hover:bg-bg-hover hover:text-ink transition-all"
                >
                  <BookOpen size={12} /> Summary
                </button>
                <button
                  onClick={() => { setActiveId(null); setMessages([]); setSources(null); }}
                  className="w-7 h-7 flex items-center justify-center rounded-[7px] text-ink-muted hover:text-ink hover:bg-bg-hover transition-all"
                >
                  <X size={14} />
                </button>
              </div>
            </div>

            {/* Summary block */}
            {showSummary && summary && (
              <div className="mx-5 mt-3 p-4 glass-panel border border-glass-border rounded-[12px] relative">
                <button
                  onClick={() => setShowSummary(false)}
                  className="absolute top-2.5 right-2.5 w-6 h-6 flex items-center justify-center rounded-[6px] text-ink-muted hover:text-ink hover:bg-bg-hover"
                >
                  <X size={12} />
                </button>
                <div className="flex items-center gap-1.5 mb-2">
                  <BookOpen size={13} className="text-accent-secondary" />
                  <p className="text-[0.72rem] font-semibold text-ink">Summary</p>
                </div>
                <div
                  className="prose-chat text-[0.73rem] text-ink-dim"
                  dangerouslySetInnerHTML={{ __html: renderContent(summary) }}
                />
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto min-h-0 scrollbar-thin">
              <div className="max-w-2xl mx-auto px-5 py-5 space-y-4">
                {messages.length === 0 && (
                  <div className="text-center py-10">
                    <p className="text-[0.78rem] text-ink-dim">
                      Ask anything about <span className="text-accent-secondary font-medium">{activeSession.filename}</span>
                    </p>
                    <p className="text-[0.65rem] text-ink-muted mt-1">AI answers only from the PDF content</p>
                  </div>
                )}
                {messages.map(msg => (
                  <div key={msg.id} className={clsx("flex gap-2.5", msg.role === "user" ? "justify-end" : "justify-start")}>
                    {msg.role === "assistant" && (
                      <div className="w-7 h-7 rounded-full bg-accent/25 border border-accent/40 flex items-center justify-center flex-shrink-0 mt-0.5 text-[0.6rem] font-bold text-accent-secondary">
                        PDF
                      </div>
                    )}
                    <div className={clsx(
                      "max-w-[80%] text-sm rounded-2xl px-4 py-3",
                      msg.role === "user"
                        ? "bg-accent/20 border border-accent/30 text-ink rounded-br-sm"
                        : "bg-glass-fill border border-glass-border text-ink rounded-bl-sm",
                    )}>
                      {msg.role === "assistant" ? (
                        <>
                          <div className="prose-chat leading-relaxed" dangerouslySetInnerHTML={{ __html: renderContent(msg.content) }} />
                          {msg.streaming && (
                            <span className="inline-block w-1.5 h-4 bg-accent-secondary ml-0.5 align-middle animate-pulse rounded-sm" />
                          )}
                          {!msg.streaming && msg.mode && (
                            <div className="mt-2 inline-flex items-center px-2 py-0.5 rounded-full bg-accent-secondary/10 border border-accent-secondary/20 text-accent-secondary text-[0.62rem] font-medium">
                              {msg.mode.replace("_", " ")}
                            </div>
                          )}
                        </>
                      ) : (
                        <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                      )}
                    </div>
                  </div>
                ))}
                {permQuery && (
                  <WebSearchCard
                    query={permQuery}
                    onAllow={() => { if (pendingMsg) sendMessage(pendingMsg, true); }}
                    onDeny={() => { setPermQuery(null); setPendingMsg(null); }}
                  />
                )}
                <div ref={bottomRef} />
              </div>
            </div>

            {/* Input bar */}
            <div className="flex-shrink-0 px-5 pb-4 pt-2">
              <div className="max-w-2xl mx-auto">
                <div className="glass-panel rounded-[14px] border border-glass-border-strong flex items-end gap-2 p-2 focus-within:border-accent/40 transition-all duration-200">
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={`Ask about ${activeSession.filename}…`}
                    rows={1}
                    className="flex-1 resize-none bg-transparent px-3 py-2 text-sm text-ink placeholder-ink-muted focus:outline-none max-h-32 leading-relaxed"
                    style={{ minHeight: "36px" }}
                    onInput={e => {
                      const t = e.currentTarget;
                      t.style.height = "auto";
                      t.style.height = Math.min(t.scrollHeight, 128) + "px";
                    }}
                  />
                  {streaming ? (
                    <button
                      onClick={() => { abortRef.current?.abort(); setStreaming(false); }}
                      className="w-9 h-9 flex-shrink-0 flex items-center justify-center rounded-[10px] bg-status-danger/80 text-white hover:bg-status-danger transition-colors"
                      aria-label="Stop"
                    >
                      <Square size={13} fill="currentColor" />
                    </button>
                  ) : (
                    <button
                      onClick={() => sendMessage(input)}
                      disabled={!input.trim()}
                      className="w-9 h-9 flex-shrink-0 flex items-center justify-center rounded-[10px] bg-accent disabled:opacity-30 text-white hover:bg-accent-dark transition-colors"
                      aria-label="Send"
                    >
                      <Send size={15} strokeWidth={2.5} />
                    </button>
                  )}
                </div>
                <p className="text-center text-[0.62rem] text-ink-muted mt-1.5">
                  Enter to send · Shift+Enter for new line
                </p>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ── Right: Source panel ────────────────────────────────────────────── */}
      {sources && activeSession && (
        <SourcePanel
          sources={sources}
          filename={activeSession.filename}
          onClose={() => setSources(null)}
        />
      )}
    </div>
  );
}
