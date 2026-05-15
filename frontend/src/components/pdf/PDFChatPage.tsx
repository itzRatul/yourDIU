"use client";
import { useState, useRef, useCallback } from "react";
import { Upload, FileText, Trash2, Send, Square, Globe, X, Loader2, BookOpen } from "lucide-react";
import { clsx } from "clsx";
import toast from "react-hot-toast";
import { pdf, type PDFSession, type ChatMessage } from "@/lib/api";
import { config } from "@/lib/config";
import { mockPDFSessions, mockChatResponses } from "@/lib/mock";

function renderContent(text: string) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: string;
  streaming?: boolean;
}

// ── Permission dialog ─────────────────────────────────────────────────────────
function WebSearchDialog({ query, onAllow, onDeny }: { query: string; onAllow: () => void; onDeny: () => void }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] bg-diu-bg-card border border-yellow-500/30 rounded-2xl rounded-bl-sm p-4">
        <p className="text-sm text-diu-text mb-1">📄 This topic is not found in the uploaded PDF.</p>
        <p className="text-xs text-diu-text-dim mb-3">Search query: <span className="text-yellow-400">{query}</span></p>
        <div className="flex gap-2">
          <button onClick={onAllow} className="flex items-center gap-1.5 px-3 py-1.5 bg-diu-green text-white text-xs rounded-lg hover:bg-diu-green-dark transition-colors">
            <Globe size={12} /> Search web
          </button>
          <button onClick={onDeny} className="px-3 py-1.5 text-xs text-diu-text-dim border border-diu-border rounded-lg hover:bg-diu-bg-hover transition-colors">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Session card ──────────────────────────────────────────────────────────────
function SessionCard({ session, active, onClick, onDelete }: {
  session: PDFSession; active: boolean;
  onClick: () => void; onDelete: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        "flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-colors border",
        active
          ? "bg-blue-500/10 border-blue-500/30"
          : "bg-diu-bg-card border-diu-border hover:bg-diu-bg-hover",
      )}
    >
      <FileText size={16} className={active ? "text-blue-400" : "text-diu-text-dim"} />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-diu-text truncate">{session.filename}</p>
        <p className="text-xs text-diu-text-dim">
          {session.status === "processing"
            ? "Processing..."
            : `${session.page_count}p · ${formatBytes(session.file_size)}`}
        </p>
      </div>
      {session.status === "processing" && <Loader2 size={12} className="text-diu-green animate-spin" />}
      {session.status === "ready" && (
        <button onClick={e => { e.stopPropagation(); onDelete(); }}
          className="text-diu-text-dim hover:text-red-400 transition-colors">
          <Trash2 size={12} />
        </button>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function PDFChatPage() {
  const [sessions, setSessions]   = useState<PDFSession[]>([]);
  const [activeId, setActiveId]   = useState<string | null>(null);
  const [messages, setMessages]   = useState<Message[]>([]);
  const [input, setInput]         = useState("");
  const [streaming, setStreaming] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [summary, setSummary]     = useState<string | null>(null);
  const [showSummary, setShowSummary] = useState(false);
  const [permQuery, setPermQuery] = useState<string | null>(null);
  const [pendingMsg, setPendingMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef     = useRef<AbortController | null>(null);
  const bottomRef    = useRef<HTMLDivElement>(null);

  const activeSession = sessions.find(s => s.id === activeId);

  // Load sessions on mount
  useState(() => {
    if (config.useMock) { setSessions(mockPDFSessions); return; }
    pdf.list().then(r => setSessions(r.sessions)).catch(() => {});
  });

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
        id: res.session_id, filename: res.status, file_size: file.size,
        page_count: 0, chunk_count: 0, status: "processing", has_summary: false,
        expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
        created_at: new Date().toISOString(),
      };
      setSessions(p => [{ ...newSession, filename: file.name }, ...p]);
      toast.success("Uploaded! Processing...");
      // Poll until ready
      const poll = setInterval(async () => {
        try {
          const s = await pdf.get(res.session_id);
          setSessions(p => p.map(ps => ps.id === s.id ? s : ps));
          if (s.status === "ready") {
            clearInterval(poll);
            setActiveId(s.id);
            setMessages([]);
            toast.success("PDF ready to chat!");
          } else if (s.status === "failed") {
            clearInterval(poll);
            toast.error("PDF processing failed");
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
    setActiveId(id);
    setMessages([]);
    setSummary(null);
    setShowSummary(false);
    setPermQuery(null);
  };

  const deleteSession = async (id: string) => {
    if (!config.useMock) {
      try { await pdf.delete(id); } catch { toast.error("Delete failed"); return; }
    }
    setSessions(p => p.filter(s => s.id !== id));
    if (activeId === id) { setActiveId(null); setMessages([]); }
    toast.success("Session deleted");
  };

  const loadSummary = async () => {
    if (!activeId || !activeSession || activeSession.status !== "ready") return;
    if (summary) { setShowSummary(true); return; }
    try {
      if (config.useMock) {
        setSummary("**Main Topic**\nMock PDF summary for testing.\n\n**Key Points**\n- Point 1\n- Point 2");
        setShowSummary(true);
        return;
      }
      const res = await pdf.summarize(activeId);
      setSummary(res.summary);
      setShowSummary(true);
    } catch { toast.error("Summary failed"); }
  };

  const sendMessage = useCallback(async (text: string, allowWeb = false) => {
    if (!activeId || !text.trim() || streaming) return;
    setPermQuery(null);
    setPendingMsg(null);

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: text };
    setMessages(p => [...p, userMsg]);
    setInput("");
    setStreaming(true);

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
          setMessages(p => p.map(m => m.id === assistantId ? { ...m, streaming: false, mode: "pdf_rag" } : m));
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
        setStreaming(false);
        setPermQuery(query);
        setPendingMsg(text);
      },
      (mode) => {
        setMessages(p => p.map(m => m.id === assistantId ? { ...m, streaming: false, mode } : m));
        setStreaming(false);
      },
      (err) => {
        toast.error(err);
        setMessages(p => p.map(m => m.id === assistantId ? { ...m, content: "Error. Try again.", streaming: false } : m));
        setStreaming(false);
      },
      abortRef.current.signal,
    );
  }, [activeId, streaming, messages]);

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0 bg-diu-bg-card border-r border-diu-border flex flex-col">
        <div className="p-4 border-b border-diu-border">
          <h2 className="font-semibold text-diu-text mb-3 flex items-center gap-2">
            <FileText size={16} className="text-blue-400" /> PDF Chat
          </h2>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-500/10 border border-blue-500/30 text-blue-400 text-sm rounded-lg hover:bg-blue-500/20 transition-colors disabled:opacity-50"
          >
            {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
            {uploading ? "Uploading..." : "Upload PDF"}
          </button>
          <input ref={fileInputRef} type="file" accept=".pdf" className="hidden"
            onChange={e => e.target.files?.[0] && handleUpload(e.target.files[0])} />
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {sessions.length === 0 ? (
            <p className="text-xs text-diu-text-dim text-center mt-4">No PDFs yet. Upload one!</p>
          ) : sessions.map(s => (
            <SessionCard key={s.id} session={s} active={s.id === activeId}
              onClick={() => s.status === "ready" && selectSession(s.id)}
              onDelete={() => deleteSession(s.id)} />
          ))}
        </div>

        <div className="p-3 border-t border-diu-border text-xs text-diu-text-dim">
          PDFs expire after 7 days
        </div>
      </div>

      {/* Chat area */}
      {!activeSession || activeSession.status !== "ready" ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="w-16 h-16 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mx-auto mb-4">
              <FileText className="text-blue-400" size={28} />
            </div>
            <h3 className="font-semibold text-diu-text mb-1">Upload a PDF to start</h3>
            <p className="text-sm text-diu-text-dim max-w-xs">
              Chat with any PDF — research papers, textbooks, notes. AI answers only from the PDF content.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col min-w-0">
          {/* PDF header */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-diu-border bg-diu-bg-card">
            <div className="flex items-center gap-2">
              <FileText size={15} className="text-blue-400" />
              <span className="text-sm font-medium text-diu-text truncate max-w-xs">{activeSession.filename}</span>
              <span className="text-xs text-diu-text-dim">{activeSession.page_count}p</span>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={loadSummary}
                className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg border border-diu-border text-diu-text-dim hover:border-diu-green/40 hover:text-diu-green transition-colors">
                <BookOpen size={12} /> Summary
              </button>
              <button onClick={() => { setActiveId(null); setMessages([]); }}
                className="text-diu-text-dim hover:text-diu-text transition-colors">
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Summary panel */}
          {showSummary && summary && (
            <div className="m-4 p-4 bg-diu-bg-card border border-diu-border rounded-xl relative">
              <button onClick={() => setShowSummary(false)} className="absolute top-3 right-3 text-diu-text-dim hover:text-diu-text">
                <X size={14} />
              </button>
              <h4 className="text-sm font-semibold text-diu-text mb-2">PDF Summary</h4>
              <div className="prose-chat text-sm text-diu-text-dim"
                dangerouslySetInnerHTML={{ __html: renderContent(summary) }} />
            </div>
          )}

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.length === 0 && (
              <div className="text-center py-10">
                <p className="text-sm text-diu-text-dim">Ask anything about <span className="text-blue-400">{activeSession.filename}</span></p>
                <p className="text-xs text-diu-text-dim mt-1">AI answers only from the PDF content</p>
              </div>
            )}
            {messages.map(msg => (
              <div key={msg.id} className={clsx("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                <div className={clsx(
                  "max-w-[75%] rounded-2xl px-4 py-3 text-sm",
                  msg.role === "user"
                    ? "bg-blue-500 text-white rounded-br-sm"
                    : "bg-diu-bg-card border border-diu-border text-diu-text rounded-bl-sm",
                )}>
                  {msg.role === "assistant" ? (
                    <>
                      <div className="prose-chat" dangerouslySetInnerHTML={{ __html: renderContent(msg.content) }} />
                      {msg.streaming && <span className="inline-block w-1.5 h-4 bg-blue-400 animate-pulse ml-0.5 align-middle" />}
                      {!msg.streaming && msg.mode && (
                        <p className="text-xs text-diu-text-dim mt-1 capitalize">{msg.mode.replace("_", " ")}</p>
                      )}
                    </>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}
            {permQuery && (
              <WebSearchDialog
                query={permQuery}
                onAllow={() => { if (pendingMsg) sendMessage(pendingMsg, true); }}
                onDeny={() => { setPermQuery(null); setPendingMsg(null); }}
              />
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-diu-border bg-diu-bg-card">
            <div className="flex items-end gap-3">
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
                placeholder={`Ask about ${activeSession.filename}...`}
                rows={1}
                className="flex-1 resize-none bg-diu-bg-base border border-diu-border rounded-xl px-4 py-3 text-sm text-diu-text placeholder-diu-text-dim focus:outline-none focus:border-blue-400 transition-colors max-h-32"
                style={{ minHeight: "44px" }}
                onInput={e => {
                  const t = e.currentTarget;
                  t.style.height = "auto";
                  t.style.height = Math.min(t.scrollHeight, 128) + "px";
                }}
              />
              {streaming ? (
                <button onClick={() => { abortRef.current?.abort(); setStreaming(false); }}
                  className="w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors">
                  <Square size={16} fill="currentColor" />
                </button>
              ) : (
                <button onClick={() => sendMessage(input)} disabled={!input.trim()}
                  className="w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-xl bg-blue-500 disabled:opacity-30 hover:bg-blue-600 transition-colors">
                  <Send size={16} className="text-white" />
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
