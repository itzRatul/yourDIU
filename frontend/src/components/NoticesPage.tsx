"use client";
import { useState, useEffect } from "react";
import { FileText, ExternalLink } from "lucide-react";
import { notices, type Notice } from "@/lib/api";
import { config } from "@/lib/config";
import { mockNotices } from "@/lib/mock";

const CATEGORIES = ["all", "exam", "admission", "event", "general"];

const CATEGORY_COLORS: Record<string, string> = {
  exam:      "bg-red-500/10 text-red-400 border-red-500/20",
  admission: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  event:     "bg-purple-500/10 text-purple-400 border-purple-500/20",
  general:   "bg-diu-green/10 text-diu-green border-diu-green/20",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-BD", { day: "numeric", month: "short", year: "numeric" });
}

export default function NoticesPage() {
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
    <div className="max-w-3xl mx-auto p-6">
      <div className="flex items-center gap-3 mb-6">
        <FileText className="text-yellow-400" size={22} />
        <h1 className="text-xl font-bold text-diu-text">Notices</h1>
      </div>

      {/* Category filter */}
      <div className="flex gap-2 flex-wrap mb-6">
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors capitalize ${
              category === cat
                ? "bg-diu-green border-diu-green text-white"
                : "bg-diu-bg-card border-diu-border text-diu-text-dim hover:border-diu-green/40"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1,2,3,4].map(i => <div key={i} className="skeleton h-24 w-full" />)}
        </div>
      ) : items.length === 0 ? (
        <p className="text-center text-diu-text-dim py-12">No notices found.</p>
      ) : (
        <div className="space-y-3">
          {items.map(notice => (
            <div key={notice.id} className="bg-diu-bg-card border border-diu-border rounded-xl p-4 hover:border-diu-border-bright transition-colors">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs px-2 py-0.5 rounded-full border capitalize ${CATEGORY_COLORS[notice.category] ?? CATEGORY_COLORS.general}`}>
                      {notice.category}
                    </span>
                    <span className="text-xs text-diu-text-dim">{formatDate(notice.published_at)}</span>
                  </div>
                  <h3 className="text-sm font-medium text-diu-text">{notice.title}</h3>
                  <p className="text-xs text-diu-text-dim mt-1 line-clamp-2">{notice.content}</p>
                </div>
                {notice.source_url && (
                  <a href={notice.source_url} target="_blank" rel="noopener noreferrer"
                    className="text-diu-text-dim hover:text-diu-green transition-colors flex-shrink-0">
                    <ExternalLink size={15} />
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
