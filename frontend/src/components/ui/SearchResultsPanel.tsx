"use client";
import { X, Search, ExternalLink } from "lucide-react";
import { clsx } from "clsx";

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
}

export interface SearchData {
  query: string;
  answer?: string;
  results: SearchResult[];
}

interface Props {
  open: boolean;
  data: SearchData | null;
  streaming: boolean;
  onClose: () => void;
}

export default function SearchResultsPanel({ open, data, streaming, onClose }: Props) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/40 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={clsx(
          "fixed top-16 right-0 bottom-0 z-30 w-[272px] flex flex-col glass-panel border-l border-glass-border transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-glass-border flex-shrink-0">
          <span className="text-[0.78rem] font-semibold text-ink-dim uppercase tracking-wider flex items-center gap-2">
            <Search size={13} />
            Web Search
            {streaming && (
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            )}
          </span>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-glass-sm text-ink-muted hover:text-ink hover:bg-bg-hover transition-all"
          >
            <X size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin px-3 py-3">
          {!data ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-center">
              <Search size={20} className="text-ink-muted" />
              <p className="text-ink-muted text-[0.75rem]">
                Web search results will appear here
              </p>
              {streaming && (
                <p className="text-amber-400 text-[0.65rem] animate-pulse">
                  Searching…
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {/* Query */}
              <div className="px-2 py-1.5 rounded-[8px] bg-glass-fill border border-glass-border">
                <p className="text-[0.65rem] text-ink-muted uppercase tracking-wider mb-0.5">Query</p>
                <p className="text-[0.75rem] text-ink font-medium">{data.query}</p>
              </div>

              {/* AI answer */}
              {data.answer && (
                <div className="px-2 py-2 rounded-[8px] bg-accent/10 border border-accent/20">
                  <p className="text-[0.65rem] text-accent uppercase tracking-wider mb-1">Answer</p>
                  <p className="text-[0.73rem] text-ink-dim leading-relaxed">{data.answer}</p>
                </div>
              )}

              {/* Source cards */}
              {data.results.length > 0 && (
                <div className="space-y-2">
                  <p className="text-[0.65rem] text-ink-muted uppercase tracking-wider px-1">
                    Sources ({data.results.length})
                  </p>
                  {data.results.map((r, i) => (
                    <a
                      key={i}
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block px-2.5 py-2 rounded-[8px] bg-glass-fill border border-glass-border hover:border-glass-border-strong hover:bg-bg-hover transition-all group"
                    >
                      <div className="flex items-start justify-between gap-1">
                        <p className="text-[0.72rem] text-ink font-medium leading-snug line-clamp-2 group-hover:text-accent-secondary transition-colors">
                          {r.title}
                        </p>
                        <ExternalLink size={10} className="text-ink-muted flex-shrink-0 mt-0.5" />
                      </div>
                      <p className="text-[0.65rem] text-ink-muted mt-1 line-clamp-2 leading-relaxed">
                        {r.snippet}
                      </p>
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
