"use client";
import { useState, useEffect } from "react";
import { FileText, ExternalLink, PanelLeftClose } from "lucide-react";
import { clsx } from "clsx";
import { notices, type Notice } from "@/lib/api";
import { config } from "@/lib/config";
import { mockNotices } from "@/lib/mock";

interface PageProps {
  sidebarOpen?: boolean;
  onCloseSidebar?: () => void;
}

const CATEGORIES: { id: string; label: string; color: string; dot: string }[] = [
  { id: "all",       label: "All",       color: "text-amber-400",   dot: "bg-amber-400" },
  { id: "exam",      label: "Exam",      color: "text-red-400",     dot: "bg-red-400" },
  { id: "admission", label: "Admission", color: "text-blue-400",    dot: "bg-blue-400" },
  { id: "event",     label: "Event",     color: "text-violet-400",  dot: "bg-violet-400" },
  { id: "general",   label: "General",   color: "text-emerald-400", dot: "bg-emerald-400" },
];

const BADGE_STYLES: Record<string, string> = {
  exam:      "bg-red-400/15 text-red-400 border-red-400/25",
  admission: "bg-blue-400/15 text-blue-400 border-blue-400/25",
  event:     "bg-violet-400/15 text-violet-400 border-violet-400/25",
  general:   "bg-emerald-400/15 text-emerald-400 border-emerald-400/25",
  all:       "bg-amber-400/15 text-amber-400 border-amber-400/25",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-BD", { day: "numeric", month: "short", year: "numeric" });
}

export default function NoticesPage({ sidebarOpen = true, onCloseSidebar }: PageProps) {
  const [items, setItems]       = useState<Notice[]>([]);
  const [category, setCategory] = useState("all");
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    setLoading(true);
    if (config.useMock) {
      const filtered = category === "all" ? mockNotices : mockNotices.filter(n => n.category === category);
      setItems(filtered);
      setLoading(false);
      return;
    }
    notices.list(0, category === "all" ? undefined : category)
      .then(r => setItems(r.notices))
      .finally(() => setLoading(false));
  }, [category]);

  return (
    <div className="h-full flex overflow-hidden">
      {/* Left sidebar — category filters */}
      <div className={clsx(
        "flex-shrink-0 overflow-hidden transition-[width] duration-300 ease-in-out",
        sidebarOpen ? "w-[220px]" : "w-0",
      )}>
        <div className="w-[220px] h-full flex flex-col border-r border-glass-border glass-panel">
          {/* Sidebar header */}
          <div className="flex items-center justify-between px-4 py-4 border-b border-glass-border flex-shrink-0">
            <div className="flex items-center gap-2">
              <FileText size={15} className="text-accent-secondary" strokeWidth={2} />
              <span className="text-[0.78rem] font-semibold text-ink">Categories</span>
            </div>
            <button
              onClick={onCloseSidebar}
              title="Close filter panel"
              className="w-7 h-7 grid place-items-center rounded-[8px] text-ink-muted hover:text-ink hover:bg-bg-hover transition-all"
            >
              <PanelLeftClose size={15} strokeWidth={2} />
            </button>
          </div>

          {/* Category pills */}
          <div className="flex-1 overflow-y-auto p-3 space-y-1">
            {CATEGORIES.map(({ id, label, color, dot }) => {
              const active = category === id;
              return (
                <button
                  key={id}
                  onClick={() => setCategory(id)}
                  className={clsx(
                    "w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[10px] text-left transition-all text-[0.8rem] font-medium",
                    active
                      ? "bg-accent/15 border border-accent/30 text-ink"
                      : "text-ink-dim hover:bg-bg-hover border border-transparent",
                  )}
                >
                  <span className={clsx("w-2 h-2 rounded-full flex-shrink-0", active ? dot : "bg-glass-border")} />
                  <span className={active ? color : ""}>{label}</span>
                  {active && (
                    <span className={clsx("ml-auto text-[0.65rem] font-semibold", color)}>
                      {items.length}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main notices area */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-glass-border">
          <div className="flex items-center gap-2">
            <FileText size={18} className="text-amber-400" strokeWidth={2} />
            <h2 className="text-[1.05rem] font-semibold text-ink">Official Notices</h2>
            <span className="text-[0.68rem] text-ink-muted ml-1">Daffodil International University</span>
          </div>
        </div>

        {/* Notices list */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {loading ? (
            <>
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="h-24 rounded-[14px] bg-glass-fill border border-glass-border animate-pulse" />
              ))}
            </>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 gap-3 text-center">
              <div className="w-14 h-14 rounded-2xl bg-amber-400/10 border border-amber-400/20 flex items-center justify-center">
                <FileText size={22} className="text-amber-400" strokeWidth={1.8} />
              </div>
              <p className="text-ink-dim text-sm font-medium">No notices found</p>
              <p className="text-ink-muted text-xs">Try a different category</p>
            </div>
          ) : (
            items.map(notice => (
              <NoticeCard key={notice.id} notice={notice} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function NoticeCard({ notice }: { notice: Notice }) {
  return (
    <div className="group glass-panel rounded-[14px] border border-glass-border hover:border-glass-border-strong p-4 transition-all hover:shadow-glass">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Badge + date row */}
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className={clsx(
              "text-[0.65rem] font-semibold px-2 py-0.5 rounded-full border capitalize",
              BADGE_STYLES[notice.category] ?? BADGE_STYLES.general,
            )}>
              {notice.category}
            </span>
            <span className="text-[0.68rem] text-ink-muted">{formatDate(notice.published_at)}</span>
          </div>

          <h3 className="text-[0.84rem] font-semibold text-ink leading-snug">{notice.title}</h3>
          <p className="text-[0.76rem] text-ink-dim mt-1.5 line-clamp-2 leading-relaxed">{notice.content}</p>
        </div>

        {notice.source_url && (
          <a
            href={notice.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 p-1.5 rounded-[8px] text-ink-muted hover:text-accent-secondary hover:bg-bg-hover transition-all"
          >
            <ExternalLink size={14} />
          </a>
        )}
      </div>
    </div>
  );
}
