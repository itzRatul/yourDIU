"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare, Users, Bell, FileText, FileUp, Home, LogOut,
} from "lucide-react";
import { clsx } from "clsx";
import { useAuth } from "@/hooks/useAuth";

const NAV = [
  { href: "/",             icon: Home,         label: "Home" },
  { href: "/chat",         icon: MessageSquare, label: "Chat" },
  { href: "/pdf-chat",     icon: FileUp,       label: "PDF Chat" },
  { href: "/community",    icon: Users,         label: "Community" },
  { href: "/notices",      icon: FileText,      label: "Notices" },
  { href: "/notifications",icon: Bell,         label: "Notifications" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();

  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-diu-bg-card border-r border-diu-border flex flex-col z-40">
      {/* Logo */}
      <div className="p-5 border-b border-diu-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-diu-green flex items-center justify-center">
            <span className="text-white font-bold text-sm">D</span>
          </div>
          <span className="font-bold text-diu-text text-lg">yourDIU</span>
        </div>
      </div>

      {/* Nav links */}
      <nav className="flex-1 p-3 space-y-1">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "bg-diu-green/10 text-diu-green"
                  : "text-diu-text-dim hover:bg-diu-bg-hover hover:text-diu-text",
              )}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User footer */}
      {user && (
        <div className="p-3 border-t border-diu-border">
          <div className="flex items-center gap-2 px-2 py-2 rounded-lg">
            <div className="w-7 h-7 rounded-full bg-diu-green/20 flex items-center justify-center flex-shrink-0">
              <span className="text-diu-green text-xs font-bold">
                {(user.user_metadata?.full_name || user.email || "U")[0].toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-diu-text truncate">
                {user.user_metadata?.full_name || "User"}
              </p>
              <p className="text-xs text-diu-muted truncate">{user.email}</p>
            </div>
          </div>
          <button
            onClick={signOut}
            className="mt-1 w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-diu-text-dim hover:text-red-400 hover:bg-red-400/10 transition-colors"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}
