"use client";
import Link from "next/link";
import { MessageSquare, FileUp, Users, FileText, Bell, MapPin } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

const FEATURES = [
  { href: "/chat",          icon: MessageSquare, label: "AI Chat",       desc: "Ask anything about DIU — schedules, teachers, info",  color: "text-diu-green" },
  { href: "/pdf-chat",      icon: FileUp,        label: "PDF Chat",      desc: "Upload a PDF and chat with it using AI",              color: "text-blue-400" },
  { href: "/community",     icon: Users,         label: "Community",     desc: "Connect with fellow DIU students",                    color: "text-purple-400" },
  { href: "/notices",       icon: FileText,      label: "Notices",       desc: "Official DIU notices and announcements",              color: "text-yellow-400" },
  { href: "/notifications", icon: Bell,          label: "Notifications", desc: "Your personalized alerts and updates",                color: "text-orange-400" },
];

export default function HomeContent() {
  const { user } = useAuth();
  const name = user?.user_metadata?.full_name?.split(" ")[0] ?? "there";

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-diu-text">
          Hello, {name} 👋
        </h1>
        <p className="text-diu-text-dim mt-1">
          What would you like to do today?
        </p>
      </div>

      {/* Quick action — Chat */}
      <Link href="/chat" className="block mb-8 p-6 bg-diu-green/10 border border-diu-green/30 rounded-2xl hover:border-diu-green/60 transition-colors group">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-diu-green/20 flex items-center justify-center group-hover:bg-diu-green/30 transition-colors">
            <MessageSquare className="text-diu-green" size={22} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-diu-text">Ask the AI Assistant</h2>
            <p className="text-sm text-diu-text-dim">
              Class schedules · Teacher availability · Campus navigation · DIU information
            </p>
          </div>
        </div>
      </Link>

      {/* Feature grid */}
      <div className="grid grid-cols-2 gap-4">
        {FEATURES.slice(1).map(({ href, icon: Icon, label, desc, color }) => (
          <Link
            key={href}
            href={href}
            className="p-5 bg-diu-bg-card border border-diu-border rounded-xl hover:border-diu-border-bright hover:bg-diu-bg-hover transition-colors group"
          >
            <Icon className={`${color} mb-3`} size={20} />
            <h3 className="font-semibold text-diu-text mb-1">{label}</h3>
            <p className="text-xs text-diu-text-dim">{desc}</p>
          </Link>
        ))}
      </div>

      {/* Campus nav hint */}
      <div className="mt-6 p-4 bg-diu-bg-card border border-diu-border rounded-xl flex items-start gap-3">
        <MapPin className="text-diu-green mt-0.5 flex-shrink-0" size={16} />
        <div>
          <p className="text-sm text-diu-text font-medium">Campus Navigation</p>
          <p className="text-xs text-diu-text-dim mt-0.5">
            Ask in Chat — e.g. <span className="text-diu-green">&quot;Main Gate 1 থেকে Food Court কিভাবে যাবো?&quot;</span>
          </p>
        </div>
      </div>
    </div>
  );
}
