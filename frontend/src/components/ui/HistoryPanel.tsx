"use client";
import { X, MessageSquare, Clock, LogIn } from "lucide-react";
import { clsx } from "clsx";

export interface ChatHistoryItem {
  id: string;
  title: string;
  preview: string;
  timestamp: Date;
}

interface Props {
  open: boolean;
  isGuest: boolean;
  history: ChatHistoryItem[];
  activeChatId?: string;
  onClose: () => void;
  onSelectChat: (id: string) => void;
  onLoginClick: () => void;
}

function timeAgo(date: Date): string {
  const diff = (Date.now() - date.getTime()) / 1000;
  if (diff < 60)   return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function HistoryPanel({
  open,
  isGuest,
  history,
  activeChatId,
  onClose,
  onSelectChat,
  onLoginClick,
}: Props) {
  return (
    <>
      {/* Backdrop (mobile) */}
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/40 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <aside
        className={clsx(
          "fixed top-16 left-0 bottom-0 z-30 w-[272px] flex flex-col glass-panel border-r border-glass-border transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-glass-border flex-shrink-0">
          <span className="text-[0.78rem] font-semibold text-ink-dim uppercase tracking-wider flex items-center gap-2">
            <Clock size={13} /> History
          </span>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-glass-sm text-ink-muted hover:text-ink hover:bg-bg-hover transition-all"
          >
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto scrollbar-thin py-2">
          {isGuest ? (
            <div className="flex flex-col items-center justify-center h-full gap-4 px-5 text-center">
              <div className="w-10 h-10 rounded-full bg-accent/20 border border-accent/30 flex items-center justify-center">
                <LogIn size={16} className="text-accent-secondary" />
              </div>
              <p className="text-ink-dim text-[0.78rem] leading-relaxed">
                Login to save and view your chat history
              </p>
              <button
                onClick={onLoginClick}
                className="px-4 py-2 rounded-full text-[0.75rem] font-medium bg-accent text-white hover:bg-accent-dark transition-colors"
              >
                Sign in with Google
              </button>
            </div>
          ) : history.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 px-5 text-center">
              <MessageSquare size={20} className="text-ink-muted" />
              <p className="text-ink-muted text-[0.75rem]">No chat history yet</p>
            </div>
          ) : (
            <ul className="space-y-0.5 px-2">
              {history.map(item => (
                <li key={item.id}>
                  <button
                    onClick={() => onSelectChat(item.id)}
                    className={clsx(
                      "w-full text-left px-3 py-2.5 rounded-[10px] transition-all group",
                      item.id === activeChatId
                        ? "bg-accent/20 border border-accent/30"
                        : "hover:bg-bg-hover border border-transparent",
                    )}
                  >
                    <p className={clsx(
                      "text-[0.78rem] font-medium truncate",
                      item.id === activeChatId ? "text-ink" : "text-ink-dim group-hover:text-ink",
                    )}>
                      {item.title}
                    </p>
                    <p className="text-[0.65rem] text-ink-muted truncate mt-0.5">
                      {item.preview}
                    </p>
                    <p className="text-[0.6rem] text-ink-faint mt-1">
                      {timeAgo(item.timestamp)}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </>
  );
}
