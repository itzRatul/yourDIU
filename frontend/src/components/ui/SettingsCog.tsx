"use client";
import { useState, useRef, useEffect } from "react";
import { Settings2, LogOut, User } from "lucide-react";
import { clsx } from "clsx";

export interface UserProfile {
  name: string;
  email: string;
  avatar?: string;
}

interface Props {
  isGuest: boolean;
  user?: UserProfile;
  onLoginWithGoogle: () => void;
  onSignOut: () => void;
}

export default function SettingsCog({ isGuest, user, onLoginWithGoogle, onSignOut }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const initial = user?.name?.[0]?.toUpperCase() ?? "U";

  return (
    <div ref={ref} className="fixed bottom-5 right-5 z-40">
      {/* Dropdown — opens upward */}
      {open && (
        <div className="absolute bottom-[calc(100%+10px)] right-0 w-[248px] glass-panel rounded-glass border border-glass-border-strong shadow-glass-lg py-3 px-1 animate-in fade-in slide-in-from-bottom-2 duration-150">

          {/* Profile card */}
          <div className="flex items-center gap-3 px-3 py-2 mb-1">
            <div className={clsx(
              "w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold border",
              isGuest
                ? "bg-glass-fill border-glass-border text-ink-dim"
                : "bg-accent/25 border-accent/40 text-accent-secondary",
            )}>
              {isGuest ? <User size={18} strokeWidth={1.8} /> : initial}
            </div>
            <div className="min-w-0">
              <p className="text-[0.8rem] font-semibold text-ink truncate">
                {isGuest ? "Guest User" : (user?.name ?? "User")}
              </p>
              <p className="text-[0.65rem] text-ink-muted truncate">
                {isGuest ? "Not signed in" : (user?.email ?? "")}
              </p>
            </div>
          </div>

          <div className="mx-3 h-px bg-glass-border mb-1.5" />

          {isGuest ? (
            <button
              onClick={() => { onLoginWithGoogle(); setOpen(false); }}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[10px] hover:bg-bg-hover transition-all text-left"
            >
              <GoogleIcon />
              <span className="text-[0.78rem] font-medium text-ink">Sign in with Google</span>
            </button>
          ) : (
            <button
              onClick={() => { onSignOut(); setOpen(false); }}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[10px] hover:bg-status-danger/10 transition-all text-left"
            >
              <LogOut size={16} className="text-status-danger flex-shrink-0" />
              <span className="text-[0.78rem] font-medium text-status-danger">Sign out</span>
            </button>
          )}
        </div>
      )}

      {/* Trigger button */}
      <button
        onClick={() => setOpen(o => !o)}
        title="Account & settings"
        aria-label="Account & settings"
        className={clsx(
          "w-11 h-11 grid place-items-center border-2 overflow-hidden transition-all",
          user?.avatar && !isGuest
            ? clsx("rounded-full", open ? "border-accent shadow-glow-sm" : "border-glass-border hover:border-accent/60")
            : clsx("rounded-[12px]", open
                ? "bg-accent/20 border-accent/40 text-accent-secondary"
                : "bg-glass-fill border-glass-border text-ink-dim hover:bg-bg-hover hover:border-glass-border-strong hover:text-ink"),
        )}
      >
        {!isGuest && user?.avatar ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img src={user.avatar} alt={user.name} className="w-full h-full object-cover" referrerPolicy="no-referrer" />
        ) : (
          <Settings2 size={17} strokeWidth={2} />
        )}
      </button>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" className="flex-shrink-0">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}
