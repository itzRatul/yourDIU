"use client";
import { useState, useEffect } from "react";
import { Bell, CheckCheck } from "lucide-react";
import { clsx } from "clsx";
import toast from "react-hot-toast";
import { notifications as notifApi, type Notification } from "@/lib/api";
import { config } from "@/lib/config";
import { mockNotifications } from "@/lib/mock";

function timeAgo(iso: string) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60)    return `${s}s ago`;
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function NotificationsPage() {
  const [items, setItems]     = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (config.useMock) { setItems(mockNotifications); setLoading(false); return; }
    notifApi.list()
      .then(r => setItems(r.notifications))
      .finally(() => setLoading(false));
  }, []);

  const markRead = async (id: string) => {
    setItems(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    if (!config.useMock) notifApi.markRead(id).catch(() => {});
  };

  const markAll = async () => {
    setItems(prev => prev.map(n => ({ ...n, is_read: true })));
    if (!config.useMock) {
      try { await notifApi.markAllRead(); toast.success("All marked as read"); }
      catch { toast.error("Failed"); }
    }
  };

  const unread = items.filter(n => !n.is_read).length;

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Bell className="text-orange-400" size={22} />
          <h1 className="text-xl font-bold text-diu-text">Notifications</h1>
          {unread > 0 && (
            <span className="bg-diu-green text-white text-xs font-bold px-2 py-0.5 rounded-full">{unread}</span>
          )}
        </div>
        {unread > 0 && (
          <button onClick={markAll} className="flex items-center gap-1.5 text-xs text-diu-text-dim hover:text-diu-green transition-colors">
            <CheckCheck size={14} /> Mark all read
          </button>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1,2,3].map(i => <div key={i} className="skeleton h-16 w-full" />)}
        </div>
      ) : items.length === 0 ? (
        <p className="text-center text-diu-text-dim py-12">No notifications yet.</p>
      ) : (
        <div className="space-y-2">
          {items.map(n => (
            <button
              key={n.id}
              onClick={() => markRead(n.id)}
              className={clsx(
                "w-full text-left p-4 rounded-xl border transition-colors",
                n.is_read
                  ? "bg-diu-bg-card border-diu-border opacity-60"
                  : "bg-diu-bg-card border-diu-border hover:border-diu-green/40",
              )}
            >
              <div className="flex items-start gap-3">
                <div className={clsx("w-2 h-2 rounded-full mt-1.5 flex-shrink-0", n.is_read ? "bg-diu-border" : "bg-diu-green")} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-diu-text">{n.title}</p>
                  <p className="text-xs text-diu-text-dim mt-0.5">{n.body}</p>
                  <p className="text-xs text-diu-muted mt-1">{timeAgo(n.created_at)}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
