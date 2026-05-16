"use client";
import { useState, useRef, useEffect } from "react";
import { Sparkles, FileScan, FileText, Bell, Handshake, Plus, AlignJustify } from "lucide-react";
import { clsx } from "clsx";

export type AppMode = "assistant" | "pdf" | "notice";

export interface PanelSettings {
  autoOpenThinking: boolean;
  autoOpenSearch: boolean;
  autoOpenSources: boolean;
}

export interface TopBarProps {
  mode: AppMode;
  onModeChange: (m: AppMode) => void;
  isGuest: boolean;
  unreadCount?: number;
  historyOpen: boolean;
  activityOpen: boolean;
  searchOpen: boolean;
  pdfListOpen: boolean;
  noticeListOpen: boolean;
  onToggleHistory: () => void;
  onToggleActivity: () => void;
  onToggleSearch: () => void;
  onTogglePdfList: () => void;
  onToggleNoticeList: () => void;
  onOpenNotifications: () => void;
  onOpenCommunity: () => void;
  onNewChat: () => void;
  settings: PanelSettings;
  onSettingsChange: (s: PanelSettings) => void;
}

const MODES: { id: AppMode; label: string; icon: typeof Sparkles; loggedInOnly?: boolean }[] = [
  { id: "assistant", label: "AI Assistant", icon: Sparkles },
  { id: "pdf",       label: "PDF Scrapper", icon: FileScan, loggedInOnly: true },
  { id: "notice",    label: "Notice",       icon: FileText },
];

export default function TopBar({
  mode, onModeChange, isGuest, unreadCount = 0,
  historyOpen, activityOpen, searchOpen, pdfListOpen, noticeListOpen,
  onToggleHistory, onToggleActivity, onToggleSearch, onTogglePdfList, onToggleNoticeList,
  onOpenNotifications, onOpenCommunity, onNewChat,
  settings, onSettingsChange,
}: TopBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const visibleModes = MODES.filter(m => !m.loggedInOnly || !isGuest);

  // Close menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const toggle = (key: keyof PanelSettings) => {
    onSettingsChange({ ...settings, [key]: !settings[key] });
  };

  return (
    <header className="relative z-30 grid grid-cols-[1fr_auto_1fr] items-center h-16 px-6 glass-panel rounded-b-glass border-t-0 flex-shrink-0">
      {/* Logo */}
      <div className="flex items-baseline gap-2.5 min-w-0">
        <h1 className="text-[1.15rem] font-bold tracking-[2px] text-gradient flex-shrink-0">yourDIU</h1>
        <span className="hidden lg:inline text-[0.62rem] font-light text-ink-muted tracking-[0.3px] truncate">
          Virtual assistant of Daffodil International University
        </span>
      </div>

      {/* Mode switch — always true center */}
      <div className="flex justify-center">
        <div className="relative flex bg-glass-fill border border-glass-border rounded-[12px] p-[3px] gap-0.5">
          {visibleModes.map(({ id, label, icon: Icon }) => {
            const active = mode === id;
            return (
              <button
                key={id}
                onClick={() => onModeChange(id)}
                className={clsx(
                  "relative z-[1] flex items-center gap-1.5 px-4 py-[7px] text-[0.76rem] font-medium rounded-[10px] whitespace-nowrap transition-colors",
                  active ? "bg-accent text-white shadow-glow-sm" : "text-ink-dim hover:text-ink",
                )}
              >
                <Icon size={15} strokeWidth={active ? 2.4 : 2} />
                <span className="hidden md:inline">{label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Right cluster */}
      <div className="flex items-center gap-2 justify-end">
        <div className="hidden lg:flex items-center gap-1.5 text-[0.7rem] text-ink-dim mr-1">
          <span className="w-[7px] h-[7px] rounded-full bg-status-success shadow-[0_0_6px_#51cf66] animate-pulse-dot" />
          <span>{isGuest ? "Guest" : "Online"}</span>
        </div>

        <IconBtn label="Notifications" onClick={onOpenNotifications} badge={unreadCount}>
          <Bell size={17} strokeWidth={2} />
        </IconBtn>

        <IconBtn label="Community" onClick={onOpenCommunity}>
          <Handshake size={17} strokeWidth={2} />
        </IconBtn>

        <IconBtn label="New chat" onClick={onNewChat}>
          <Plus size={17} strokeWidth={2.2} />
        </IconBtn>

        {/* Hamburger menu — panel controls + settings */}
        <div ref={menuRef} className="relative">
          <IconBtn label="Menu" onClick={() => setMenuOpen(o => !o)} active={menuOpen}>
            <AlignJustify size={17} strokeWidth={2} />
          </IconBtn>

          {menuOpen && (
            <div className="absolute right-0 top-[calc(100%+8px)] w-[248px] glass-panel rounded-glass border border-glass-border-strong shadow-glass-lg z-50 py-3 px-1">

              {/* Panel toggles */}
              <p className="text-[0.65rem] text-ink-muted uppercase tracking-wider px-3 pb-1.5">
                Panels
              </p>

              {mode === "pdf" ? (
                <ToggleRow
                  label="PDF List"
                  description="Uploaded PDFs (left)"
                  checked={pdfListOpen}
                  onChange={() => { onTogglePdfList(); setMenuOpen(false); }}
                  pill={false}
                />
              ) : mode === "notice" ? (
                <ToggleRow
                  label="Filter panel"
                  description="Category filters (left)"
                  checked={noticeListOpen}
                  onChange={() => { onToggleNoticeList(); setMenuOpen(false); }}
                  pill={false}
                />
              ) : (
                <>
                  <ToggleRow
                    label={isGuest ? "Thinking panel" : "Activity panel"}
                    description={isGuest ? "AI thinking steps (left)" : "Thinking + search (right)"}
                    checked={activityOpen}
                    onChange={() => { onToggleActivity(); setMenuOpen(false); }}
                    pill={false}
                  />

                  {!isGuest && (
                    <ToggleRow
                      label="History"
                      description="Chat history (left)"
                      checked={historyOpen}
                      onChange={() => { onToggleHistory(); setMenuOpen(false); }}
                      pill={false}
                    />
                  )}

                  {isGuest && (
                    <ToggleRow
                      label="Search results"
                      description="Web search results (right)"
                      checked={searchOpen}
                      onChange={() => { onToggleSearch(); setMenuOpen(false); }}
                      pill={false}
                    />
                  )}
                </>
              )}

              {/* Auto-open settings */}
              <div className="mt-2 pt-2 border-t border-glass-border">
                <p className="text-[0.65rem] text-ink-muted uppercase tracking-wider px-3 pb-1.5">
                  Auto-open
                </p>

                {mode === "assistant" && (
                  <>
                    <ToggleRow
                      label="Auto-open thinking"
                      description="Opens when AI starts responding"
                      checked={settings.autoOpenThinking}
                      onChange={() => toggle("autoOpenThinking")}
                      pill
                    />
                    <ToggleRow
                      label="Auto-open search"
                      description="Opens on web search results"
                      checked={settings.autoOpenSearch}
                      onChange={() => toggle("autoOpenSearch")}
                      pill
                    />
                  </>
                )}

                {mode === "pdf" && (
                  <ToggleRow
                    label="Auto-open sources"
                    description="Opens after PDF RAG response"
                    checked={settings.autoOpenSources}
                    onChange={() => toggle("autoOpenSources")}
                    pill
                  />
                )}

                {mode === "notice" && (
                  <p className="text-[0.7rem] text-ink-muted px-3 py-2">No auto-open settings for notices.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function ToggleRow({
  label, description, checked, onChange, pill = true,
}: {
  label: string; description: string; checked: boolean; onChange: () => void; pill?: boolean;
}) {
  return (
    <button
      onClick={onChange}
      className="w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-[10px] hover:bg-bg-hover transition-all text-left"
    >
      <div className="min-w-0">
        <p className={clsx("text-[0.76rem] font-medium", checked ? "text-ink" : "text-ink-dim")}>
          {label}
        </p>
        <p className="text-[0.65rem] text-ink-muted mt-0.5">{description}</p>
      </div>

      {pill ? (
        /* Toggle pill (auto-open settings) */
        <div className={clsx(
          "relative flex-shrink-0 w-9 h-5 rounded-full border transition-all duration-200",
          checked ? "bg-accent border-accent" : "bg-glass-fill border-glass-border",
        )}>
          <span className={clsx(
            "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200",
            checked ? "translate-x-4" : "translate-x-0.5",
          )} />
        </div>
      ) : (
        /* Dot indicator (panel open/close) */
        <span className={clsx(
          "flex-shrink-0 w-2 h-2 rounded-full transition-all",
          checked ? "bg-accent-secondary shadow-[0_0_6px_#4ecdc4]" : "bg-glass-border",
        )} />
      )}
    </button>
  );
}

function IconBtn({
  children, onClick, label, active = false, badge = 0,
}: {
  children: React.ReactNode; onClick: () => void; label: string;
  active?: boolean; badge?: number;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className={clsx(
        "relative grid place-items-center w-[34px] h-[34px] rounded-glass-sm border transition-all",
        active
          ? "bg-accent/20 border-accent/40 text-accent-secondary"
          : "bg-glass-fill border-glass-border text-ink-dim hover:bg-bg-hover hover:border-glass-border-strong hover:text-ink",
      )}
    >
      {children}
      {badge > 0 && (
        <span className="absolute -top-1 -right-1 min-w-[16px] h-[16px] px-1 rounded-full bg-status-danger text-white text-[9px] font-bold flex items-center justify-center ring-2 ring-bg-base">
          {badge > 9 ? "9+" : badge}
        </span>
      )}
    </button>
  );
}
