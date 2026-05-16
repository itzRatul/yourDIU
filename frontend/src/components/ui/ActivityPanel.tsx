"use client";
import { X, Activity, Cpu, Search, BookOpen, MapPin, Zap, ExternalLink } from "lucide-react";
import { clsx } from "clsx";
import type { SearchData } from "./SearchResultsPanel";

export interface ActivityStep {
  id: string;
  type: "thinking" | "search" | "rag" | "navigation" | "done" | "error";
  label: string;
  detail?: string;
  done?: boolean;
}

interface Props {
  open: boolean;
  steps: ActivityStep[];
  streaming: boolean;
  onClose: () => void;
  side?: "left" | "right";
  searchData?: SearchData | null;
}

const STEP_ICON: Record<ActivityStep["type"], typeof Cpu> = {
  thinking:   Cpu,
  search:     Search,
  rag:        BookOpen,
  navigation: MapPin,
  done:       Zap,
  error:      Zap,
};

const STEP_COLOR: Record<ActivityStep["type"], string> = {
  thinking:   "text-accent",
  search:     "text-amber-400",
  rag:        "text-blue-400",
  navigation: "text-emerald-400",
  done:       "text-accent-secondary",
  error:      "text-status-danger",
};

export default function ActivityPanel({ open, steps, streaming, onClose, side = "right", searchData }: Props) {
  const isLeft = side === "left";
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
          "fixed top-16 bottom-0 z-30 w-[272px] flex flex-col glass-panel transition-transform duration-300 ease-in-out",
          isLeft
            ? "left-0 border-r border-glass-border"
            : "right-0 border-l border-glass-border",
          open
            ? "translate-x-0"
            : isLeft ? "-translate-x-full" : "translate-x-full",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-glass-border flex-shrink-0">
          <span className="text-[0.78rem] font-semibold text-ink-dim uppercase tracking-wider flex items-center gap-2">
            <Activity size={13} />
            Activity
            {streaming && (
              <span className="w-1.5 h-1.5 rounded-full bg-accent-secondary animate-pulse" />
            )}
          </span>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-glass-sm text-ink-muted hover:text-ink hover:bg-bg-hover transition-all"
          >
            <X size={14} />
          </button>
        </div>

        {/* Steps */}
        <div className="flex-1 overflow-y-auto scrollbar-thin px-3 py-3">
          {steps.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-center">
              <Activity size={20} className="text-ink-muted" />
              <p className="text-ink-muted text-[0.75rem]">
                AI thinking steps will appear here
              </p>
              <p className="text-ink-faint text-[0.65rem]">
                Send a message to see activity
              </p>
            </div>
          ) : (
            <ul className="space-y-2">
              {steps.map((step, i) => {
                const Icon = STEP_ICON[step.type];
                const color = STEP_COLOR[step.type];
                return (
                  <li key={step.id} className="flex gap-3">
                    {/* Timeline dot + line */}
                    <div className="flex flex-col items-center">
                      <div className={clsx(
                        "w-6 h-6 rounded-full border flex items-center justify-center flex-shrink-0",
                        step.done
                          ? "bg-glass-fill border-glass-border"
                          : "bg-accent/10 border-accent/30 animate-pulse",
                      )}>
                        <Icon size={12} className={color} />
                      </div>
                      {i < steps.length - 1 && (
                        <div className="w-px flex-1 min-h-[12px] bg-glass-border mt-1" />
                      )}
                    </div>

                    {/* Content */}
                    <div className="pb-3 min-w-0">
                      <p className={clsx("text-[0.75rem] font-medium", step.done ? "text-ink-dim" : "text-ink")}>
                        {step.label}
                      </p>
                      {step.detail && (
                        <p className="text-[0.65rem] text-ink-muted mt-0.5 leading-relaxed break-words">
                          {step.detail}
                        </p>
                      )}
                    </div>
                  </li>
                );
              })}

              {/* Live thinking indicator */}
              {streaming && (
                <li className="flex gap-3">
                  <div className="w-6 h-6 rounded-full bg-accent/10 border border-accent/30 flex items-center justify-center flex-shrink-0">
                    <span className="w-2 h-2 rounded-full bg-accent animate-ping" />
                  </div>
                  <div className="pt-1">
                    <p className="text-[0.75rem] text-ink-dim">Processing…</p>
                  </div>
                </li>
              )}
            </ul>
          )}

          {/* Search results section (logged-in right panel) */}
          {!isLeft && searchData && (
            <div className="mt-4 pt-3 border-t border-glass-border space-y-2">
              <p className="text-[0.65rem] text-ink-muted uppercase tracking-wider px-1 flex items-center gap-1.5">
                <Search size={10} /> Web Search
              </p>
              <div className="px-2 py-1.5 rounded-[8px] bg-glass-fill border border-glass-border">
                <p className="text-[0.65rem] text-ink-muted mb-0.5">Query</p>
                <p className="text-[0.73rem] text-ink">{searchData.query}</p>
              </div>
              {searchData.results.map((r, i) => (
                <a
                  key={i}
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block px-2.5 py-2 rounded-[8px] bg-glass-fill border border-glass-border hover:bg-bg-hover transition-all group"
                >
                  <div className="flex items-start justify-between gap-1">
                    <p className="text-[0.7rem] text-ink font-medium line-clamp-2 group-hover:text-accent-secondary transition-colors">
                      {r.title}
                    </p>
                    <ExternalLink size={10} className="text-ink-muted flex-shrink-0 mt-0.5" />
                  </div>
                  <p className="text-[0.63rem] text-ink-muted mt-1 line-clamp-2">{r.snippet}</p>
                </a>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
