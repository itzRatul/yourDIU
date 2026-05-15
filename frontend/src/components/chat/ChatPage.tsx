"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Square, Trash2, MapPin, Zap, Search, BookOpen } from "lucide-react";
import { clsx } from "clsx";
import toast from "react-hot-toast";
import { streamChat, type ChatMessage } from "@/lib/api";
import { config } from "@/lib/config";
import { mockChatResponses } from "@/lib/mock";

const MODE_LABELS: Record<string, { label: string; icon: typeof Zap; color: string }> = {
  navigation: { label: "Navigation",   icon: MapPin,    color: "text-diu-green" },
  rag:        { label: "Knowledge",    icon: BookOpen,  color: "text-blue-400" },
  search:     { label: "Web Search",  icon: Search,    color: "text-yellow-400" },
  routine:    { label: "Schedule",    icon: Zap,       color: "text-purple-400" },
  teacher:    { label: "Teacher",     icon: Zap,       color: "text-orange-400" },
  direct:     { label: "Direct",      icon: Zap,       color: "text-diu-text-dim" },
};

const STARTERS = [
  "Main Gate 1 থেকে Food Court কিভাবে যাবো?",
  "আজকে MAK স্যার available আছেন?",
  "CSE department সম্পর্কে বলো",
  "DIU তে ভর্তির প্রক্রিয়া কী?",
];

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: string;
  streaming?: boolean;
}

function renderContent(text: string) {
  // Very lightweight markdown — bold, inline code, line breaks
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput]       = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef  = useRef<HTMLDivElement>(null);
  const abortRef   = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = useCallback(async (text: string) => {
    const msg = text.trim();
    if (!msg || streaming) return;

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: msg };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setStreaming(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, { id: assistantId, role: "assistant", content: "", streaming: true }]);

    if (config.useMock) {
      // Simulate streaming with mock
      const resp = mockChatResponses[Math.floor(Math.random() * mockChatResponses.length)];
      let i = 0;
      const interval = setInterval(() => {
        const chunk = resp.slice(i, i + 5);
        i += 5;
        setMessages(prev => prev.map(m => m.id === assistantId
          ? { ...m, content: m.content + chunk }
          : m,
        ));
        if (i >= resp.length) {
          clearInterval(interval);
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, streaming: false, mode: "direct" } : m));
          setStreaming(false);
        }
      }, 40);
      return;
    }

    const history: ChatMessage[] = messages.map(m => ({ role: m.role, content: m.content }));
    abortRef.current = new AbortController();

    await streamChat(
      msg, history,
      (chunk) => {
        setMessages(prev => prev.map(m => m.id === assistantId
          ? { ...m, content: m.content + chunk }
          : m,
        ));
      },
      (mode) => {
        setMessages(prev => prev.map(m => m.id === assistantId
          ? { ...m, streaming: false, mode }
          : m,
        ));
        setStreaming(false);
      },
      (err) => {
        toast.error(err);
        setMessages(prev => prev.map(m => m.id === assistantId
          ? { ...m, content: "Sorry, something went wrong. Please try again.", streaming: false }
          : m,
        ));
        setStreaming(false);
      },
      abortRef.current.signal,
    );
  }, [streaming, messages]);

  const stopStream = () => {
    abortRef.current?.abort();
    setStreaming(false);
    setMessages(prev => prev.map(m => m.streaming ? { ...m, streaming: false } : m));
  };

  const clearChat = () => {
    if (streaming) stopStream();
    setMessages([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-diu-border bg-diu-bg-card">
        <div>
          <h1 className="font-semibold text-diu-text">DIU Assistant</h1>
          <p className="text-xs text-diu-text-dim">Ask about schedules, teachers, campus, and more</p>
        </div>
        {messages.length > 0 && (
          <button onClick={clearChat} className="flex items-center gap-1.5 text-xs text-diu-text-dim hover:text-red-400 transition-colors px-2 py-1 rounded">
            <Trash2 size={13} /> Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-6 pb-10">
            <div className="text-center">
              <div className="w-14 h-14 rounded-2xl bg-diu-green/10 border border-diu-green/20 flex items-center justify-center mx-auto mb-3">
                <span className="text-diu-green text-2xl font-bold">D</span>
              </div>
              <h2 className="text-lg font-semibold text-diu-text">DIU AI Assistant</h2>
              <p className="text-sm text-diu-text-dim mt-1 max-w-sm">
                Ask about class routines, teacher availability, campus navigation, or general DIU information.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 w-full max-w-lg">
              {STARTERS.map(s => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left p-3 bg-diu-bg-card border border-diu-border rounded-xl text-sm text-diu-text-dim hover:border-diu-green/40 hover:text-diu-text hover:bg-diu-bg-hover transition-all"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={clsx("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
            <div className={clsx(
              "max-w-[75%] rounded-2xl px-4 py-3 text-sm",
              msg.role === "user"
                ? "bg-diu-green text-white rounded-br-sm"
                : "bg-diu-bg-card border border-diu-border text-diu-text rounded-bl-sm",
            )}>
              {msg.role === "assistant" ? (
                <>
                  <div
                    className="prose-chat"
                    dangerouslySetInnerHTML={{ __html: renderContent(msg.content) || (msg.streaming ? "" : "") }}
                  />
                  {msg.streaming && (
                    <span className="inline-block w-1.5 h-4 bg-diu-green animate-pulse ml-0.5 align-middle" />
                  )}
                  {!msg.streaming && msg.mode && MODE_LABELS[msg.mode] && (
                    <div className={clsx("flex items-center gap-1 mt-2 text-xs", MODE_LABELS[msg.mode].color)}>
                      {(() => { const { icon: Icon } = MODE_LABELS[msg.mode]; return <Icon size={11} />; })()}
                      {MODE_LABELS[msg.mode].label}
                    </div>
                  )}
                </>
              ) : (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-diu-border bg-diu-bg-card">
        <div className="flex items-end gap-3 max-w-4xl mx-auto">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about DIU..."
            rows={1}
            className="flex-1 resize-none bg-diu-bg-base border border-diu-border rounded-xl px-4 py-3 text-sm text-diu-text placeholder-diu-text-dim focus:outline-none focus:border-diu-green transition-colors max-h-32"
            style={{ height: "auto", minHeight: "44px" }}
            onInput={e => {
              const t = e.currentTarget;
              t.style.height = "auto";
              t.style.height = Math.min(t.scrollHeight, 128) + "px";
            }}
          />
          {streaming ? (
            <button
              onClick={stopStream}
              className="w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors"
            >
              <Square size={16} fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={() => send(input)}
              disabled={!input.trim()}
              className="w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-xl bg-diu-green disabled:opacity-30 disabled:cursor-not-allowed hover:bg-diu-green-dark transition-colors"
            >
              <Send size={16} className="text-white" />
            </button>
          )}
        </div>
        <p className="text-center text-xs text-diu-text-dim mt-2">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  );
}
