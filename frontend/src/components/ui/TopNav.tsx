"use client";
import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  MessageSquare, Users, Bell, FileText, FileScan, Home, LogOut, Sparkles, ChevronDown, Menu, X,
} from "lucide-react";
import { clsx } from "clsx";
import { useAuth } from "@/hooks/useAuth";

const MAIN_NAV = [
  { href: "/",              icon: Home,          label: "Home",         accent: "from-indigo-500 to-violet-500" },
  { href: "/chat",          icon: MessageSquare, label: "AI Chat",      accent: "from-indigo-500 to-violet-500" },
  { href: "/pdf-scrapper",  icon: FileScan,      label: "PDF Scrapper", accent: "from-sky-500 to-blue-500" },
  { href: "/community",     icon: Users,         label: "Community",    accent: "from-pink-500 to-rose-500" },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export default function TopNav({ unreadCount = 0 }: { unreadCount?: number }) {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const [menuOpen, setMenuOpen]       = useState(false);
  const [mobileOpen, setMobileOpen]   = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const initial   = (user?.user_metadata?.full_name || user?.email || "U")[0].toUpperCase();
  const avatarUrl = user?.user_metadata?.avatar_url;

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  // close mobile menu on route change
  useEffect(() => { setMobileOpen(false); setMenuOpen(false); }, [pathname]);

  return (
    <header className="sticky top-0 z-50 glass border-b border-surface-border">
      <div className="max-w-7xl mx-auto px-4 lg:px-8 h-16 flex items-center gap-4">

        {/* Brand */}
        <Link href="/" className="flex items-center gap-2.5 group flex-shrink-0">
          <div className="w-9 h-9 rounded-xl bg-brand-gradient flex items-center justify-center shadow-soft group-hover:shadow-soft-lg transition-shadow">
            <Sparkles className="text-white" size={17} strokeWidth={2.6} />
          </div>
          <div className="hidden sm:flex flex-col leading-tight">
            <span className="font-display font-bold text-ink text-base tracking-tight">your<span className="text-gradient">DIU</span></span>
            <span className="text-[9px] text-ink-muted uppercase tracking-widest font-semibold">Campus AI</span>
          </div>
        </Link>

        {/* Center nav — desktop */}
        <nav className="hidden md:flex items-center gap-1 ml-6">
          {MAIN_NAV.map(({ href, icon: Icon, label, accent }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                className={clsx(
                  "relative flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-semibold transition-all duration-200",
                  active
                    ? "text-ink"
                    : "text-ink-dim hover:text-ink hover:bg-surface-soft",
                )}
              >
                <Icon size={15} strokeWidth={active ? 2.6 : 2.2} className={clsx(active && "text-brand-600")} />
                {label}
                {active && (
                  <span className={`absolute -bottom-[1px] left-2 right-2 h-[3px] rounded-full bg-gradient-to-r ${accent}`} />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Spacer to push right cluster */}
        <div className="flex-1" />

        {/* Right actions cluster */}
        <div className="flex items-center gap-1">
          {/* Notices link */}
          <Link
            href="/notices"
            className={clsx(
              "hidden sm:flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium transition-all",
              isActive(pathname, "/notices")
                ? "bg-amber-50 text-amber-700"
                : "text-ink-dim hover:bg-surface-soft hover:text-ink",
            )}
          >
            <FileText size={15} strokeWidth={2.2} />
            <span className="hidden lg:inline">Notices</span>
          </Link>

          {/* Notifications bell */}
          <Link
            href="/notifications"
            className={clsx(
              "relative flex items-center justify-center w-10 h-10 rounded-xl transition-all",
              isActive(pathname, "/notifications")
                ? "bg-orange-50 text-orange-600"
                : "text-ink-dim hover:bg-surface-soft hover:text-ink",
            )}
            aria-label="Notifications"
          >
            <Bell size={17} strokeWidth={2.2} />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 min-w-[18px] h-[18px] px-1 rounded-full bg-gradient-to-br from-orange-500 to-red-500 text-white text-[10px] font-bold flex items-center justify-center ring-2 ring-white">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </Link>

          {/* User avatar dropdown */}
          <div className="relative ml-1" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(o => !o)}
              className="flex items-center gap-2 px-2 py-1.5 rounded-xl hover:bg-surface-soft transition-colors"
            >
              {avatarUrl ? (
                <Image src={avatarUrl} alt="avatar" width={32} height={32} className="w-8 h-8 rounded-full object-cover ring-2 ring-white shadow-soft" />
              ) : (
                <div className="w-8 h-8 rounded-full bg-brand-gradient flex items-center justify-center ring-2 ring-white shadow-soft">
                  <span className="text-white text-xs font-bold">{initial}</span>
                </div>
              )}
              <ChevronDown size={14} className="text-ink-muted hidden sm:block" />
            </button>

            {menuOpen && user && (
              <div className="absolute right-0 top-full mt-2 w-72 bg-white border border-surface-border rounded-2xl shadow-soft-xl overflow-hidden animate-slide-down">
                <div className="p-4 bg-gradient-to-br from-brand-50 to-pink-50 border-b border-surface-border">
                  <div className="flex items-center gap-3">
                    {avatarUrl ? (
                      <Image src={avatarUrl} alt="avatar" width={44} height={44} className="w-11 h-11 rounded-full object-cover ring-2 ring-white shadow-soft" />
                    ) : (
                      <div className="w-11 h-11 rounded-full bg-brand-gradient flex items-center justify-center ring-2 ring-white shadow-soft">
                        <span className="text-white text-sm font-bold">{initial}</span>
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-ink truncate">{user.user_metadata?.full_name || "DIU Student"}</p>
                      <p className="text-xs text-ink-muted truncate">{user.email}</p>
                    </div>
                  </div>
                </div>
                <div className="p-2">
                  <button
                    onClick={() => { setMenuOpen(false); signOut(); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium text-ink-dim hover:bg-red-50 hover:text-red-600 transition-colors"
                  >
                    <LogOut size={15} />
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(o => !o)}
            className="md:hidden ml-1 w-10 h-10 flex items-center justify-center rounded-xl text-ink-dim hover:bg-surface-soft"
            aria-label="Menu"
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {/* Mobile nav drawer */}
      {mobileOpen && (
        <div className="md:hidden border-t border-surface-border bg-white animate-slide-down">
          <nav className="px-4 py-3 space-y-1 max-w-7xl mx-auto">
            {MAIN_NAV.map(({ href, icon: Icon, label, accent }) => {
              const active = isActive(pathname, href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={clsx(
                    "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium",
                    active
                      ? `bg-gradient-to-r ${accent} text-white shadow-soft`
                      : "text-ink-dim hover:bg-surface-soft",
                  )}
                >
                  <Icon size={16} strokeWidth={2.4} />
                  {label}
                </Link>
              );
            })}
            <Link
              href="/notices"
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium sm:hidden",
                isActive(pathname, "/notices") ? "bg-amber-50 text-amber-700" : "text-ink-dim hover:bg-surface-soft",
              )}
            >
              <FileText size={16} strokeWidth={2.4} />
              Notices
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
