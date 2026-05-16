"use client";
import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { Send, Square } from "lucide-react";
import { clsx } from "clsx";
import toast from "react-hot-toast";
import { streamChat, type ChatMessage } from "@/lib/api";
import { config } from "@/lib/config";
import { mockChatResponses } from "@/lib/mock";

const CHIPS = [
  "DIU তে ভর্তির প্রক্রিয়া কী?",
  "CSE department সম্পর্কে বলো",
  "Main Gate থেকে Food Court কিভাবে যাবো?",
  "What can you do?",
];

const MODE_TAG: Record<string, string> = {
  navigation: "Campus Nav",
  rag:        "DIU Knowledge",
  search:     "Web Search",
  routine:    "Schedule",
  teacher:    "Teacher Info",
  direct:     "Direct",
};

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: string;
  streaming?: boolean;
}

function renderContent(text: string) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

export interface ActivityStep {
  id: string;
  type: "thinking" | "search" | "rag" | "navigation" | "done" | "error";
  label: string;
  detail?: string;
  done?: boolean;
}

const MODE_TO_STEP_TYPE: Record<string, ActivityStep["type"]> = {
  navigation: "navigation",
  rag:        "rag",
  search:     "search",
  routine:    "rag",
  teacher:    "rag",
  direct:     "done",
};

interface Props {
  isGuest: boolean;
  setOrbActive: (active: boolean) => void;
  onActivityStep?: (step: ActivityStep) => void;
  onSend?: () => void;
  onSearchResult?: (query: string) => void;
}

export default function AssistantChat({ isGuest, setOrbActive, onActivityStep, onSend, onSearchResult }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput]       = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef   = useRef<HTMLDivElement>(null);
  const abortRef    = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const greeting = useMemo(() => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning.";
    if (h < 17) return "Good afternoon.";
    return "Good evening.";
  }, []);

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
    setOrbActive(true);
    onSend?.();
    onActivityStep?.({ id: Date.now().toString(), type: "thinking", label: "Thinking…", done: false });

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    const assistantId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, { id: assistantId, role: "assistant", content: "", streaming: true }]);

    if (config.useMock) {
      const resp = mockChatResponses[Math.floor(Math.random() * mockChatResponses.length)];
      let i = 0;
      const interval = setInterval(() => {
        const chunk = resp.slice(i, i + 5);
        i += 5;
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content + chunk } : m,
        ));
        if (i >= resp.length) {
          clearInterval(interval);
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, streaming: false, mode: "direct" } : m,
          ));
          setStreaming(false);
          setOrbActive(false);
        }
      }, 40);
      return;
    }

    const history: ChatMessage[] = messages.map(m => ({ role: m.role, content: m.content }));
    abortRef.current = new AbortController();

    await streamChat(
      msg,
      history,
      (chunk) => setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: m.content + chunk } : m,
      )),
      (mode) => {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, streaming: false, mode } : m,
        ));
        onActivityStep?.({
          id: (Date.now() + 2).toString(),
          type: MODE_TO_STEP_TYPE[mode] ?? "done",
          label: MODE_TAG[mode] ?? "Done",
          detail: `Responded via ${MODE_TAG[mode] ?? mode}`,
          done: true,
        });
        if (mode === "search") onSearchResult?.(msg);
        setStreaming(false);
        setOrbActive(false);
      },
      (err) => {
        toast.error(err);
        setMessages(prev => prev.map(m =>
          m.id === assistantId
            ? { ...m, content: "Sorry, something went wrong. Please try again.", streaming: false }
            : m,
        ));
        setStreaming(false);
        setOrbActive(false);
      },
      abortRef.current.signal,
    );
  }, [streaming, messages, setOrbActive, onActivityStep, onSend, onSearchResult]);

  const stopStream = () => {
    abortRef.current?.abort();
    setStreaming(false);
    setOrbActive(false);
    setMessages(prev => prev.map(m => m.streaming ? { ...m, streaming: false } : m));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages / welcome */}
      <div className="flex-1 overflow-y-auto min-h-0 scrollbar-thin">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-6 gap-5 select-none">
            {/* DIU logo mark */}
            <span
              className="text-gradient font-bold leading-none"
              style={{ fontSize: "clamp(1.6rem, 5vw, 2.6rem)", letterSpacing: "0.22em" }}
            >
              DIU
            </span>

            {/* Greeting */}
            <div className="flex flex-col gap-1.5">
              <h2
                className="font-semibold text-ink leading-tight"
                style={{ fontSize: "clamp(1.6rem, 5vw, 2.2rem)" }}
              >
                {greeting}
              </h2>
              <p className="text-ink-dim text-sm">How may I assist you today?</p>
            </div>

            {/* Chips */}
            <div className="flex flex-wrap justify-center gap-2 max-w-md">
              {CHIPS.map(chip => (
                <button
                  key={chip}
                  onClick={() => send(chip)}
                  className="px-4 py-2 rounded-full text-[0.78rem] text-ink-dim border border-glass-border bg-glass-fill hover:bg-bg-hover hover:text-ink hover:border-glass-border-strong transition-all"
                >
                  {chip}
                </button>
              ))}
            </div>

            {isGuest && (
              <p className="text-ink-muted text-[0.68rem]">
                Browsing as guest · AI chat is free · history not saved
              </p>
            )}
          </div>
        ) : (
          <div className="max-w-3xl mx-auto px-4 md:px-6 py-6 space-y-4">
            {messages.map(msg => (
              <div
                key={msg.id}
                className={clsx("flex gap-3", msg.role === "user" ? "justify-end" : "justify-start")}
              >
                {msg.role === "assistant" && (
                  <div className="w-7 h-7 rounded-full bg-accent/30 border border-accent/40 flex items-center justify-center flex-shrink-0 mt-0.5 text-[0.58rem] font-bold text-accent-secondary">
                    AI
                  </div>
                )}
                <div className={clsx(
                  "max-w-[78%] text-sm rounded-2xl px-4 py-3",
                  msg.role === "user"
                    ? "bg-accent/20 border border-accent/30 text-ink rounded-br-sm"
                    : "bg-glass-fill border border-glass-border text-ink rounded-bl-sm",
                )}>
                  {msg.role === "assistant" ? (
                    <>
                      <div
                        className="prose-chat leading-relaxed"
                        dangerouslySetInnerHTML={{ __html: renderContent(msg.content) }}
                      />
                      {msg.streaming && (
                        <span className="inline-block w-1.5 h-4 bg-accent-secondary ml-0.5 align-middle animate-pulse rounded-sm" />
                      )}
                      {!msg.streaming && msg.mode && MODE_TAG[msg.mode] && (
                        <div className="mt-2 inline-flex items-center px-2 py-0.5 rounded-full bg-accent-secondary/10 border border-accent-secondary/20 text-accent-secondary text-[0.62rem] font-medium">
                          {MODE_TAG[msg.mode]}
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="flex-shrink-0 px-4 md:px-6 pb-4 pt-2">
        <div className="max-w-3xl mx-auto">
          <div className="glass-panel rounded-[16px] border border-glass-border-strong flex items-end gap-2 p-2 focus-within:border-accent/40 transition-all duration-200">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about DIU..."
              rows={1}
              className="flex-1 resize-none bg-transparent px-3 py-2 text-sm text-ink placeholder-ink-muted focus:outline-none max-h-32 leading-relaxed"
              style={{ minHeight: "38px" }}
              onInput={e => {
                const t = e.currentTarget;
                t.style.height = "auto";
                t.style.height = Math.min(t.scrollHeight, 128) + "px";
              }}
            />
            {streaming ? (
              <button
                onClick={stopStream}
                className="w-9 h-9 flex-shrink-0 flex items-center justify-center rounded-[10px] bg-status-danger/80 text-white hover:bg-status-danger transition-colors"
                aria-label="Stop"
              >
                <Square size={13} fill="currentColor" />
              </button>
            ) : (
              <button
                onClick={() => send(input)}
                disabled={!input.trim()}
                className="w-9 h-9 flex-shrink-0 flex items-center justify-center rounded-[10px] bg-accent disabled:opacity-30 disabled:cursor-not-allowed text-white hover:bg-accent-dark transition-colors"
                aria-label="Send"
              >
                <Send size={15} strokeWidth={2.5} />
              </button>
            )}
          </div>
          <p className="text-center text-[0.65rem] text-ink-muted mt-1.5">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}
